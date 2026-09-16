from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


DraftRevisionPlanStatus = Literal[
    "WAITING_CONFIRMATION",
    "PENDING",
    "READY",
    "FAILED",
    "PROVIDER_NOT_CONFIGURED",
    "CANCELLED",
    "APPLIED",
]
RevisionPlanAction = Literal[
    "REWRITE",
    "SHORTEN",
    "EXPAND",
    "REMOVE",
    "SOFTEN",
    "STRENGTHEN",
    "ALIGN_EVIDENCE",
    "FIX_RISK",
    "PRESERVE",
]
RevisionPlanTarget = Literal[
    "TITLE",
    "INTRO",
    "BODY",
    "CTA",
    "TAGS",
    "TONE",
    "FACTUAL_CLAIM",
    "WHOLE_DRAFT",
]
RevisionPlanPriority = Literal["LOW", "MEDIUM", "HIGH"]


class DraftRevisionPlanRequest(BaseModel):
    """Controlled B10 request for planning revisions without changing a draft."""

    account_id: int = Field(gt=0)
    confirmed: bool = False
    review_report_id: int | None = Field(default=None, gt=0)
    conversation_id: int | None = Field(default=None, gt=0)
    feedback_text: str = Field(default="", max_length=2000)
    feedback_scope: list[RevisionPlanTarget] = Field(default_factory=list)


class RevisionOperation(BaseModel):
    """One allowed operation in a structured revision plan."""

    order: int = Field(ge=1)
    target: RevisionPlanTarget
    action: RevisionPlanAction
    reason: str = Field(min_length=1)
    instruction: str = Field(min_length=1)
    priority: RevisionPlanPriority = "MEDIUM"


class RevisionPlanLLMResult(BaseModel):
    """Structured LLM output for B10 revision planning."""

    summary: str = Field(min_length=1)
    operations: list[RevisionOperation] = Field(default_factory=list)
    preserve: list[str] = Field(default_factory=list)
    must_not_change: list[str] = Field(default_factory=list)
    risk_fixes: list[str] = Field(default_factory=list)
    ready_for_revision: bool = True


class DraftRevisionPlanCreate(BaseModel):
    """Data required to persist a B10 revision plan."""

    account_id: int
    draft_id: int
    review_report_id: int | None = None
    conversation_id: int | None = None
    feedback_text: str
    feedback_scope: list[str] = Field(default_factory=list)
    status: str = "READY"
    plan: dict[str, Any] = Field(default_factory=dict)
    summary: str | None = None
    risk_flags: list[str] = Field(default_factory=list)
    base_draft_updated_at: datetime | None = None


class DraftRevisionPlanRecord(BaseModel):
    """Persisted B10 revision plan record."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    account_id: int
    draft_id: int
    review_report_id: int | None = None
    conversation_id: int | None = None
    feedback_text: str
    feedback_scope: list[str]
    status: str
    plan: dict[str, Any]
    summary: str | None = None
    risk_flags: list[str]
    base_draft_updated_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class DraftRevisionPlanResponse(BaseModel):
    """Controlled B10 API response."""

    status: DraftRevisionPlanStatus
    account_id: int
    draft_id: int
    plan_id: int | None = None
    review_report_id: int | None = None
    conversation_id: int | None = None
    feedback_scope: list[str] = Field(default_factory=list)
    summary: str = ""
    operations: list[RevisionOperation] = Field(default_factory=list)
    preserve: list[str] = Field(default_factory=list)
    must_not_change: list[str] = Field(default_factory=list)
    risk_fixes: list[str] = Field(default_factory=list)
    ready_for_revision: bool = False
    base_draft_updated_at: datetime | None = None
    confirmation: dict[str, Any] = Field(default_factory=dict)
    error_code: str | None = None
    error_message: str | None = None
