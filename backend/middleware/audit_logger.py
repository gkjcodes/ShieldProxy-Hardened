import time
import hashlib
import logging
from datetime import datetime, timedelta
from collections import deque
from typing import Optional, List, Dict

logger = logging.getLogger(__name__)

STREAM_KEY = "shieldproxy:audit"
MAX_ENTRIES = 10000


class AuditLogger:
    """
    Privacy-safe Audit Logger.
    Persists structured security event metadata to Redis streams with in-memory deque fallback.
    Enforces Phase 1 Zero-Raw-Prompt Policy: user prompt text, raw PII, and response text
    are strictly excluded from routine event logs.
    """

    def __init__(self, redis_client):
        self.redis = redis_client
        self._memory_log = deque(maxlen=MAX_ENTRIES)

    async def log(self, entry: dict):
        try:
            # Build safe, non-sensitive event preview metadata
            threat_type = str(entry.get("threat_type", "SAFE"))
            is_blocked = str(entry.get("is_blocked", False))

            if str(is_blocked).lower() == "true":
                patterns = entry.get("matched_patterns", [])
                pattern_str = f" ({','.join(patterns[:2])})" if patterns else ""
                preview = f"[{threat_type}_BLOCKED]{pattern_str}"
            else:
                preview = f"[PASSED] Query processed cleanly"

            prompt_hash = str(entry.get("prompt_hash", ""))

            fields = {
                "timestamp": entry.get("timestamp", datetime.utcnow().isoformat() + "Z"),
                "tenant_id": str(entry.get("tenant_id") or entry.get("client_id") or "anonymous"),
                "request_id": str(entry.get("request_id", "")),
                "threat_type": threat_type,
                "is_blocked": is_blocked,
                "confidence": str(entry.get("confidence", 0.0)),
                "pii_count": str(entry.get("pii_count", 0)),
                "latency_ms": str(entry.get("latency_ms", 0)),
                "prompt_hash": prompt_hash,
                "prompt_preview": preview,
            }

            await self.redis.xadd(STREAM_KEY, fields, maxlen=MAX_ENTRIES)
            self._memory_log.append(fields)

        except Exception as e:
            logger.warning("Audit log write failed: %s", e)
            fallback_fields = {
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "tenant_id": str(entry.get("tenant_id") or "unknown"),
                "request_id": str(entry.get("request_id", "")),
                "threat_type": str(entry.get("threat_type", "UNKNOWN")),
                "is_blocked": str(entry.get("is_blocked", False)),
                "confidence": str(entry.get("confidence", 0.0)),
                "pii_count": str(entry.get("pii_count", 0)),
                "latency_ms": str(entry.get("latency_ms", 0)),
                "prompt_hash": "",
                "prompt_preview": "[LOG_FAILURE]",
            }
            self._memory_log.append(fallback_fields)

    async def get_recent(self, count: int = 50, tenant_id: Optional[str] = None) -> List[dict]:
        results = []
        try:
            entries = await self.redis.xrevrange(STREAM_KEY, count=count * 2)
            for entry_id, fields in entries:
                fields_dict = dict(fields)
                fields_dict["id"] = entry_id
                if tenant_id and fields_dict.get("tenant_id") != tenant_id:
                    continue
                results.append(fields_dict)
                if len(results) >= count:
                    break
            if results:
                return results
        except Exception as e:
            logger.warning("Redis audit stream read failed, using memory: %s", e)

        mem_entries = list(self._memory_log)
        mem_entries.reverse()
        for e in mem_entries:
            if tenant_id and e.get("tenant_id") != tenant_id:
                continue
            results.append(dict(e))
            if len(results) >= count:
                break
        return results

    async def get_stats(self, tenant_id: Optional[str] = None) -> dict:
        entries = await self.get_recent(500, tenant_id=tenant_id)
        if not entries:
            return {
                "total_requests": 0,
                "total_blocked": 0,
                "total_passed": 0,
                "block_rate": 0.0,
                "threats_by_type": {},
                "avg_latency_ms": 0.0,
                "requests_last_hour": 0,
            }

        total = len(entries)
        blocked = sum(1 for e in entries if str(e.get("is_blocked", "False")).lower() == "true")
        passed = total - blocked

        threats_by_type: Dict[str, int] = {}
        total_latency = 0.0
        now = datetime.utcnow()
        requests_last_hour = 0

        for e in entries:
            tt = e.get("threat_type", "SAFE")
            if tt != "SAFE":
                threats_by_type[tt] = threats_by_type.get(tt, 0) + 1
            total_latency += float(e.get("latency_ms", 0))
            try:
                ts = datetime.fromisoformat(e.get("timestamp", "").replace("Z", ""))
                if (now - ts) < timedelta(hours=1):
                    requests_last_hour += 1
            except Exception:
                pass

        return {
            "total_requests": total,
            "total_blocked": blocked,
            "total_passed": passed,
            "block_rate": round(blocked / max(total, 1) * 100, 1),
            "threats_by_type": threats_by_type,
            "avg_latency_ms": round(total_latency / max(total, 1), 1),
            "requests_last_hour": requests_last_hour,
        }

    async def get_client_stats(self) -> List[dict]:
        entries = await self.get_recent(500)
        if not entries:
            return []

        clients = {}
        for e in entries:
            cid = e.get("tenant_id") or e.get("client_id") or "anonymous"
            if cid not in clients:
                clients[cid] = {
                    "client_id": cid,
                    "api_key_masked": f"sk-***{hashlib.sha256(cid.encode()).hexdigest()[-4:]}",
                    "total_requests": 0,
                    "total_blocked": 0,
                    "last_active": e.get("timestamp", ""),
                    "status": "active",
                }
            clients[cid]["total_requests"] += 1
            if str(e.get("is_blocked", "False")).lower() == "true":
                clients[cid]["total_blocked"] += 1
            ts = e.get("timestamp", "")
            if ts > clients[cid]["last_active"]:
                clients[cid]["last_active"] = ts

        result = []
        for c in clients.values():
            c["block_rate"] = round(
                c["total_blocked"] / max(c["total_requests"], 1) * 100, 1
            )
            try:
                last = datetime.fromisoformat(c["last_active"].replace("Z", ""))
                c["status"] = "active" if (datetime.utcnow() - last) < timedelta(minutes=5) else "idle"
            except Exception:
                c["status"] = "idle"
            result.append(c)

        return result