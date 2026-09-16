from typing import Any, Literal

from pydantic import BaseModel, Field


DraftReviewStatus = Literal["WAITING_CONFIRMATION", "REVIEWED", "PROVIDER_NOT_CONFIGURED", "FAILED", "BLOCKED"]
DraftReviewRiskLevel = Literal["LOW", "MEDIUM", "HIGH"]


class DraftReviewRequest(BaseModel):
    """Controlled request for reviewing a generated draft."""

    account_id: int = Field(gt=0)
    confirmed: bool = False
    review_mode: str = "standard"
    check_ai_tone: bool = True
    check_risk: bool = True
    check_evidence_consistency: bool = True


class DraftReviewIssue(BaseModel):
    """One issue found during draft review."""

    field: str = "draft"
    category: str
    level: DraftReviewRiskLevel
    message: str
    evidence: str | None = None


class DraftReviewLLMResult(BaseModel):
    """Structured LLM output for B9 draft review."""

    can_enter_publish_preparation: bool
    risk_level: DraftReviewRiskLevel
    score: int = Field(ge=0, le=100)
    issues: list[DraftReviewIssue] = Field(default_factory=list)
    suggestions: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    summary: str
    block_reasons: list[str] = Field(default_factory=list)
    must_fix_before_publish: list[str] = Field(default_factory=list)
    optional_improvements: list[str] = Field(default_factory=list)
    ai_tone_feedback: dict[str, Any] = Field(default_factory=dict)
    evidence_consistency: dict[str, Any] = Field(default_factory=dict)


class DraftReviewResponse(BaseModel):
    """Controlled B9 draft review response."""

    status: DraftReviewStatus
    account_id: int
    draft_id: int
    review_report_id: int | None = None
    can_enter_publish_preparation: bool = False
    risk_level: DraftReviewRiskLevel | None = None
    score: int = 0
    issues: list[DraftReviewIssue] = Field(default_factory=list)
    suggestions: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    summary: str = ""
    block_reasons: list[str] = Field(default_factory=list)
    must_fix_before_publish: list[str] = Field(default_factory=list)
    optional_improvements: list[str] = Field(default_factory=list)
    confirmation: dict[str, Any] = Field(default_factory=dict)
    error_code: str | None = None
    error_message: str | None = None
