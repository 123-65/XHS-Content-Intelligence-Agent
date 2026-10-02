from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.content_strategy import ContentOpportunityResult, EvidenceRef


class StrictDraftModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class DraftContent(StrictDraftModel):
    title: str = Field(min_length=1)
    body: str = Field(min_length=1)
    tags: list[str] = Field(default_factory=list)
    cta: str | None = None


class DraftPersistenceMetadata(StrictDraftModel):
    """表达 Draft 持久化可选的显式生成元数据，不要求完整 LLM 响应对象。"""

    prompt_tokens: int = Field(default=0, ge=0)
    completion_tokens: int = Field(default=0, ge=0)
    total_tokens: int = Field(default=0, ge=0)
    estimated_cost: Decimal = Field(default=Decimal("0"), ge=0)
    raw_response_id: str | None = None


class DraftGenerationInput(StrictDraftModel):
    account_id: int = Field(gt=0)
    strategy_ref: str = Field(min_length=1)
    opportunity: ContentOpportunityResult
    research_artifact_ref: EvidenceRef
    evidence_refs: list[EvidenceRef] = Field(default_factory=list)
    user_constraints: list[str] = Field(default_factory=list)
    optional_previous_context: dict[str, Any] | None = None


class GeneratedDraft(StrictDraftModel):
    draft_ref: int
    version: int
    title: str
    body: str
    tags: list[str]
    cta: str | None = None
    content_goal: str
    opportunity_ref: int
    strategy_ref: str
    evidence_refs: list[EvidenceRef]
    generation_metadata: dict[str, Any]


class DraftReviewInput(StrictDraftModel):
    draft_ref: int = Field(gt=0)
    account_id: int = Field(gt=0)
    strategy_ref: str = Field(min_length=1)
    opportunity_ref: int = Field(gt=0)
    evidence_refs: list[EvidenceRef] = Field(default_factory=list)
    user_style_constraints: list[str] = Field(default_factory=list)


class DraftReviewIssue(StrictDraftModel):
    category: str
    severity: Literal["LOW", "MEDIUM", "HIGH"]
    location: str
    explanation: str
    suggestion: str


class DraftReviewLLMResult(StrictDraftModel):
    overall_status: Literal["PASS", "REVISE", "BLOCK"]
    issues: list[DraftReviewIssue] = Field(default_factory=list)
    strategy_alignment: str
    evidence_grounding: str
    cited_evidence_refs: list[EvidenceRef] = Field(default_factory=list)
    style_consistency: str
    risk_findings: list[str] = Field(default_factory=list)
    revision_required: bool
    summary: str


class DraftReviewResult(DraftReviewLLMResult):
    review_result_ref: int
    draft_ref: int


class DraftRevisionInput(StrictDraftModel):
    source_draft_ref: int = Field(gt=0)
    account_id: int = Field(gt=0)
    revision_source: Literal["USER_FEEDBACK", "REVIEW_RESULT"]
    user_instruction: str | None = Field(default=None, max_length=2000)
    review_result_ref: int | None = Field(default=None, gt=0)
    preserved_constraints: list[str] = Field(default_factory=list)
    context_refs: list[EvidenceRef] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_revision_basis(self):
        if self.revision_source == "USER_FEEDBACK" and not (self.user_instruction or "").strip():
            raise ValueError("USER_FEEDBACK revision requires user_instruction")
        if self.revision_source == "REVIEW_RESULT" and self.review_result_ref is None:
            raise ValueError("REVIEW_RESULT revision requires review_result_ref")
        return self


class DraftRevisionLLMResult(DraftContent):
    applied_changes: list[str] = Field(min_length=1)


class RevisedDraft(StrictDraftModel):
    draft_ref: int
    parent_draft_ref: int
    version: int
    title: str
    body: str
    tags: list[str]
    cta: str | None = None
    applied_changes: list[str]
    preserved_constraints: list[str]
    evidence_refs: list[EvidenceRef]
    opportunity_ref: int
    strategy_ref: str
