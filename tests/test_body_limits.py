import pytest


@pytest.mark.asyncio
async def test_body_within_limit_passes(async_client):
    small_payload = {"message": "A" * 100}
    response = await async_client.post(
        "/v1/chat",
        headers={"X-API-Key": "sk-test-client-123"},
        json=small_payload,
    )
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_oversized_declared_content_length_rejected(async_client):
    # 70,000 bytes exceeds 65,536 limit
    large_msg = "X" * 70000
    response = await async_client.post(
        "/v1/chat",
        headers={
            "X-API-Key": "sk-test-client-123",
            "Content-Length": str(len(large_msg) + 50),
        },
        json={"message": large_msg},
    )
    assert response.status_code == 413
    assert "PAYLOAD_TOO_LARGE" in response.json()["error"]


@pytest.mark.asyncio
async def test_validation_error_safe_schema(async_client):
    # Pass invalid payload (missing required 'message')
    response = await async_client.post(
        "/v1/chat",
        headers={"X-API-Key": "sk-test-client-123"},
        json={"wrong_field": 123},
    )
    assert response.status_code == 422
    data = response.json()
    assert data["error"] == "VALIDATION_ERROR"
    assert "Traceback" not in str(data)