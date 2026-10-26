import time
import uuid
import logging
from datetime import datetime

from fastapi import APIRouter, HTTPException, Depends
from models.schemas import ChatRequest, PipelineStage
from middleware.auth import TenantContext, get_current_tenant
from config import settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/v1", tags=["chat"])

# Injected by main.py on startup
rate_limiter = None
threat_classifier = None
pii_scrubber = None
audit_logger = None
llm_gateway = None
output_filter = None


def init_pipeline(rl, tc, ps, al, lg, of):
    global rate_limiter, threat_classifier, pii_scrubber
    global audit_logger, llm_gateway, output_filter
    rate_limiter = rl
    threat_classifier = tc
    pii_scrubber = ps
    audit_logger = al
    llm_gateway = lg
    output_filter = of


def _ensure_pipeline_initialized():
    global rate_limiter, threat_classifier, pii_scrubber
    global audit_logger, llm_gateway, output_filter
    if rate_limiter is None:
        from utils.redis_client import MockRedis
        from middleware.rate_limiter import RateLimiter
        from middleware.threat_classifier import ThreatClassifier
        from middleware.pii_scrubber import PIIScrubber
        from middleware.audit_logger import AuditLogger
        from middleware.llm_gateway import LLMGateway
        from middleware.output_filter import OutputFilter

        mock_redis = MockRedis()
        rate_limiter = RateLimiter(mock_redis, rpm=settings.RATE_LIMIT_RPM)
        threat_classifier = ThreatClassifier(use_mock=settings.USE_MOCK_LLM)
        pii_scrubber = PIIScrubber()
        audit_logger = AuditLogger(mock_redis)
        llm_gateway = LLMGateway(use_mock=settings.USE_MOCK_LLM)
        output_filter = OutputFilter()


