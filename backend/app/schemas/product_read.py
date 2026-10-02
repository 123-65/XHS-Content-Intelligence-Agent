from datetime import datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class ReadModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class PageMeta(ReadModel):
    page_no: int
    page_size: int
    total: int
    pages: int


class ResearchSummary(ReadModel):
    ref: int
    name: str
    topic: str | None
    status: str
    created_at: datetime
    updated_at: datetime


class ResearchListPage(PageMeta):
    items: list[ResearchSummary]


class StrategySummary(ReadModel):
    ref: int
    research_ref: int
    goal: str
    audience: str
    created_at: datetime


class StrategyListPage(PageMeta):
    items: list[StrategySummary]


class DraftSummary(ReadModel):
    ref: int
    title: str
    version: int
    status: str
    updated_at: datetime


class DraftListPage(PageMeta):
    items: list[DraftSummary]


class PublicationSummary(ReadModel):
    ref: int
    draft_ref: int
    draft_version_ref: int | None
    version_number: int | None
    title: str
    status: str
    published_at: datetime | None


class PublicationListPage(PageMeta):
    items: list[PublicationSummary]


class ReviewSummary(ReadModel):
    ref: int
    published_note_ref: int
    status: str
    result_status: str | None
    created_at: datetime


class ReviewListPage(PageMeta):
    items: list[ReviewSummary]


class ResearchOpportunity(ReadModel):
    ref: int
    title: str
    angle: str
    target_audience: str | None
    evidence_summary: str
    score: int
    risk_level: str


class ResearchDetail(ReadModel):
    ref: int
    account_ref: int
    name: str
    topic: str | None
    summary: str | None
    status: str
    findings: dict[str, list[Any]]
    source_metadata: dict[str, Any]
    opportunities: list[ResearchOpportunity]
    warnings: list[str]
    limitations: list[str]
    created_at: datetime
    updated_at: datetime


class StrategyOpportunity(ReadModel):
    ref: int
    source_opportunity_ref: int
    topic: str
    angle: str
    target_audience: str | None
    content_goal: str
    why_now: str
    suggested_hook: str
    evidence_refs: list[dict[str, Any]]
    constraints: list[str]


class StrategyDetail(ReadModel):
    ref: int
    account_ref: int
    research_ref: int
    goal: str
    audience: str
    directions: list[dict[str, Any]]
    rationale: str
    evidence_refs: list[dict[str, Any]]
    constraints: list[str]
    opportunities: list[StrategyOpportunity]
    created_at: datetime


class DraftVersionMetadata(ReadModel):
    ref: int
    version: int
    parent_version_ref: int | None
    created_from: str | None
    created_at: datetime
    content: "DraftContentView"


class DraftContentView(ReadModel):
    title: str
    body: str
    tags: list[str]
    cta: str | None


class DraftReviewSummary(ReadModel):
    ref: int
    status: str
    passed: bool
    score: int
    risk_level: str
    summary: str | None
    created_at: datetime


class DraftDetail(ReadModel):
    ref: int
    account_ref: int
    strategy_ref: int | None
    opportunity_ref: int | None
    content_goal: str | None
    status: str
    latest_version_ref: int | None
    latest_version: int
    current_content: DraftContentView
    versions: list[DraftVersionMetadata]
    reviews: list[DraftReviewSummary]
    created_at: datetime
    updated_at: datetime


class MetricSnapshot(ReadModel):
    ref: int
    window: str | None
    values: dict[str, int | Decimal | None]
    source_type: str
    collected_at: datetime


class PostPublishReviewSummary(ReadModel):
    ref: int
    status: str
    result_status: str | None
    summary: str | None
    observed_facts: list[dict[str, Any]]
    inferences: list[dict[str, Any]]
    created_at: datetime


class StrategyCandidateSummary(ReadModel):
    ref: int
    statement: str
    scope: str
    supporting_refs: list[dict[str, Any]]
    contradicting_refs: list[dict[str, Any]]
    confidence_context: str | dict[str, Any]
    status: str


class PublicationDetail(ReadModel):
    ref: int
    account_ref: int
    publish_url: str
    platform: str
    status: str
    published_at: datetime | None
    draft_ref: int
    published_draft_version_ref: int | None
    published_draft_version: int | None
    published_content: DraftContentView | None
    public_metrics: list[MetricSnapshot]
    private_metrics_status: Literal["AVAILABLE", "UNKNOWN"]
    private_metrics: list[MetricSnapshot]
    post_publish_review: PostPublishReviewSummary | None
    strategy_candidates: list[StrategyCandidateSummary]
    created_at: datetime
