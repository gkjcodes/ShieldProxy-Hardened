import sys
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import RATE_LIMIT_RPM, USE_MOCK_LLM
from utils.redis_client import get_redis
from middleware.rate_limiter import RateLimiter
from middleware.threat_classifier import ThreatClassifier
from middleware.pii_scrubber import PIIScrubber
from middleware.audit_logger import AuditLogger
from middleware.output_filter import OutputFilter
from middleware.llm_gateway import LLMGateway
from routers import chat, dashboard

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
)
logger = logging.getLogger("shieldproxy")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── Startup ──
    logger.info("🛡️  ShieldProxy Backend Starting...")
    logger.info("   Mock LLM: %s | Rate Limit: %d RPM", USE_MOCK_LLM, RATE_LIMIT_RPM)

    redis = await get_redis()

    rl = RateLimiter(redis, rpm=RATE_LIMIT_RPM)
    tc = ThreatClassifier()
    ps = PIIScrubber()
    al = AuditLogger(redis)
    of = OutputFilter()
    lg = LLMGateway(use_mock=USE_MOCK_LLM)

    chat.init_pipeline(rl, tc, ps, al, lg, of)
    dashboard.init_dashboard(al)

    logger.info("✅ All middleware initialized")
    logger.info("🚀 ShieldProxy is LIVE on http://localhost:8000")
    logger.info("📊 Dashboard API: http://localhost:8000/v1/dashboard/stats")
    logger.info("🔬 Chat API: POST http://localhost:8000/v1/chat")

    yield

    # ── Shutdown ──
    logger.info("🛑 ShieldProxy shutting down...")


app = FastAPI(
    title="ShieldProxy",
    description="LLM Prompt Injection Firewall — Protects LLMs from prompt injection, PII leakage, and jailbreaking in real-time.",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount routers
app.include_router(chat.router)
app.include_router(dashboard.router)


@app.get("/")
async def root():
    return {
        "service": "ShieldProxy",
        "version": "1.0.0",
        "status": "operational",
        "endpoints": {
            "chat": "POST /v1/chat",
            "stats": "GET /v1/dashboard/stats",
            "alerts": "GET /v1/dashboard/alerts",
            "clients": "GET /v1/dashboard/clients",
            "volume": "GET /v1/dashboard/volume?hours=24",
        },
    }


@app.get("/health")
async def health():
    return {"status": "healthy", "service": "shieldproxy"}
