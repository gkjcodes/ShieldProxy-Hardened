import os
import sys
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport

os.environ["APP_MODE"] = "test"
os.environ["USE_MOCK_LLM"] = "true"
os.environ["AUTH_KEY_REGISTRY"] = (
    "sk-test-client-123:tenant-alpha:client:60,"
    "sk-test-admin-456:tenant-admin:admin:120,"
    "sk-tenant-beta-789:tenant-beta:client:5"
)
os.environ["MAX_BODY_SIZE_BYTES"] = "65536"
os.environ["GATEWAY_TIMEOUT_SECONDS"] = "2.0"

backend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend"))
if backend_path not in sys.path:
    sys.path.insert(0, backend_path)

from main import app, initialize_app_services
from utils.redis_client import get_redis, reset_redis_client


@pytest_asyncio.fixture
async def async_client():
    reset_redis_client()
    await initialize_app_services()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client


@pytest_asyncio.fixture
async def mock_redis():
    reset_redis_client()
    redis = await get_redis()
    yield redis