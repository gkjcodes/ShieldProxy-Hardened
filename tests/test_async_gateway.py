import time
import asyncio
import pytest
from middleware.llm_gateway import LLMGateway
from config import settings, AppMode
from fastapi import HTTPException


@pytest.mark.asyncio
async def test_mock_gateway_uses_async_sleep():
    gw = LLMGateway(use_mock=True)
    start = time.time()
    # Fire 5 concurrent completions
    tasks = [gw.complete(f"Prompt {i}") for i in range(5)]
    results = await asyncio.gather(*tasks)
    total_time = time.time() - start

    assert len(results) == 5
    # If sleep was synchronous time.sleep(0.05), total time would be >= 0.25s.
    # With asyncio.sleep(0.05), all 5 run concurrently in ~0.05s-0.10s.
    assert total_time < 0.20, f"Expected non-blocking concurrency, took {total_time:.3f}s"


@pytest.mark.asyncio
async def test_protected_mode_uninitialized_client_raises_503():
    orig_mode = settings.APP_MODE
    try:
        settings.APP_MODE = AppMode.PROTECTED
        gw = LLMGateway(use_mock=False)
        gw._async_client = None

        with pytest.raises(HTTPException) as exc:
            await gw.complete("Test message", tenant_id="tenant-1")
        assert exc.value.status_code == 503
    finally:
        settings.APP_MODE = orig_mode