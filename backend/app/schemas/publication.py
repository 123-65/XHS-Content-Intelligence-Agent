from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.content_strategy import EvidenceRef


class StrictPublicationModel(BaseModel):
    """禁止额外字段的发布闭环基础合同。"""

    model_config = ConfigDict(extra="forbid")


class PublishPackageInput(StrictPublicationModel):
    """从最终 Draft Version 生成人工发布包的输入。"""

    account_id: int = Field(gt=0)
    draft_version_id: int = Field(gt=0)
    optional_publish_notes: str | None = None


class PublishPackageResult(StrictPublicationModel):
    """供用户人工发布的内容交付物。"""

    package_ref: int
    draft_id: int
    draft_version_id: int
    version_number: int
    title: str
    body: str
    suggested_tags: list[str]
    optional_publish_notes: str | None
    generated_at: datetime | None = None


class PublishedNoteBindingInput(StrictPublicationModel):
    """将人工发布结果绑定到 Draft Version 的输入。"""

    account_id: int = Field(gt=0)
    publish_package_ref: int = Field(gt=0)
    publish_url: str = Field(min_length=1)
    published_at: datetime


class PublishedNoteResult(StrictPublicationModel):
    """真实平台已发布笔记的绑定结果。"""

    published_note_ref: int
    draft_id: int
    draft_version_id: int
    version_number: int
    publish_url: str
    platform_note_id: str | None
    published_at: datetime
    bound_at: datetime | None
    account_ref: int


class MetricWindow(StrictPublicationModel):
    """指标快照对应的真实时间窗口。"""

    label: str = Field(min_length=1, max_length=16)
    window_start: datetime
    window_end: datetime

    @model_validator(mode="after")
    def validate_window(self):
        """校验时间窗口的结束时间不早于开始时间。"""
        if self.window_end <= self.window_start:
            raise ValueError("window_end must be later than window_start")
        return self


class PublicMetricSnapshotResult(StrictPublicationModel):
    """由正式 XHS Provider 测得的公开指标快照。"""

    snapshot_ref: int
    published_note_ref: int
    observed_at: datetime | None
    window: MetricWindow
    metrics: dict[str, int]
    provenance: Literal["MEASURED"] = "MEASURED"
    source: str


class PrivateMetricsInput(StrictPublicationModel):
    """用户明确归因给某篇已发布笔记的私域指标。"""

    account_id: int = Field(gt=0)
    published_note_ref: int = Field(gt=0)
    window: MetricWindow
    dm_count: int | None = Field(default=None, ge=0)
    wechat_add_count: int | None = Field(default=None, ge=0)
    consultation_count: int | None = Field(default=None, ge=0)
    deal_count: int | None = Field(default=None, ge=0)
    revenue: Decimal | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def require_user_provided_metric(self):
        """禁止创建一条完全没有用户输入的私域快照。"""
        fields = (self.dm_count, self.wechat_add_count, self.consultation_count, self.deal_count, self.revenue)
        if all(value is None for value in fields):
            raise ValueError("at least one private metric must be user-provided")
        return self


class PrivateMetricsWriteRequest(StrictPublicationModel):
    """正式 HTTP 表单使用的扁平私域指标写入合同。"""

    account_id: int = Field(gt=0)
    label: str = Field(min_length=1, max_length=16)
    window_start: datetime
    window_end: datetime
    dm_count: int | None = Field(default=None, ge=0)
    wechat_add_count: int | None = Field(default=None, ge=0)
    consultation_count: int | None = Field(default=None, ge=0)
    deal_count: int | None = Field(default=None, ge=0)
    revenue: Decimal | None = Field(default=None, ge=0)

    def to_service_input(self, published_note_ref: int) -> PrivateMetricsInput:
        """将路径中的 PublishedNote identity 合并为现有服务合同。"""
        return PrivateMetricsInput(
            account_id=self.account_id, published_note_ref=published_note_ref,
            window=MetricWindow(label=self.label, window_start=self.window_start, window_end=self.window_end),
            dm_count=self.dm_count, wechat_add_count=self.wechat_add_count,
            consultation_count=self.consultation_count, deal_count=self.deal_count,
            revenue=self.revenue,
        )


class PrivateMetricSnapshotResult(StrictPublicationModel):
    """保留 UNKNOWN 语义的私域指标快照。"""

    snapshot_ref: int
    published_note_ref: int
    observed_at: datetime | None
    window: MetricWindow
    metrics: dict[str, int | Decimal | None]
    provenance: Literal["USER_ATTRIBUTED"] = "USER_ATTRIBUTED"


class StrategyCandidate(StrictPublicationModel):
    """发布后复盘生成、但尚未成为长期事实的策略候选。"""

    candidate_index: int = Field(ge=0)
    statement: str = Field(min_length=1)
    scope: str = Field(min_length=1)
    supporting_refs: list[EvidenceRef] = Field(default_factory=list)
    contradicting_refs: list[EvidenceRef] = Field(default_factory=list)
    confidence_context: str
    created_from_review: int | None = None
    status: Literal["PROPOSED", "CONFIRMED", "REJECTED"] = "PROPOSED"


class PostPublishReviewInput(StrictPublicationModel):
    """发布后复盘的输入引用。"""

    account_id: int = Field(gt=0)
    published_note_ref: int = Field(gt=0)
    strategy_ref: str
    opportunity_ref: int = Field(gt=0)


class PostPublishReviewLLMResult(StrictPublicationModel):
    """LLM 产生的观察、解释和策略候选。"""

    observed_results: list[str]
    public_performance_analysis: str
    optional_conversion_analysis: str | None = None
    strategy_alignment: str
    what_worked: list[str]
    what_did_not_work: list[str]
    uncertainties: list[str]
    evidence_refs: list[EvidenceRef]
    strategy_candidates: list[StrategyCandidate]


class PostPublishReviewResult(PostPublishReviewLLMResult):
    """已持久化的发布后复盘结果。"""

    review_ref: int


class ConfirmStrategyCandidateInput(StrictPublicationModel):
    """显式确认某条 Strategy Candidate 的命令输入。"""

    account_id: int = Field(gt=0)
    review_ref: int = Field(gt=0)
    candidate_index: int = Field(ge=0)
    confirmed: bool


class StrategyMemoryResult(StrictPublicationModel):
    """用户确认后创建的长期策略记忆。"""

    status: Literal["WAITING_CONFIRMATION", "SAVED"]
    memory_ref: int | None = None
