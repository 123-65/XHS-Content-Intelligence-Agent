from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


PostPublishReviewStatus = Literal["WAITING_CONFIRMATION", "REVIEWED", "DATA_INSUFFICIENT", "FAILED"]


class PostPublishReviewV0Request(BaseModel):
    """Controlled post-publish review request based on manual snapshots."""

    account_id: int = Field(gt=0)
    confirmed: bool = False
    review_window: str = "MANUAL_SNAPSHOT"
    notes: str | None = Field(default=None, max_length=2000)


class PostPublishAction(BaseModel):
    """One suggested next action from factual review."""

    action: str
    label: str
    enabled: bool = True


class StrategyMemoryCandidate(BaseModel):
    """Candidate conclusion for B15; not persisted as StrategyMemory in B14."""

    type: str
    content: str
    evidence: str
    confidence: Literal["LOW", "MEDIUM", "HIGH"] = "LOW"


class PostPublishReviewV0Response(BaseModel):
    """B14 post-publish review response."""

    model_config = ConfigDict(from_attributes=True)

    status: PostPublishReviewStatus
    review_id: int | None = None
    account_id: int
    published_note_id: int
    package_id: int | None = None
    summary: str = ""
    metric_summary: dict = Field(default_factory=dict)
    target_comparison: dict = Field(default_factory=dict)
    conversion_summary: dict = Field(default_factory=dict)
    insights: list[str] = Field(default_factory=list)
    data_gaps: list[dict] = Field(default_factory=list)
    next_actions: list[PostPublishAction] = Field(default_factory=list)
    strategy_memory_candidates: list[StrategyMemoryCandidate] = Field(default_factory=list)
    confirmation: dict = Field(default_factory=dict)
    error_code: str | None = None
    error_message: str | None = None
    created_at: datetime | None = None
