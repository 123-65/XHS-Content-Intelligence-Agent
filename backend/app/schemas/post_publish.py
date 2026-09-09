from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.enums.post_publish import MetricSnapshotWindow, OptimizationPlanType


class PublishedNoteCreate(BaseModel):
    """创建已发布笔记的请求体。"""

    account_id: int
    experiment_id: int
    draft_id: int
    publish_url: str
    platform: str = "xhs"
    published_at: datetime | None = None
    source_type: str = "MANUAL"
    raw_snapshot: dict = Field(default_factory=dict)


class PublishedNoteResponse(BaseModel):
    """已发布笔记的响应结构。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    account_id: int
    experiment_id: int
    draft_id: int
    publish_url: str
    platform: str
    status: str
    source_type: str
    published_at: datetime | None
    raw_snapshot: dict
    created_at: datetime
    updated_at: datetime


class PublicMetricSnapshotCreate(BaseModel):
    """公开指标快照的请求体。"""

    snapshot_window: MetricSnapshotWindow
    view_count: int = Field(default=0, ge=0)
    like_count: int = Field(default=0, ge=0)
    collect_count: int = Field(default=0, ge=0)
    comment_count: int = Field(default=0, ge=0)
    share_count: int = Field(default=0, ge=0)
    follow_count: int = Field(default=0, ge=0)
    profile_visit_count: int = Field(default=0, ge=0)
    source_type: str = "MANUAL"
    confidence: Decimal = Field(default=Decimal("1"), ge=0, le=1)
    raw_snapshot: dict = Field(default_factory=dict)


class CollectMetricsRequest(BaseModel):
    """手动或 Mock 回采公开指标的请求体。"""

    snapshot_window: MetricSnapshotWindow
    metrics: PublicMetricSnapshotCreate | None = None
    use_mock: bool = False


class PublicMetricSnapshotResponse(BaseModel):
    """公开指标快照的响应结构。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    published_note_id: int
    snapshot_window: str
    view_count: int
    like_count: int
    collect_count: int
    comment_count: int
    share_count: int
    follow_count: int
    profile_visit_count: int
    source_type: str
    collected_at: datetime
    confidence: Decimal
    raw_snapshot: dict


class PrivateConversionSnapshotCreate(BaseModel):
    """人工录入私域转化数据的请求体。"""

    account_id: int | None = None
    published_note_id: int
    snapshot_window: MetricSnapshotWindow | None = None
    dm_count: int = Field(default=0, ge=0)
    lead_count: int = Field(default=0, ge=0)
    wechat_add_count: int = Field(default=0, ge=0)
    group_join_count: int = Field(default=0, ge=0)
    consultation_count: int = Field(default=0, ge=0)
    price_inquiry_count: int = Field(default=0, ge=0)
    resource_request_count: int = Field(default=0, ge=0)
    deal_count: int = Field(default=0, ge=0)
    revenue_amount: Decimal = Field(default=Decimal("0"), ge=0)
    source_type: str = "MANUAL"
    confidence: Decimal = Field(default=Decimal("1"), ge=0, le=1)
    raw_snapshot: dict = Field(default_factory=dict)


class PrivateConversionSnapshotResponse(BaseModel):
    """私域转化快照的响应结构。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    account_id: int
    published_note_id: int
    snapshot_window: str | None
    dm_count: int
    lead_count: int
    wechat_add_count: int
    group_join_count: int
    consultation_count: int
    price_inquiry_count: int
    resource_request_count: int
    deal_count: int
    revenue_amount: Decimal
    source_type: str
    collected_at: datetime
    confidence: Decimal
    raw_snapshot: dict


class ReviewCreate(BaseModel):
    """发布后复盘的请求体。"""

    published_note_id: int


class ReviewReportV2Response(BaseModel):
    """发布后复盘报告的响应结构。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    draft_id: int
    account_id: int | None
    experiment_id: int | None
    published_note_id: int | None
    review_type: str
    result_status: str | None
    passed: bool
    score: int
    risk_level: str
    issues: list[dict]
    suggestions: list[str]
    public_metrics_summary: dict
    private_conversion_summary: dict
    comment_summary: dict
    data_facts: list[dict]
    inferences: list[dict]
    action_suggestions: list[dict]
    summary: str | None
    status: str
    created_at: datetime


class StrategyMemoryResponse(BaseModel):
    """策略记忆的响应结构。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    account_id: int
    memory_type: str
    status: str
    summary: str
    pattern: str | None
    confidence: Decimal
    source_review_report_id: int | None
    support_count: int
    evidence_count: int
    risk_level: str
    metadata_payload: dict
    created_at: datetime
    updated_at: datetime


class MemoryExtractionResponse(BaseModel):
    """策略记忆提取的响应结构。"""

    review_report_id: int
    count: int
    memories: list[StrategyMemoryResponse]


class OptimizationGenerateRequest(BaseModel):
    """生成内容优化计划的请求体。"""

    account_id: int
    review_report_id: int | None = None
    plan_type: OptimizationPlanType | None = None


class ContentOptimizationPlanResponse(BaseModel):
    """内容优化计划的响应结构。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    account_id: int
    source_review_report_id: int
    plan_type: str
    status: str
    summary: str
    rationale: str
    actions: list[dict]
    generated_experiment_id: int | None
    created_at: datetime
    applied_at: datetime | None
