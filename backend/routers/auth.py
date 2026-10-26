import hmac
import hashlib
from fastapi import APIRouter, Request, Response, HTTPException, Depends
from pydantic import BaseModel, Field
from config import settings
from middleware.auth import session_store, TenantContext, get_current_tenant

router = APIRouter(prefix="/v1/auth", tags=["auth"])


class LoginRequest(BaseModel):
    api_key: str = Field(..., min_length=1, max_length=512, description="API Key for tenant/admin authentication")


@router.post("/login")
async def login(req: LoginRequest, response: Response):
    """Authenticate with a valid server-side API key and establish an HttpOnly session."""
    registry = settings.key_registry
    resolved_creds = None

    for configured_key, creds in registry.items():
        if hmac.compare_digest(req.api_key.strip(), configured_key):
            resolved_creds = creds
            break

    if not resolved_creds:
        raise HTTPException(
            status_code=401,
            detail="Invalid credentials. Authentication failed.",
        )

    # Create opaque session token in server-side session store
    masked = f"sk-***{hashlib.sha256(resolved_creds.key.encode()).hexdigest()[-4:]}"
    session_id = session_store.create_session(
        tenant_id=resolved_creds.tenant_id,
        role=resolved_creds.role,
        rate_limit_rpm=resolved_creds.rate_limit_rpm or settings.RATE_LIMIT_RPM,
        max_age_seconds=settings.SESSION_MAX_AGE_SECONDS,
        key_masked=masked,
    )

    # Set HttpOnly, SameSite, Secure cookie
    response.set_cookie(
        key=settings.SESSION_COOKIE_NAME,
        value=session_id,
        httponly=True,
        samesite="lax",
        secure=settings.is_cookie_secure,
        max_age=settings.SESSION_MAX_AGE_SECONDS,
        path="/",
    )

    # Return safe tenant context without credentials
    return {
        "status": "authenticated",
        "tenant_id": resolved_creds.tenant_id,
        "role": resolved_creds.role,
        "session_expires_in": settings.SESSION_MAX_AGE_SECONDS,
    }


@router.post("/logout")
async def logout(request: Request, response: Response):
    """Revoke server-side session and clear session cookie."""
    session_cookie = request.cookies.get(settings.SESSION_COOKIE_NAME)
    if session_cookie:
        session_store.revoke_session(session_cookie)

    response.delete_cookie(
        key=settings.SESSION_COOKIE_NAME,
        path="/",
        samesite="lax",
    )
    return {"status": "logged_out"}


@router.get("/session")
async def get_session(request: Request):
    """Check current session status without disclosing sensitive credentials."""
    session_cookie = request.cookies.get(settings.SESSION_COOKIE_NAME)
    if session_cookie:
        tenant = session_store.get_session(session_cookie)
        if tenant:
            return {
                "authenticated": True,
                "tenant_id": tenant.tenant_id,
                "role": tenant.role,
            }

    return {
        "authenticated": False,
        "tenant_id": None,
        "role": None,
    }