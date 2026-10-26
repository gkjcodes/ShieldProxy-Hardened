import pytest


@pytest.mark.asyncio
async def test_chat_unauthenticated_rejected(async_client):
    response = await async_client.post("/v1/chat", json={"message": "Hello"})
    assert response.status_code == 401
    assert "Authentication credentials were not provided" in response.json()["message"]


@pytest.mark.asyncio
async def test_chat_invalid_api_key_rejected(async_client):
    response = await async_client.post(
        "/v1/chat",
        headers={"X-API-Key": "invalid-random-key-999"},
        json={"message": "Hello"}
    )
    assert response.status_code == 401
    assert "Invalid or unrecognized" in response.json()["message"]


@pytest.mark.asyncio
async def test_chat_valid_api_key_passes(async_client):
    response = await async_client.post(
        "/v1/chat",
        headers={"X-API-Key": "sk-test-client-123"},
        json={"message": "What is the weather?"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["blocked"] is False
    assert data["tenant_id"] == "tenant-alpha"


@pytest.mark.asyncio
async def test_chat_bearer_auth_supported(async_client):
    response = await async_client.post(
        "/v1/chat",
        headers={"Authorization": "Bearer sk-test-client-123"},
        json={"message": "What is the weather?"}
    )
    assert response.status_code == 200
    assert response.json()["tenant_id"] == "tenant-alpha"


@pytest.mark.asyncio
async def test_caller_cannot_spoof_tenant_via_body(async_client):
    # Caller authenticates with Tenant Alpha key, but attempts to spoof Tenant Beta in body
    response = await async_client.post(
        "/v1/chat",
        headers={"X-API-Key": "sk-test-client-123"},
        json={"message": "Hello", "client_id": "tenant-beta"}
    )
    assert response.status_code == 200
    # Must be bound to authenticated tenant (tenant-alpha), NOT spoofed body client_id
    assert response.json()["tenant_id"] == "tenant-alpha"


@pytest.mark.asyncio
async def test_dashboard_clients_requires_admin_role(async_client):
    # 1. Ordinary client key gets 403 Forbidden
    client_resp = await async_client.get(
        "/v1/dashboard/clients",
        headers={"X-API-Key": "sk-test-client-123"}
    )
    assert client_resp.status_code == 403
    assert "Administrative privileges required" in client_resp.json()["detail"]

    # 2. Admin key gets 200 OK
    admin_resp = await async_client.get(
        "/v1/dashboard/clients",
        headers={"X-API-Key": "sk-test-admin-456"}
    )
    assert admin_resp.status_code == 200