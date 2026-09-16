from typing import Any, Literal

from pydantic import BaseModel, Field


DraftRevisionApplyStatus = Literal[
    "WAITING_CONFIRMATION",
    "CREATED",
    "STALE_PLAN",
    "PROVIDER_NOT_CONFIGURED",
    "FAILED",
    "BLOCKED",
]
DraftRevisionSaveAs = Literal["NEW_DRAFT"]


class DraftRevisionApplyRequest(BaseModel):
    """Controlled B11 request for applying an existing revision plan."""

    account_id: int = Field(gt=0)
    confirmed: bool = False
    user_extra_requirements: str | None = Field(default=None, max_length=1000)
    save_as: DraftRevisionSaveAs = "NEW_DRAFT"
    source_draft_id: int | None = Field(default=None, gt=0)


class AppliedRevisionOperation(BaseModel):
    """One operation applied by the revision LLM."""

    operation_order: int = Field(ge=1)
    target: str
    action: str
    result: str = Field(min_length=1)


class DraftRevisionApplyLLMResult(BaseModel):
    """Structured LLM output for B11 apply."""

    title: str = Field(min_length=1)
    content: str = Field(min_length=1)
    tags: list[str] = Field(default_factory=list)
    cta: str | None = None
    change_summary: str = Field(min_length=1)
    applied_operations: list[AppliedRevisionOperation] = Field(default_factory=list)


class DraftRevisionApplyDraft(BaseModel):
    """Small revised draft payload returned to Agent Workbench."""

    title: str
    content: str
    tags: list[str] = Field(default_factory=list)
    cta: str | None = None


class DraftRevisionApplyResponse(BaseModel):
    """Controlled B11 API response."""

    status: DraftRevisionApplyStatus
    account_id: int
    revision_plan_id: int
    source_draft_id: int | None = None
    revised_draft_id: int | None = None
    review_report_id: int | None = None
    summary: str = ""
    applied_operations: list[AppliedRevisionOperation] = Field(default_factory=list)
    draft: DraftRevisionApplyDraft | None = None
    warnings: list[str] = Field(default_factory=list)
    confirmation: dict[str, Any] = Field(default_factory=dict)
    error_code: str | None = None
    error_message: str | None = None
