import time
import logging
from collections import deque
from typing import Optional

logger = logging.getLogger(__name__)


class MockRedis:
    """In-memory fallback when Redis is unavailable, with TTL and atomic lock support."""

    def __init__(self):
        self._data = {}
        self._hash_data = {}
        self._ttls = {}
        self._streams = {}

    def _purge_if_expired(self, key: str) -> bool:
        if key in self._ttls:
            if time.time() > self._ttls[key]:
                self._data.pop(key, None)
                self._hash_data.pop(key, None)
                self._ttls.pop(key, None)
                return True
        return False

    async def get(self, key: str):
        if self._purge_if_expired(key):
            return None
        return self._data.get(key)

    async def set(self, key: str, value, ex: Optional[int] = None):
        self._data[key] = str(value)
        if ex is not None:
            self._ttls[key] = time.time() + ex
        else:
            self._ttls.pop(key, None)

    async def incr(self, key: str):
        self._purge_if_expired(key)
        val = int(self._data.get(key, 0)) + 1
        self._data[key] = str(val)
        return val

    async def decr(self, key: str):
        self._purge_if_expired(key)
        val = int(self._data.get(key, 0)) - 1
        self._data[key] = str(val)
        return val

    async def expire(self, key: str, seconds: int):
        if key in self._data or key in self._hash_data or key in self._streams:
            self._ttls[key] = time.time() + seconds
            return 1
        return 0

    async def ttl(self, key: str) -> int:
        if self._purge_if_expired(key):
            return -2
        if key not in self._ttls:
            if key in self._data or key in self._hash_data:
                return -1
            return -2
        remaining = int(self._ttls[key] - time.time())
        return max(remaining, 0)

    async def exists(self, key: str) -> int:
        if self._purge_if_expired(key):
            return 0
        return 1 if (key in self._data or key in self._hash_data or key in self._streams) else 0

    async def delete(self, key: str):
        self._data.pop(key, None)
        self._hash_data.pop(key, None)
        self._ttls.pop(key, None)
        self._streams.pop(key, None)

    async def hset(self, key: str, mapping: dict):
        self._purge_if_expired(key)
        if key not in self._hash_data:
            self._hash_data[key] = {}
        for k, v in mapping.items():
            self._hash_data[key][str(k)] = str(v)

    async def hgetall(self, key: str) -> dict:
        if self._purge_if_expired(key):
            return {}
        return dict(self._hash_data.get(key, {}))

    async def eval(self, script: str, numkeys: int, *keys_and_args):
        """Mock execution of atomic rate limiting Lua script in MockRedis."""
        keys = keys_and_args[:numkeys]
        args = keys_and_args[numkeys:]
        key = keys[0]
        rpm = float(args[0])
        window = float(args[1])
        now = float(args[2])
        cost = float(args[3]) if len(args) > 3 else 1.0

        refill_rate = rpm / window
        self._purge_if_expired(key)

        hdata = self._hash_data.get(key, {})
        tokens = float(hdata.get("tokens", rpm))
        last_refill = float(hdata.get("last_refill", now))

        if key in self._hash_data:
            elapsed = now - last_refill
            if elapsed > 0:
                tokens = min(rpm, tokens + (elapsed * refill_rate))
                last_refill = now

        if tokens >= cost:
            tokens -= cost
            self._hash_data[key] = {"tokens": str(tokens), "last_refill": str(now)}
            self._ttls[key] = now + (window * 2)
            wait_sec = 0
            return [1, int(tokens), wait_sec]
        else:
            self._hash_data[key] = {"tokens": str(tokens), "last_refill": str(last_refill)}
            self._ttls[key] = now + (window * 2)
            wait_sec = int((cost - tokens) / refill_rate) + 1
            return [0, int(tokens), wait_sec]

    async def xadd(self, stream: str, fields: dict, maxlen: Optional[int] = None):
        if stream not in self._streams:
            self._streams[stream] = deque(maxlen=maxlen or 10000)
        entry_id = f"{int(time.time() * 1000)}-{len(self._streams[stream])}"
        self._streams[stream].append((entry_id, fields))
        return entry_id

    async def xrevrange(self, stream: str, max="+", min="-", count: Optional[int] = None):
        if stream not in self._streams:
            return []
        entries = list(self._streams[stream])
        entries.reverse()
        if count:
            entries = entries[:count]
        return entries

    async def xlen(self, stream: str) -> int:
        return len(self._streams.get(stream, []))

    async def ping(self) -> bool:
        return True


_redis_client = None


async def get_redis():
    global _redis_client
    if _redis_client is not None:
        return _redis_client

    try:
        import redis.asyncio as aioredis
        from config import settings

        client = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
        await client.ping()
        _redis_client = client
        logger.info("✅ Connected to Redis at %s", settings.REDIS_URL)
    except Exception as e:
        logger.warning("⚠️ Redis unavailable (%s), using in-memory fallback", e)
        _redis_client = MockRedis()

    return _redis_client


def reset_redis_client():
    """Allows test fixtures to reset client singleton."""
    global _redis_client
    _redis_client = None