import time
import logging

logger = logging.getLogger(__name__)


class RateLimiter:
    """Token bucket rate limiter using Redis (or in-memory fallback)."""

    def __init__(self, redis_client, rpm: int = 60):
        self.redis = redis_client
        self.rpm = rpm
        self.window_seconds = 60

    async def check(self, client_id: str) -> dict:
        start = time.time()
        key = f"rate:{client_id}"
        ts_key = f"rate_ts:{client_id}"

        try:
            tokens = await self.redis.get(key)
            last_refill = await self.redis.get(ts_key)
            now = time.time()

            if tokens is None or last_refill is None:
                tokens = float(self.rpm - 1)
                await self.redis.set(key, str(tokens), ex=self.window_seconds * 2)
                await self.redis.set(ts_key, str(now), ex=self.window_seconds * 2)
                elapsed = (time.time() - start) * 1000
                return {
                    "allowed": True,
                    "remaining": int(tokens),
                    "latency_ms": round(max(elapsed, 1), 1),
                }

            tokens = float(tokens)
            last_refill = float(last_refill)
            elapsed_since_refill = now - last_refill

            # Continuous token bucket refill based on time elapsed
            refill_rate = self.rpm / self.window_seconds  # tokens per second
            new_tokens = elapsed_since_refill * refill_rate

            if new_tokens > 0:
                tokens = min(float(self.rpm), tokens + new_tokens)
                last_refill = now

            if tokens < 1:
                # Save fractional tokens so they continue to refill accurately over time
                await self.redis.set(key, str(tokens), ex=self.window_seconds * 2)
                await self.redis.set(ts_key, str(last_refill), ex=self.window_seconds * 2)
                elapsed = (time.time() - start) * 1000
                return {
                    "allowed": False,
                    "remaining": 0,
                    "latency_ms": round(max(elapsed, 1), 1),
                    "reason": "RATE_LIMIT_EXCEEDED",
                    "message": "Too many requests. Slow down.",
                }

            tokens -= 1
            await self.redis.set(key, str(tokens), ex=self.window_seconds * 2)
            await self.redis.set(ts_key, str(now), ex=self.window_seconds * 2)
            elapsed = (time.time() - start) * 1000
            return {
                "allowed": True,
                "remaining": int(tokens),
                "latency_ms": round(max(elapsed, 1), 1),
            }

        except Exception as e:
            logger.error("Rate limiter error: %s", e)
            elapsed = (time.time() - start) * 1000
            return {
                "allowed": True,
                "remaining": -1,
                "latency_ms": round(max(elapsed, 1), 1),
            }
