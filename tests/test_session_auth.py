import os
import glob
import pytest
from config import Settings, AppMode


@pytest.mark.asyncio
async def test_login_success_sets_httponly_cookie(async_client):
    response = await async_client.post(
        "/v1/auth/login",
        json={"api_key": "sk-test-client-123"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "authenticated"
    assert data["tenant_id"] == "tenant-alpha"
    assert data["role"] == "client"
    # Never disclose raw credentials or secrets
    assert "sk-test-client-123" not in response.text

    # Verify cookie attributes
    cookie_header = response.headers.get("set-cookie", "")
    assert "shieldproxy_session=" in cookie_header
    assert "HttpOnly" in cookie_header
    assert "SameSite=lax" in cookie_header


@pytest.mark.asyncio
async def test_login_invalid_key_fails_cleanly(async_client):
    response = await async_client.post(
        "/v1/auth/login",
        json={"api_key": "invalid-fake-key-999"}
    )
    assert response.status_code == 401
    assert "Invalid credentials" in response.json()["detail"]
    assert "set-cookie" not in response.headers


@pytest.mark.asyncio
async def test_session_cookie_authenticates_chat_with_valid_origin(async_client):
    # 1. Login
    login_resp = await async_client.post("/v1/auth/login", json={"api_key": "sk-test-client-123"})
    assert login_resp.status_code == 200
    session_cookie = login_resp.cookies.get("shieldproxy_session")
    assert session_cookie is not None

    # 2. Chat using session cookie with valid Origin header
    chat_resp = await async_client.post(
        "/v1/chat",
        headers={"Origin": "http://localhost:5173"},
        cookies={"shieldproxy_session": session_cookie},
        json={"message": "What is the capital of France?"}
    )
    assert chat_resp.status_code == 200
    data = chat_resp.json()
    assert data["blocked"] is False
    assert data["tenant_id"] == "tenant-alpha"


@pytest.mark.asyncio
async def test_session_cookie_csrf_origin_check_blocks_untrusted_origin(async_client):
    # 1. Login
    login_resp = await async_client.post("/v1/auth/login", json={"api_key": "sk-test-client-123"})
    session_cookie = login_resp.cookies.get("shieldproxy_session")

    # 2. Cross-origin request from untrusted origin
    chat_resp = await async_client.post(
        "/v1/chat",
        headers={"Origin": "https://attacker-phishing.example.com"},
        cookies={"shieldproxy_session": session_cookie},
        json={"message": "Test CSRF payload"}
    )
    assert chat_resp.status_code == 403
    assert "CSRF" in chat_resp.json()["detail"] or "origin" in chat_resp.json()["detail"]


@pytest.mark.asyncio
async def test_client_session_cannot_access_admin_dashboard(async_client):
    # Client login
    login_resp = await async_client.post("/v1/auth/login", json={"api_key": "sk-test-client-123"})
    session_cookie = login_resp.cookies.get("shieldproxy_session")

    # Access admin-only endpoint
    clients_resp = await async_client.get(
        "/v1/dashboard/clients",
        cookies={"shieldproxy_session": session_cookie}
    )
    assert clients_resp.status_code == 403
    assert "Administrative privileges required" in clients_resp.json()["detail"]


@pytest.mark.asyncio
async def test_admin_session_can_access_admin_dashboard(async_client):
    # Admin login
    login_resp = await async_client.post("/v1/auth/login", json={"api_key": "sk-test-admin-456"})
    session_cookie = login_resp.cookies.get("shieldproxy_session")

    # Access admin-only endpoint
    clients_resp = await async_client.get(
        "/v1/dashboard/clients",
        cookies={"shieldproxy_session": session_cookie}
    )
    assert clients_resp.status_code == 200


@pytest.mark.asyncio
async def test_logout_revokes_session(async_client):
    # 1. Login
    login_resp = await async_client.post("/v1/auth/login", json={"api_key": "sk-test-client-123"})
    session_cookie = login_resp.cookies.get("shieldproxy_session")

    # 2. Logout
    logout_resp = await async_client.post(
        "/v1/auth/logout",
        cookies={"shieldproxy_session": session_cookie}
    )
    assert logout_resp.status_code == 200
    assert logout_resp.json()["status"] == "logged_out"

    # 3. Subsequent request with revoked cookie is rejected
    stats_resp = await async_client.get(
        "/v1/dashboard/stats",
        cookies={"shieldproxy_session": session_cookie}
    )
    assert stats_resp.status_code == 401


@pytest.mark.asyncio
async def test_forged_or_expired_session_rejected(async_client):
    resp = await async_client.get(
        "/v1/dashboard/stats",
        cookies={"shieldproxy_session": "forged-invalid-session-token"}
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_session_status_endpoint(async_client):
    # Unauthenticated
    unauth_resp = await async_client.get("/v1/auth/session")
    assert unauth_resp.status_code == 200
    assert unauth_resp.json()["authenticated"] is False

    # Authenticated
    login_resp = await async_client.post("/v1/auth/login", json={"api_key": "sk-test-client-123"})
    session_cookie = login_resp.cookies.get("shieldproxy_session")
    auth_resp = await async_client.get(
        "/v1/auth/session",
        cookies={"shieldproxy_session": session_cookie}
    )
    assert auth_resp.status_code == 200
    assert auth_resp.json()["authenticated"] is True
    assert auth_resp.json()["tenant_id"] == "tenant-alpha"
    assert auth_resp.json()["role"] == "client"


def test_no_admin_keys_in_frontend_source():
    api_js_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src", "services", "api.js"))
    with open(api_js_path, "r", encoding="utf-8") as f:
        src = f.read()

    assert "sk-dev-admin-99999" not in src
    assert "VITE_API_KEY" not in src


def test_no_default_admin_in_backend_config():
    # Fresh settings without AUTH_KEY_REGISTRY set
    s = Settings(APP_MODE=AppMode.DEVELOPMENT, AUTH_KEY_REGISTRY="")
    assert "sk-dev-admin-99999" not in s.key_registry
    assert len(s.key_registry) == 0


def test_production_bundle_clean_of_credentials():
    dist_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "dist", "assets"))
    js_files = glob.glob(os.path.join(dist_dir, "index-*.js"))
    assert len(js_files) > 0, "Production bundle must be built before running this check"

    for js_path in js_files:
        with open(js_path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
        assert "sk-dev-admin-99999" not in content
        assert "VITE_API_KEY" not in content
        assert "sk-dev-" not in content