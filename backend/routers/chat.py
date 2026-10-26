import time
import uuid
import logging
from datetime import datetime

from fastapi import APIRouter, HTTPException
from models.schemas import ChatRequest, ChatResponse, PipelineStage, ThreatAnalysis

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/v1", tags=["chat"])

# These get injected by main.py on startup
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


@router.post("/chat")
async def chat(req: ChatRequest):
    request_id = uuid.uuid4().hex[:16]
    total_start = time.time()
    stages = []
    client_id = req.client_id or "anonymous"

    # ── Stage 1: Rate Limiter ──
    stage_start = time.time()
    rl_result = await rate_limiter.check(client_id)
    rl_latency = round((time.time() - stage_start) * 1000, 1)

    stages.append(PipelineStage(
        stage="rate_limiter",
        passed=rl_result["allowed"],
        latency_ms=int(rl_latency),
    ))

    if not rl_result["allowed"]:
        total_ms = round((time.time() - total_start) * 1000)
        await audit_logger.log({
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "client_id": client_id,
            "request_id": request_id,
            "threat_type": "RATE_LIMIT",
            "is_blocked": True,
            "confidence": 1.0,
            "pii_count": 0,
            "latency_ms": total_ms,
            "prompt": req.message,
        })
        raise HTTPException(
            status_code=429,
            detail={
                "request_id": request_id,
                "blocked": True,
                "block_reason": "RATE_LIMIT_EXCEEDED",
                "threat_analysis": {"threat_type": "RATE_LIMIT", "confidence": 1.0, "matched_patterns": []},
                "pii_scrubbed": False,
                "pii_count": 0,
                "response": None,
                "output_filtered": False,
                "total_latency_ms": total_ms,
                "pipeline_stages": [s.model_dump() for s in stages],
            },
        )

    # ── Stage 2: Threat Classifier ──
    stage_start = time.time()
    tc_result = threat_classifier.classify(req.message)
    tc_latency = round((time.time() - stage_start) * 1000, 1)

    stages.append(PipelineStage(
        stage="threat_classifier",
        passed=not tc_result["is_threat"],
        latency_ms=int(max(tc_latency, tc_result.get("inference_time_ms", 0))),
        threat_type=tc_result["threat_type"],
    ))

    if tc_result["is_threat"]:
        # ── Still scrub PII for logging ──
        stage_start = time.time()
        pii_result = pii_scrubber.scrub(req.message)
        pii_latency = round((time.time() - stage_start) * 1000, 1)
        stages.append(PipelineStage(
            stage="pii_scrubber", passed=True,
            latency_ms=int(pii_latency), pii_count=pii_result["pii_count"],
        ))

        # Log the blocked request
        stage_start = time.time()
        total_ms = round((time.time() - total_start) * 1000)
        await audit_logger.log({
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "client_id": client_id,
            "request_id": request_id,
            "threat_type": tc_result["threat_type"],
            "is_blocked": True,
            "confidence": tc_result["confidence"],
            "pii_count": pii_result["pii_count"],
            "latency_ms": total_ms,
            "prompt": req.message,
        })
        al_latency = round((time.time() - stage_start) * 1000, 1)
        stages.append(PipelineStage(stage="audit_logger", passed=True, latency_ms=int(al_latency)))

        # Skip LLM and output filter
        stages.append(PipelineStage(stage="llm_gateway", passed=False, latency_ms=0))
        stages.append(PipelineStage(stage="output_filter", passed=False, latency_ms=0))

        total_ms = round((time.time() - total_start) * 1000)
        raise HTTPException(
            status_code=403,
            detail={
                "request_id": request_id,
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
        stage="pii_scrubber", passed=True,
        latency_ms=int(max(pii_latency, pii_result.get("latency_ms", 0))),
        pii_count=pii_result["pii_count"],
    ))

    # ── Stage 4: Audit Logger ──
    stage_start = time.time()
    await audit_logger.log({
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "client_id": client_id,
        "request_id": request_id,
        "threat_type": "SAFE",
        "is_blocked": False,
        "confidence": tc_result["confidence"],
        "pii_count": pii_result["pii_count"],
        "latency_ms": 0,  # will update later
        "prompt": req.message,
    })
    al_latency = round((time.time() - stage_start) * 1000, 1)
    stages.append(PipelineStage(stage="audit_logger", passed=True, latency_ms=int(al_latency)))

    # ── Stage 5: LLM Gateway ──
    stage_start = time.time()
    clean_prompt = pii_result["scrubbed_text"]
    llm_result = await llm_gateway.complete(clean_prompt, client_id)
    llm_latency = round((time.time() - stage_start) * 1000, 1)
    stages.append(PipelineStage(
        stage="llm_gateway", passed=True,
        latency_ms=int(max(llm_latency, llm_result.get("latency_ms", 0))),
    ))

    # ── Stage 6: Output Filter ──
    stage_start = time.time()
    of_result = output_filter.filter(llm_result["response"], req.message)
    of_latency = round((time.time() - stage_start) * 1000, 1)
    stages.append(PipelineStage(
        stage="output_filter", passed=True,
        latency_ms=int(max(of_latency, of_result.get("latency_ms", 0))),
    ))

    total_ms = round((time.time() - total_start) * 1000)

    return {
        "request_id": request_id,
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