@router.post("/chat")
async def chat(
    req: ChatRequest,
    tenant: TenantContext = Depends(get_current_tenant),
):
    _ensure_pipeline_initialized()

    request_id = uuid.uuid4().hex[:16]
    total_start = time.time()
    stages = []
    tenant_id = tenant.tenant_id

    # ── Stage 1: Rate Limiter (Atomic, Tenant-Bound) ──
    stage_start = time.time()
    rl_result = await rate_limiter.check(tenant_id, custom_rpm=tenant.rate_limit_rpm)
    rl_latency = round((time.time() - stage_start) * 1000, 1)

    stages.append(PipelineStage(
        stage="rate_limiter",
        passed=rl_result["allowed"],
        latency_ms=int(rl_latency),
    ))

    if not rl_result["allowed"]:
        total_ms = round((time.time() - total_start) * 1000)
        status_code = rl_result.get("status_code", 429)

        # Zero raw prompt logged
        await audit_logger.log({
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "tenant_id": tenant_id,
            "request_id": request_id,
            "threat_type": rl_result.get("reason", "RATE_LIMIT"),
            "is_blocked": True,
            "confidence": 1.0,
            "pii_count": 0,
            "latency_ms": total_ms,
            "prompt_preview": "[RATE_LIMIT_EXCEEDED]",
        })

        raise HTTPException(
            status_code=status_code,
            detail={
                "request_id": request_id,
                "tenant_id": tenant_id,
                "blocked": True,
                "block_reason": rl_result.get("reason", "RATE_LIMIT_EXCEEDED"),
                "message": rl_result.get("message", "Too many requests. Please slow down."),
                "retry_after": rl_result.get("retry_after", 60),
                "threat_analysis": {
                    "threat_type": rl_result.get("reason", "RATE_LIMIT"),
                    "confidence": 1.0,
                    "matched_patterns": [],
                },
                "pii_scrubbed": False,
                "pii_count": 0,
                "response": None,
                "output_filtered": False,
                "total_latency_ms": total_ms,
                "pipeline_stages": [s.model_dump() for s in stages],
            },
        )

    # ── Stage 2: Threat Classifier (Asynchronous Non-Blocking) ──
    stage_start = time.time()
    tc_result = await threat_classifier.classify(req.message)
    tc_latency = round((time.time() - stage_start) * 1000, 1)

    stages.append(PipelineStage(
        stage="threat_classifier",
        passed=not tc_result["is_threat"],
        latency_ms=int(max(tc_latency, tc_result.get("inference_time_ms", 0))),
        threat_type=tc_result["threat_type"],
    ))

    if tc_result["is_threat"]:
        stage_start = time.time()
        pii_result = pii_scrubber.scrub(req.message)
        pii_latency = round((time.time() - stage_start) * 1000, 1)
        stages.append(PipelineStage(
            stage="pii_scrubber",
            passed=True,
            latency_ms=int(pii_latency),
            pii_count=pii_result["pii_count"],
        ))

        total_ms = round((time.time() - total_start) * 1000)

        # Zero raw prompt logged: Pass scrubbed text only
        await audit_logger.log({
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "tenant_id": tenant_id,
            "request_id": request_id,
            "threat_type": tc_result["threat_type"],
            "is_blocked": True,
            "confidence": tc_result["confidence"],
            "pii_count": pii_result["pii_count"],
            "latency_ms": total_ms,
            "prompt_scrubbed": pii_result["scrubbed_text"],
        })

        stages.append(PipelineStage(stage="audit_logger", passed=True, latency_ms=1))
        stages.append(PipelineStage(stage="llm_gateway", passed=False, latency_ms=0))
        stages.append(PipelineStage(stage="output_filter", passed=False, latency_ms=0))

        raise HTTPException(
            status_code=403,
            detail={
                "request_id": request_id,
                "tenant_id": tenant_id,
                "blocked": True,
                "block_reason": tc_result["threat_type"],
                "threat_analysis": {
                    "threat_type": tc_result["threat_type"],
                    "confidence": tc_result["confidence"],
                    "matched_patterns": tc_result["matched_patterns"],
                },
                "pii_scrubbed": pii_result["pii_count"] > 0,
                "pii_count": pii_result["pii_count"],
                "response": None,
                "output_filtered": False,
                "total_latency_ms": total_ms,
                "pipeline_stages": [s.model_dump() for s in stages],
            },
        )

    # ── Stage 3: PII Scrubber ──
    stage_start = time.time()
    pii_result = pii_scrubber.scrub(req.message)
    pii_latency = round((time.time() - stage_start) * 1000, 1)
    stages.append(PipelineStage(
        stage="pii_scrubber",
        passed=True,
        latency_ms=int(max(pii_latency, pii_result.get("latency_ms", 0))),
        pii_count=pii_result["pii_count"],
    ))

    # ── Stage 4: LLM Gateway (Asynchronous Execution) ──
    stage_start = time.time()
    clean_prompt = pii_result["scrubbed_text"]
    llm_result = await llm_gateway.complete(clean_prompt, tenant_id=tenant_id)
    llm_latency = round((time.time() - stage_start) * 1000, 1)
    stages.append(PipelineStage(
        stage="llm_gateway",
        passed=True,
        latency_ms=int(max(llm_latency, llm_result.get("latency_ms", 0))),
    ))

    # ── Stage 5: Output Filter ──
    stage_start = time.time()
    of_result = output_filter.filter(llm_result["response"], req.message)
    of_latency = round((time.time() - stage_start) * 1000, 1)
    stages.append(PipelineStage(
        stage="output_filter",
        passed=True,
        latency_ms=int(max(of_latency, of_result.get("latency_ms", 0))),
    ))

    total_ms = round((time.time() - total_start) * 1000)

    # ── Stage 6: Audit Logger (Post-Completion with Authentic Total Latency) ──
    stage_start = time.time()
    await audit_logger.log({
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "tenant_id": tenant_id,
        "request_id": request_id,
        "threat_type": "SAFE",
        "is_blocked": False,
        "confidence": tc_result["confidence"],
        "pii_count": pii_result["pii_count"],
        "latency_ms": max(total_ms, 1),
        "prompt_scrubbed": pii_result["scrubbed_text"],
    })
    al_latency = round((time.time() - stage_start) * 1000, 1)
    stages.append(PipelineStage(stage="audit_logger", passed=True, latency_ms=int(max(al_latency, 1))))

    return {
        "request_id": request_id,
        "tenant_id": tenant_id,
        "blocked": False,
        "block_reason": None,
        "threat_analysis": {
            "threat_type": tc_result["threat_type"],
            "confidence": tc_result["confidence"],
            "matched_patterns": tc_result["matched_patterns"],
        },
        "pii_scrubbed": pii_result["pii_count"] > 0,
        "pii_count": pii_result["pii_count"],
        "response": of_result["filtered_text"],
        "output_filtered": of_result["leaked"],
        "total_latency_ms": total_ms,
        "pipeline_stages": [s.model_dump() for s in stages],
    }