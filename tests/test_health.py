import pytest


@pytest.mark.asyncio
async def test_health_live_endpoint(async_client):
    response = await async_client.get("/health/live")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "alive"
    assert data["service"] == "shieldproxy"


@pytest.mark.asyncio
async def test_health_ready_endpoint(async_client):
    response = await async_client.get("/health/ready")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ready"
    assert "redis" in data["checks"]
    assert "llm_mode" in data["checks"]


@pytest.mark.asyncio
async def test_health_legacy_compatibility(async_client):
    response = await async_client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ready"