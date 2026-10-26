from pydantic import BaseModel, Field
from typing import Optional, List
import uuid


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000)
    client_id: str = Field(default="anonymous")


class PipelineStage(BaseModel):
    stage: str
    passed: bool
    latency_ms: int
    threat_type: Optional[str] = None
    pii_count: Optional[int] = None


class ThreatAnalysis(BaseModel):
    threat_type: str
    confidence: float
    matched_patterns: List[str]


class ChatResponse(BaseModel):
    request_id: str = Field(default_factory=lambda: uuid.uuid4().hex[:16])
    blocked: bool
    block_reason: Optional[str] = None
    threat_analysis: ThreatAnalysis
    pii_scrubbed: bool
    pii_count: int
    response: Optional[str] = None
    output_filtered: bool = False
    total_latency_ms: int
    pipeline_stages: List[PipelineStage]


class DashboardStats(BaseModel):
    total_requests: int
    total_blocked: int
    total_passed: int
    block_rate: float
    threats_by_type: dict
    avg_latency_ms: float
    requests_last_hour: int


class AlertEntry(BaseModel):
    id: str
    timestamp: str
    client_id: str
    threat_type: str
    is_blocked: bool
    confidence: float
    pii_count: int
    latency_ms: int
    prompt_preview: str = ""


class ClientInfo(BaseModel):
    client_id: str
    api_key_masked: str
    total_requests: int
    total_blocked: int
    block_rate: float
    last_active: str
    status: str


class VolumeEntry(BaseModel):
    timestamp: str
    blocked: int
    passed: int
