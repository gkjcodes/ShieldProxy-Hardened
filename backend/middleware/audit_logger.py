import time
import hashlib
import logging
from datetime import datetime, timedelta
from collections import deque

logger = logging.getLogger(__name__)

STREAM_KEY = "shieldproxy:audit"
MAX_ENTRIES = 10000


class AuditLogger:
    """Logs all requests to Redis streams with fallback to in-memory deque."""

    def __init__(self, redis_client):
        self.redis = redis_client
        self._memory_log = deque(maxlen=MAX_ENTRIES)

    async def log(self, entry: dict):
        try:
            fields = {
                "timestamp": entry.get("timestamp", datetime.utcnow().isoformat() + "Z"),
                "client_id": str(entry.get("client_id", "anonymous")),
                "request_id": str(entry.get("request_id", "")),
                "threat_type": str(entry.get("threat_type", "SAFE")),
                "is_blocked": str(entry.get("is_blocked", False)),
                "confidence": str(entry.get("confidence", 0.0)),
                "pii_count": str(entry.get("pii_count", 0)),
                "latency_ms": str(entry.get("latency_ms", 0)),
                "prompt_hash": hashlib.sha256(
                    entry.get("prompt", "").encode()
                ).hexdigest()[:16],
                "prompt_preview": entry.get("prompt", "")[:80],
            }
            await self.redis.xadd(STREAM_KEY, fields, maxlen=MAX_ENTRIES)
            self._memory_log.append(fields)
        except Exception as e:
            logger.warning("Audit log write failed: %s", e)
            fields["timestamp"] = datetime.utcnow().isoformat() + "Z"
            self._memory_log.append(fields)

    async def get_recent(self, count: int = 50) -> list:
        try:
            entries = await self.redis.xrevrange(STREAM_KEY, count=count)
            results = []
            for entry_id, fields in entries:
                fields["id"] = entry_id
                results.append(fields)
            if results:
                return results
        except Exception as e:
            logger.warning("Redis read failed, using memory: %s", e)

        entries = list(self._memory_log)
        entries.reverse()
        return entries[:count]

    async def get_stats(self) -> dict:
        entries = await self.get_recent(500)

        if not entries:
            from utils.mock_data import generate_mock_stats
            return generate_mock_stats()

        total = len(entries)
        blocked = sum(1 for e in entries if str(e.get("is_blocked", "False")).lower() == "true")
        passed = total - blocked

        threats_by_type = {}
        total_latency = 0
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

    async def get_client_stats(self) -> list:
        entries = await self.get_recent(500)

        if not entries:
            from utils.mock_data import generate_mock_clients
            return generate_mock_clients()

        clients = {}
        for e in entries:
            cid = e.get("client_id", "anonymous")
            if cid not in clients:
                clients[cid] = {
                    "client_id": cid,
                    "api_key_masked": f"sk-***{hashlib.md5(cid.encode()).hexdigest()[-4:]}",
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
