import asyncio
import pytest
from middleware.rate_limiter import RateLimiter
from utils.redis_client import MockRedis
from config import settings, AppMode


@pytest.mark.asyncio
async def test_rate_limiter_allows_under_quota():
    redis = MockRedis()
    limiter = RateLimiter(redis, rpm=10)
    result = await limiter.check("tenant-1")
    assert result["allowed"] is True
    assert result["remaining"] == 9


@pytest.mark.asyncio
async def test_rate_limiter_blocks_burst_over_quota():
    redis = MockRedis()
    limiter = RateLimiter(redis, rpm=3)

    r1 = await limiter.check("tenant-fast", custom_rpm=3)
    r2 = await limiter.check("tenant-fast", custom_rpm=3)
    r3 = await limiter.check("tenant-fast", custom_rpm=3)
    r4 = await limiter.check("tenant-fast", custom_rpm=3)

    assert r1["allowed"] is True
    assert r2["allowed"] is True
    assert r3["allowed"] is True
    assert r4["allowed"] is False
    assert r4["reason"] == "RATE_LIMIT_EXCEEDED"
    assert r4["retry_after"] >= 1


@pytest.mark.asyncio
async def test_rate_limiter_tenant_isolation():
    redis = MockRedis()
    limiter = RateLimiter(redis, rpm=2)

    # Exhaust tenant A quota
    await limiter.check("tenant-A", custom_rpm=2)
    await limiter.check("tenant-A", custom_rpm=2)
    rA3 = await limiter.check("tenant-A", custom_rpm=2)
    assert rA3["allowed"] is False

    # Tenant B must remain unaffected
    rB1 = await limiter.check("tenant-B", custom_rpm=2)
    assert rB1["allowed"] is True
    assert rB1["remaining"] == 1


@pytest.mark.asyncio
async def test_rate_limiter_concurrent_burst_atomic():
    redis = MockRedis()
    limiter = RateLimiter(redis, rpm=5)

    # Fire 15 concurrent requests simultaneously
    tasks = [limiter.check("concurrent-tenant", custom_rpm=5) for _ in range(15)]
    results = await asyncio.gather(*tasks)

    allowed_count = sum(1 for r in results if r["allowed"])
    blocked_count = sum(1 for r in results if not r["allowed"])

    assert allowed_count == 5
    assert blocked_count == 10


@pytest.mark.asyncio
async def test_rate_limiter_protected_mode_outage_policy():
    class BrokenRedis:
        async def eval(self, *args, **kwargs):
            raise ConnectionError("Redis cluster unreachable")

    broken_redis = BrokenRedis()
    limiter = RateLimiter(broken_redis, rpm=60)

    # Test mode: falls back to in-memory limiter without failing open
    res_test = await limiter.check("tenant-fallback")
    assert res_test["allowed"] is True
    assert res_test.get("mode") == "in_memory_fallback"

    # Protected mode with required Redis: returns 503
    orig_mode = settings.APP_MODE
    orig_req = settings.REDIS_REQUIRED_IN_PROTECTED
    try:
        settings.APP_MODE = AppMode.PROTECTED
        settings.REDIS_REQUIRED_IN_PROTECTED = True
        res_protected = await limiter.check("tenant-protected")
        assert res_protected["allowed"] is False
        assert res_protected["status_code"] == 503
        assert res_protected["reason"] == "SECURITY_DEPENDENCY_OUTAGE"
    finally:
        settings.APP_MODE = orig_mode
        settings.REDIS_REQUIRED_IN_PROTECTED = orig_req