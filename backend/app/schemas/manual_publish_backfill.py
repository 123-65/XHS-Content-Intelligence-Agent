from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


ManualPublishBackfillStatus = Literal["WAITING_CONFIRMATION", "RECORDED", "FAILED"]


class ManualPublishBackfillRequest(BaseModel):
    """Manual post-publish backfill payload from the user."""

    account_id: int = Field(gt=0)
    confirmed: bool = False
    platform: Literal["xhs"] = "xhs"
    note_url: str = Field(default="", max_length=1024)
    published_at: datetime | None = None
    title: str | None = Field(default=None, max_length=512)
    like_count: int = Field(default=0, ge=0)
    collect_count: int = Field(default=0, ge=0)
    comment_count: int = Field(default=0, ge=0)
    share_count: int = Field(default=0, ge=0)
    follower_gain: int = Field(default=0, ge=0)
    lead_count: int = Field(default=0, ge=0)
    remark: str | None = Field(default=None, max_length=2000)
    snapshot_window: str = Field(default="manual", max_length=16)


class ManualPublishMetrics(BaseModel):
    """Metrics recorded from manual user input."""

    like_count: int
    collect_count: int
    comment_count: int
    share_count: int
    follower_gain: int
    lead_count: int
    source_type: str = "MANUAL"


class ManualPublishNextAction(BaseModel):
    """Next action offered after manual backfill."""

    action: str
    label: str
    enabled: bool = True


class PublishedNoteBackfillResponse(BaseModel):
    """Published note view returned by B13 APIs."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    account_id: int
    experiment_id: int
    draft_id: int
    package_id: int | None = None
    publish_url: str
    platform: str
    status: str
    source_type: str
    published_at: datetime | None = None
    raw_snapshot: dict = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime


class ManualPublishBackfillResponse(BaseModel):
    """Response for B13 manual publish and metrics backfill."""

    status: ManualPublishBackfillStatus
    account_id: int
    package_id: int | None = None
    published_note_id: int | None = None
    metric_snapshot_id: int | None = None
    private_conversion_snapshot_id: int | None = None
    note_url: str = ""
    published_at: datetime | None = None
    metrics: ManualPublishMetrics | None = None
    warnings: list[str] = Field(default_factory=list)
    next_actions: list[ManualPublishNextAction] = Field(default_factory=list)
    confirmation: dict = Field(default_factory=dict)
    error_code: str | None = None
    error_message: str | None = None
