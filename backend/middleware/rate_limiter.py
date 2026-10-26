import time
import asyncio
import logging
from typing import Optional, Dict
from config import settings, AppMode

logger = logging.getLogger(__name__)

# Atomic Token Bucket Lua Script for Redis
ATOMIC_RATE_LIMIT_LUA = """
local key = KEYS[1]
local rpm = tonumber(ARGV[1])
local window = tonumber(ARGV[2])
local now = tonumber(ARGV[3])
local cost = tonumber(ARGV[4])

local refill_rate = rpm / window

local data = redis.call('HMGET', key, 'tokens', 'last_refill')
local tokens = tonumber(data[1])
local last_refill = tonumber(data[2])

if not tokens or not last_refill then
    tokens = rpm
    last_refill = now
else
    local elapsed = now - last_refill
    if elapsed > 0 then
        tokens = math.min(rpm, tokens + (elapsed * refill_rate))
        last_refill = now
    end
end

if tokens >= cost then
    tokens = tokens - cost
    redis.call('HMSET', key, 'tokens', tokens, 'last_refill', last_refill)
    redis.call('EXPIRE', key, math.ceil(window * 2))
    return {1, math.floor(tokens), 0}
else
    redis.call('HMSET', key, 'tokens', tokens, 'last_refill', last_refill)
    redis.call('EXPIRE', key, math.ceil(window * 2))
    local wait_time = math.ceil((cost - tokens) / refill_rate)
    return {0, math.floor(tokens), wait_time}
end
"""


class RateLimiter:
    """
    Atomic Token Bucket rate limiter using Redis Lua scripting with
    thread-safe in-memory degraded mode fallback.
    """

    def __init__(self, redis_client, rpm: int = 60):
        self.redis = redis_client
        self.rpm = rpm
        self.window_seconds = 60
        # In-memory degraded fallback structures
        self._local_lock = asyncio.Lock()
        self._local_buckets: Dict[str, dict] = {}

    async def check(self, tenant_id: str, custom_rpm: Optional[int] = None) -> dict:
        start = time.time()
        effective_rpm = custom_rpm if custom_rpm and custom_rpm > 0 else self.rpm
        key = f"rate:{tenant_id}"
        now = time.time()

        try:
            # 1. Execute Atomic Redis Lua Script
            result = await self.redis.eval(
                ATOMIC_RATE_LIMIT_LUA,
                1,
                key,
                str(effective_rpm),
                str(self.window_seconds),
                str(now),
                "1"
            )

            allowed = bool(result[0] == 1)
            remaining = int(result[1])
            retry_after = int(result[2])
            elapsed = (time.time() - start) * 1000

            if allowed:
                return {
                    "allowed": True,
                    "remaining": remaining,
                    "retry_after": 0,
                    "latency_ms": round(max(elapsed, 0.5), 1),
                }
            else:
                return {
                    "allowed": False,
                    "remaining": 0,
                    "retry_after": max(retry_after, 1),
                    "latency_ms": round(max(elapsed, 0.5), 1),
                    "reason": "RATE_LIMIT_EXCEEDED",
                    "message": f"Rate limit quota exceeded. Try again in {max(retry_after, 1)} seconds.",
                    "status_code": 429,
                }

        except Exception as e:
            logger.error("Rate limiter Redis failure for tenant '%s': %s", tenant_id, e)

            # Enforce Protected Mode Failure Policy
            if settings.APP_MODE == AppMode.PROTECTED and settings.REDIS_REQUIRED_IN_PROTECTED:
                elapsed = (time.time() - start) * 1000
                return {
                    "allowed": False,
                    "remaining": 0,
                    "retry_after": 30,
                    "latency_ms": round(max(elapsed, 0.5), 1),
                    "reason": "SECURITY_DEPENDENCY_OUTAGE",
                    "message": "Critical rate-limiting security service is unavailable in protected mode.",
                    "status_code": 503,
                }

            # Local In-Memory Fallback with Asyncio Lock
            return await self._local_check(tenant_id, effective_rpm, start)

    async def _local_check(self, tenant_id: str, rpm: int, start: float) -> dict:
        async with self._local_lock:
            now = time.time()
            refill_rate = rpm / self.window_seconds
            bucket = self._local_buckets.get(tenant_id)

            if not bucket:
                bucket = {"tokens": float(rpm - 1), "last_refill": now}
                self._local_buckets[tenant_id] = bucket
                elapsed = (time.time() - start) * 1000
                return {
                    "allowed": True,
                    "remaining": int(bucket["tokens"]),
                    "retry_after": 0,
                    "latency_ms": round(max(elapsed, 0.5), 1),
                    "mode": "in_memory_fallback",
                }

            elapsed_refill = now - bucket["last_refill"]
            if elapsed_refill > 0:
                bucket["tokens"] = min(float(rpm), bucket["tokens"] + (elapsed_refill * refill_rate))
                bucket["last_refill"] = now

            if bucket["tokens"] >= 1.0:
                bucket["tokens"] -= 1.0
                elapsed = (time.time() - start) * 1000
                return {
                    "allowed": True,
                    "remaining": int(bucket["tokens"]),
                    "retry_after": 0,
                    "latency_ms": round(max(elapsed, 0.5), 1),
                    "mode": "in_memory_fallback",
                }
            else:
                wait_time = int((1.0 - bucket["tokens"]) / refill_rate) + 1
                elapsed = (time.time() - start) * 1000
                return {
                    "allowed": False,
                    "remaining": 0,
                    "retry_after": max(wait_time, 1),
                    "latency_ms": round(max(elapsed, 0.5), 1),
                    "reason": "RATE_LIMIT_EXCEEDED",
                    "message": f"Rate limit quota exceeded. Try again in {max(wait_time, 1)} seconds.",
                    "status_code": 429,
                    "mode": "in_memory_fallback",
                }