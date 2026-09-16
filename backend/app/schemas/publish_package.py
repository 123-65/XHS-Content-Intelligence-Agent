from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


PublishPackageStatus = Literal["WAITING_CONFIRMATION", "READY", "NEEDS_REVIEW", "DATA_INSUFFICIENT", "FAILED"]


class PublishPackageRequest(BaseModel):
    """Request for generating a manual publish package from a draft."""

    account_id: int = Field(gt=0)
    confirmed: bool = False
    review_report_id: int | None = Field(default=None, gt=0)
    style: str = "clean_knowledge_card"
    card_count: int = Field(default=5, ge=2, le=6)


class PublishCard(BaseModel):
    """One frontend-renderable publish card."""

    order: int = Field(ge=1)
    card_type: str
    title: str
    subtitle: str | None = None
    items: list[str] = Field(default_factory=list)
    style: str | None = None


class PublishChecklistItem(BaseModel):
    """One manual publish checklist item."""

    item: str
    passed: bool
    level: Literal["REQUIRED", "RECOMMENDED"] = "REQUIRED"


class PublishPackageCreate(BaseModel):
    """Data needed to persist a publish package."""

    account_id: int
    draft_id: int
    review_report_id: int | None = None
    revision_plan_id: int | None = None
    source_type: str = "ORIGINAL_DRAFT"
    status: str = "READY"
    title: str
    body: str
    tags: list[str] = Field(default_factory=list)
    cta: str | None = None
    cover_card: dict = Field(default_factory=dict)
    image_cards: list[dict] = Field(default_factory=list)
    publish_checklist: list[dict] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    manual_publish_steps: list[str] = Field(default_factory=list)
    stats: dict = Field(default_factory=dict)


class PublishPackageResponse(BaseModel):
    """Publish package response for Agent Workbench."""

    model_config = ConfigDict(from_attributes=True)

    status: PublishPackageStatus
    package_id: int | None = None
    account_id: int
    draft_id: int
    review_report_id: int | None = None
    revision_plan_id: int | None = None
    source_type: str = "ORIGINAL_DRAFT"
    title: str = ""
    body: str = ""
    tags: list[str] = Field(default_factory=list)
    cta: str | None = None
    cover_card: PublishCard | None = None
    image_cards: list[PublishCard] = Field(default_factory=list)
    publish_checklist: list[PublishChecklistItem] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    manual_publish_steps: list[str] = Field(default_factory=list)
    stats: dict = Field(default_factory=dict)
    confirmation: dict = Field(default_factory=dict)
    error_code: str | None = None
    error_message: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
