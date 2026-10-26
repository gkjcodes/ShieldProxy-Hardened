import time
import hmac
import hashlib
import secrets
from urllib.parse import urlparse
from typing import Optional, Dict, Any
from dataclasses import dataclass
from fastapi import Request, HTTPException, Security
from fastapi.security import APIKeyHeader, HTTPBearer
from config import settings

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)
bearer_auth = HTTPBearer(auto_error=False)


@dataclass
class TenantContext:
    tenant_id: str
    role: str = "client"
    rate_limit_rpm: int = 60
    key_masked: str = "sk-***"

    def is_admin(self) -> bool:
        return self.role.lower() == "admin"


class SessionStore:
    """Server-side opaque session store with TTL expiration and revocation."""

    def __init__(self):
        self._sessions: Dict[str, Dict[str, Any]] = {}

    def create_session(
        self,
        tenant_id: str,
        role: str = "client",
        rate_limit_rpm: int = 60,
        max_age_seconds: int = 3600,
        key_masked: str = "session-cookie"
    ) -> str:
        session_id = secrets.token_urlsafe(32)
        expires_at = time.time() + max_age_seconds
        self._sessions[session_id] = {
            "tenant_id": tenant_id,
            "role": role,
            "rate_limit_rpm": rate_limit_rpm,
            "key_masked": key_masked,
            "expires_at": expires_at,
        }
        return session_id

    def get_session(self, session_id: str) -> Optional[TenantContext]:
        if not session_id or session_id not in self._sessions:
            return None
        data = self._sessions[session_id]
        if time.time() > data["expires_at"]:
            del self._sessions[session_id]
            return None
        return TenantContext(
            tenant_id=data["tenant_id"],
            role=data["role"],
            rate_limit_rpm=data["rate_limit_rpm"],
            key_masked=data["key_masked"],
        )

    def revoke_session(self, session_id: str) -> bool:
        if session_id in self._sessions:
            del self._sessions[session_id]
            return True
        return False

    def clear(self):
        self._sessions.clear()


# Global server session store
session_store = SessionStore()


def _verify_csrf_origin(request: Request):
    """Enforce Origin/Referer check on cookie-authenticated state-changing calls."""
    if request.method in ("POST", "PUT", "DELETE", "PATCH"):
        origin_header = request.headers.get("origin")
        referer_header = request.headers.get("referer")

        candidate = None
        if origin_header:
            candidate = origin_header.strip()
        elif referer_header:
            parsed = urlparse(referer_header.strip())
            candidate = f"{parsed.scheme}://{parsed.netloc}"

        if candidate:
            allowed = [orig.rstrip("/") for orig in settings.cors_origins_list]
            if candidate.rstrip("/") not in allowed:
                raise HTTPException(
                    status_code=403,
                    detail="Cross-site request forgery (CSRF) origin verification failed.",
                )


def _extract_token(request: Request) -> Optional[str]:
    # 1. Check X-API-Key header
    key = request.headers.get("X-API-Key")
    if key and key.strip():
        return key.strip()

    # 2. Check Authorization: Bearer <token>
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.strip():
        parts = auth_header.strip().split()
        if len(parts) == 2 and parts[0].lower() == "bearer":
            return parts[1].strip()

    return None


async def get_current_tenant(request: Request) -> TenantContext:
    # 1. Check HttpOnly Session Cookie first (Browser Session Flow)
    session_cookie = request.cookies.get(settings.SESSION_COOKIE_NAME)
    if session_cookie:
        session_tenant = session_store.get_session(session_cookie)
        if session_tenant:
            # Enforce CSRF Origin verification for cookie sessions
            _verify_csrf_origin(request)
            request.state.tenant = session_tenant
            return session_tenant

    # 2. Check Machine-to-Machine API Key (Header Flow)
    token = _extract_token(request)
    if not token:
        raise HTTPException(
            status_code=401,
            detail="Authentication credentials were not provided. Include 'X-API-Key' or 'Authorization: Bearer <token>', or establish an authenticated session.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    registry = settings.key_registry
    resolved_tenant = None

    # Perform constant-time comparison against configured key registry
    for configured_key, creds in registry.items():
        if hmac.compare_digest(token, configured_key):
            masked = f"sk-***{hashlib.sha256(configured_key.encode()).hexdigest()[-4:]}"
            resolved_tenant = TenantContext(
                tenant_id=creds.tenant_id,
                role=creds.role,
                rate_limit_rpm=creds.rate_limit_rpm or settings.RATE_LIMIT_RPM,
                key_masked=masked,
            )
            break

    if not resolved_tenant:
        raise HTTPException(
            status_code=401,
            detail="Invalid or unrecognized API key.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Attach tenant context to request state for downstream logging/telemetry
    request.state.tenant = resolved_tenant
    return resolved_tenant


async def require_admin_role(
    request: Request,
    tenant: TenantContext = Security(get_current_tenant)
) -> TenantContext:
    if not tenant.is_admin():
        raise HTTPException(
            status_code=403,
            detail="Administrative privileges required to access this resource.",
        )
    return tenant