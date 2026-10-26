import time
import logging
from collections import deque

logger = logging.getLogger(__name__)


class MockRedis:
    """In-memory fallback when Redis is unavailable."""

    def __init__(self):
        self._data = {}
        self._streams = {}
        self._counters = {}

    async def get(self, key):
        return self._data.get(key)

    async def set(self, key, value, ex=None):
        self._data[key] = str(value)

    async def incr(self, key):
        val = int(self._data.get(key, 0)) + 1
        self._data[key] = str(val)
        return val

    async def decr(self, key):
        val = int(self._data.get(key, 0)) - 1
        self._data[key] = str(val)
        return val

    async def expire(self, key, seconds):
        pass

    async def ttl(self, key):
        return -1

    async def exists(self, key):
        return 1 if key in self._data else 0

    async def delete(self, key):
        self._data.pop(key, None)

    async def xadd(self, stream, fields, maxlen=None):
        if stream not in self._streams:
            self._streams[stream] = deque(maxlen=maxlen or 10000)
        entry_id = f"{int(time.time() * 1000)}-{len(self._streams[stream])}"
        self._streams[stream].append((entry_id, fields))
        return entry_id

    async def xrevrange(self, stream, max="+", min="-", count=None):
        if stream not in self._streams:
            return []
        entries = list(self._streams[stream])
        entries.reverse()
        if count:
            entries = entries[:count]
        return entries

    async def xlen(self, stream):
        return len(self._streams.get(stream, []))

    async def ping(self):
        return True


_redis_client = None


async def get_redis():
    global _redis_client
    if _redis_client is not None:
        return _redis_client

    try:
        import redis.asyncio as aioredis
        from config import REDIS_URL

        client = aioredis.from_url(REDIS_URL, decode_responses=True)
        await client.ping()
        _redis_client = client
        logger.info("✅ Connected to Redis at %s", REDIS_URL)
    except Exception as e:
        logger.warning("⚠️ Redis unavailable (%s), using in-memory fallback", e)
        _redis_client = MockRedis()

    return _redis_client
