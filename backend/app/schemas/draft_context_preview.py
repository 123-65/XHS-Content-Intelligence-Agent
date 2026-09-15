from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

DraftContextPreviewStatus = Literal["READY", "PARTIAL", "DATA_INSUFFICIENT", "BLOCKED", "FAILED"]


class DraftContextPreviewRequest(BaseModel):
    """Readonly request for previewing draft-generation context."""

    account_id: int = Field(gt=0)
    user_requirements: str | None = Field(default=None, max_length=1000)
    include_strategy_memory: bool = True
    include_comments: bool = True


class DraftContextPreviewResponse(BaseModel):
    """Structured draft context preview response."""

    model_config = ConfigDict(from_attributes=True)

    status: DraftContextPreviewStatus
    account_id: int
    experiment_id: int
    ready_for_draft_generation: bool
    requires_confirmation: bool = True
    context: dict[str, Any] = Field(default_factory=dict)
    missing_context: list[dict[str, Any]] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    confirmation: dict[str, Any] = Field(default_factory=dict)
    next_actions: list[dict[str, Any]] = Field(default_factory=list)
    error_code: str | None = None
    error_message: str | None = None
