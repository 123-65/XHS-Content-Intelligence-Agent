from typing import Any, Literal

from pydantic import BaseModel, Field


DraftGenerationStatus = Literal[
    "WAITING_CONFIRMATION",
    "CREATED",
    "DATA_INSUFFICIENT",
    "PROVIDER_NOT_CONFIGURED",
    "BLOCKED",
    "FAILED",
]


class DraftGenerationRequest(BaseModel):
    """Controlled request for generating a draft after context confirmation."""

    account_id: int = Field(gt=0)
    confirmed: bool = False
    user_requirements: str | None = Field(default=None, max_length=1000)
    draft_type: str = "xhs_note"
    tone: str = "natural"
    model_profile: str = "default"


class DraftGenerationDraft(BaseModel):
    """Small draft payload returned to the Agent workbench."""

    title: str
    content: str
    tags: list[str] = Field(default_factory=list)
    cta: str | None = None


class DraftGenerationResponse(BaseModel):
    """Controlled response for B8 draft generation."""

    status: DraftGenerationStatus
    account_id: int
    experiment_id: int
    draft_id: int | None = None
    ready_for_generation: bool = False
    context_preview_status: str | None = None
    provider: str = "unknown"
    draft: DraftGenerationDraft | None = None
    warnings: list[str] = Field(default_factory=list)
    missing_context: list[dict[str, Any]] = Field(default_factory=list)
    confirmation: dict[str, Any] = Field(default_factory=dict)
    error_code: str | None = None
    error_message: str | None = None
