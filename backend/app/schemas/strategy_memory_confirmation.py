from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


StrategyMemoryConfirmationStatus = Literal["WAITING_CONFIRMATION", "SAVED", "DATA_INSUFFICIENT", "BLOCKED", "VALIDATION_ERROR"]
StrategyMemoryType = Literal[
    "CONTENT_DIRECTION",
    "TITLE_STYLE",
    "CTA_STYLE",
    "AUDIENCE_PAIN_POINT",
    "FORMAT_PREFERENCE",
    "RISK_AVOIDANCE",
    "CONVERSION_SIGNAL",
    "DATA_GAP",
]
StrategyMemoryConfidence = Literal["LOW", "MEDIUM", "HIGH"]


class StrategyMemoryCandidateResponse(BaseModel):
    candidate_index: int
    memory_type: StrategyMemoryType
    content: str
    evidence: str
    confidence: StrategyMemoryConfidence
    selected: bool = False


class SelectedStrategyMemoryCandidate(BaseModel):
    candidate_index: int = Field(ge=0)
    memory_type: str = Field(max_length=64)
    content: str = Field(max_length=4000)
    evidence: str = Field(max_length=4000)
    confidence: str = Field(max_length=16)


class StrategyMemoryConfirmationRequest(BaseModel):
    account_id: int = Field(gt=0)
    confirmed: bool = False
    selected_candidates: list[SelectedStrategyMemoryCandidate] = Field(default_factory=list)
    conversation_id: int | None = Field(default=None, gt=0)


class StrategyMemoryAction(BaseModel):
    action: str
    label: str
    enabled: bool = True


class StrategyMemoryItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    account_id: int
    memory_type: str
    status: str
    summary: str
    pattern: str | None
    confidence: Decimal
    source_review_report_id: int | None
    support_count: int
    evidence_count: int
    risk_level: str
    metadata_payload: dict
    created_at: datetime
    updated_at: datetime


class StrategyMemoryConfirmationResponse(BaseModel):
    status: StrategyMemoryConfirmationStatus
    account_id: int
    review_id: int
    candidates: list[StrategyMemoryCandidateResponse] = Field(default_factory=list)
    created_memory_ids: list[int] = Field(default_factory=list)
    skipped_duplicates: list[dict] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    next_actions: list[StrategyMemoryAction] = Field(default_factory=list)
    error_code: str | None = None
    error_message: str | None = None
