import uuid
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from config import settings, AppMode
from utils.redis_client import get_redis
from middleware.body_limit import BodySizeLimitMiddleware
from middleware.rate_limiter import RateLimiter
from middleware.threat_classifier import ThreatClassifier
from middleware.pii_scrubber import PIIScrubber
from middleware.audit_logger import AuditLogger
from middleware.output_filter import OutputFilter
from middleware.llm_gateway import LLMGateway
from routers import chat, dashboard, auth

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
)
logger = logging.getLogger("shieldproxy")

_redis = None
_rate_limiter = None
_threat_classifier = None
_llm_gateway = None


async def initialize_app_services():
    global _redis, _rate_limiter, _threat_classifier, _llm_gateway
    _redis = await get_redis()
    _rate_limiter = RateLimiter(_redis, rpm=settings.RATE_LIMIT_RPM)
    _threat_classifier = ThreatClassifier(use_mock=settings.USE_MOCK_LLM)
    ps = PIIScrubber()
    al = AuditLogger(_redis)
    of = OutputFilter()
    _llm_gateway = LLMGateway(use_mock=settings.USE_MOCK_LLM)

    chat.init_pipeline(_rate_limiter, _threat_classifier, ps, al, _llm_gateway, of)
    dashboard.init_dashboard(al)
    logger.info("All security middleware and routers initialized")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("ShieldProxy Backend Starting in [%s] mode...", settings.APP_MODE.value)
    logger.info("   Mock LLM: %s | Rate Limit: %d RPM | Body Limit: %d bytes",
                settings.USE_MOCK_LLM, settings.RATE_LIMIT_RPM, settings.MAX_BODY_SIZE_BYTES)
    await initialize_app_services()
    yield
    logger.info("ShieldProxy shutting down...")


app = FastAPI(
    title="ShieldProxy Hardened",
    description="LLM Prompt Injection Firewall - Hardened Security Gateway with strict authentication, atomic rate limiting, and zero prompt retention.",
    version="1.1.0",
    lifespan=lifespan,
)

# 1. Enforce strict request body size limiting at ASGI layer
app.add_middleware(
    BodySizeLimitMiddleware,
    max_body_size=settings.MAX_BODY_SIZE_BYTES,
)

# 2. CORS configuration (Whitelisted origins only, credentials enabled, no wildcard origins)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

# 3. Global safe exception handling (prevent stack trace and prompt leakage)
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    req_id = getattr(request.state, "request_id", uuid.uuid4().hex[:16])
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "error": "VALIDATION_ERROR",
            "message": "Invalid request parameters or payload format.",
            "detail": exc.errors(),
            "request_id": req_id,
        },
    )


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    if isinstance(exc.detail, dict):
        return JSONResponse(status_code=exc.status_code, content=exc.detail)
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": "HTTP_ERROR",
            "message": str(exc.detail),
            "detail": str(exc.detail),
            "status_code": exc.status_code,
        },
    )


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    req_id = getattr(request.state, "request_id", uuid.uuid4().hex[:16])
    logger.exception("Unhandled gateway exception (req_id=%s)", req_id)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": "INTERNAL_SERVER_ERROR",
            "message": "An unexpected error occurred while processing the request.",
            "detail": "An unexpected error occurred while processing the request.",
            "request_id": req_id,
        },
    )


# Mount routers
app.include_router(auth.router)
app.include_router(chat.router)
app.include_router(dashboard.router)


@app.get("/")
async def root():
    return {
        "service": "ShieldProxy",
        "version": "1.1.0",
        "mode": settings.APP_MODE.value,
        "status": "operational",
        "endpoints": {
            "auth_login": "POST /v1/auth/login",
            "auth_logout": "POST /v1/auth/logout",
            "auth_session": "GET /v1/auth/session",
            "chat": "POST /v1/chat",
            "stats": "GET /v1/dashboard/stats",
            "alerts": "GET /v1/dashboard/alerts",
            "clients": "GET /v1/dashboard/clients",
            "health_live": "GET /health/live",
            "health_ready": "GET /health/ready",
        },
    }


@app.get("/health/live")
async def health_live():
    return {"status": "alive", "service": "shieldproxy"}


@app.get("/health/ready")
async def health_ready():
    checks = {}
    is_ready = True

    try:
        if _redis is not None:
            redis_alive = await _redis.ping()
            checks["redis"] = "healthy" if redis_alive else "unresponsive"
        else:
            checks["redis"] = "healthy (in-memory)"
    except Exception as e:
        checks["redis"] = f"unreachable: {str(e)}"
        if settings.APP_MODE == AppMode.PROTECTED and settings.REDIS_REQUIRED_IN_PROTECTED:
            is_ready = False

    checks["llm_mode"] = "mock" if settings.USE_MOCK_LLM else "remote"
    checks["auth"] = "enforced"
    checks["rate_limiter"] = "atomic_token_bucket"
    checks["body_limiter"] = f"max_{settings.MAX_BODY_SIZE_BYTES}_bytes"

    if not is_ready:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"status": "not_ready", "checks": checks},
        )

    return {"status": "ready", "checks": checks}


@app.get("/health")
async def health_legacy():
    return await health_ready()