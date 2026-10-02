from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.agent.schemas.evidence import EvidenceRef, EvidenceType
from app.agent.schemas.execution import ArtifactRef, ArtifactType
from app.schemas.content_strategy import ContentDirection, ContentOpportunityResult, EvidenceRef as StrategyEvidenceRef
from app.schemas.draft import DraftContent


class QueryContract(BaseModel):
    """禁止额外字段的只读 Tool 合同基类。"""

    model_config = ConfigDict(extra="forbid")


class GrowthContextSection(StrEnum):
    """允许读取的增长上下文章节白名单。"""

    ACCOUNT_PROFILE = "ACCOUNT_PROFILE"
    BUSINESS_PROFILE = "BUSINESS_PROFILE"
    CUSTOMER_MODEL = "CUSTOMER_MODEL"
    GROWTH_GOAL = "GROWTH_GOAL"
    STRATEGY_MEMORY = "STRATEGY_MEMORY"


class QueryGrowthContextInput(QueryContract):
    """读取指定账号确认上下文的输入。"""

    account_ref: int = Field(gt=0)
    requested_sections: list[GrowthContextSection] = Field(min_length=1)
    as_of: datetime | None = None


class GrowthContextResult(QueryContract):
    """缺失字段保持 None 的账号增长上下文。"""

    account: dict[str, Any] | None = None
    business_profile: dict[str, Any] | None = None
    customer_model: dict[str, Any] | None = None
    growth_goal: dict[str, Any] | None = None
    strategy_memory: list[dict[str, Any]] = Field(default_factory=list)
    missing_sections: list[GrowthContextSection] = Field(default_factory=list)
    context_version: str
    observed_at: datetime


class QueryArtifactInput(QueryContract):
    """按明确 ArtifactRef 和账号边界读取产物。"""

    account_ref: int = Field(gt=0)
    artifact_ref: ArtifactRef
    expected_type: ArtifactType | None = None
    draft_version_ref: int | None = Field(default=None, gt=0)

    @model_validator(mode="after")
    def validate_expected_type(self):
        """拒绝引用类型与期望类型不一致。"""
        if self.expected_type is not None and self.expected_type != self.artifact_ref.type:
            raise ValueError("Artifact type mismatch")
        if self.draft_version_ref is not None and self.artifact_ref.type != ArtifactType.DRAFT:
            raise ValueError("draft_version_ref 仅适用于 DRAFT Artifact")
        return self


class ArtifactResult(QueryContract):
    """不同物理模型统一后的只读 Artifact。"""

    artifact_ref: ArtifactRef
    artifact_type: ArtifactType
    version: str
    content: dict[str, Any]
    created_at: datetime | None = None
    lineage_refs: list[ArtifactRef] = Field(default_factory=list)


class ContentStrategyArtifactView(QueryContract):
    """CONTENT_STRATEGY 的完整只读视图。"""

    account_ref: int = Field(gt=0)
    research_artifact_ref: int = Field(gt=0)
    strategy_goal: str = Field(min_length=1)
    target_audience: str = Field(min_length=1)
    content_directions: list[ContentDirection]
    rationale: str = Field(min_length=1)
    evidence_refs: list[StrategyEvidenceRef]
    applicable_constraints: list[str] = Field(default_factory=list)
    generated_opportunity_refs: list[int] = Field(default_factory=list)


class ContentOpportunityArtifactView(QueryContract):
    """可用于 Draft Generation 的 Strategy Generated Opportunity 只读视图。"""

    account_ref: int = Field(gt=0)
    strategy_artifact_ref: int = Field(gt=0)
    research_artifact_ref: int = Field(gt=0)
    source_opportunity_ref: int = Field(gt=0)
    opportunity: ContentOpportunityResult
    retrievable_evidence_refs: list[EvidenceRef] = Field(default_factory=list)


class DraftArtifactView(QueryContract):
    """Draft Root 与当前正式 Version 的只读视图。"""

    account_ref: int = Field(gt=0)
    strategy_artifact_ref: int | None = Field(default=None, gt=0)
    opportunity_ref: int | None = Field(default=None, gt=0)
    content_goal: str | None = None
    latest_draft_version_ref: int | None = Field(default=None, gt=0)
    latest_version: int | None = Field(default=None, gt=0)
    latest_content: DraftContent | None = None
    latest_created_from: str | None = None
    latest_parent_draft_ref: int | None = Field(default=None, gt=0)
    resolved_draft_version_ref: int | None = Field(default=None, gt=0)
    resolved_version: int | None = Field(default=None, gt=0)
    resolved_content: DraftContent | None = None
    resolved_created_from: str | None = None
    resolved_parent_draft_ref: int | None = Field(default=None, gt=0)
    status: str
    created_at: datetime | None = None
    updated_at: datetime | None = None


class RetrieveResearchEvidenceInput(QueryContract):
    """请求读取研究证据的不可信业务输入。"""

    account_ref: int = Field(gt=0)
    evidence_refs: list[EvidenceRef] = Field(min_length=1)
    purpose: str = Field(min_length=1)
    max_items: int = Field(default=20, ge=1, le=100)
    max_content_chars: int = Field(default=4000, ge=100, le=20000)


class EvidenceItem(QueryContract):
    """可供模型使用且保留来源关系的单条证据。"""

    evidence_ref: EvidenceRef
    evidence_type: EvidenceType
    content: str
    structured_facts: dict[str, Any] = Field(default_factory=dict)
    provenance: str
    source_ref: str | None = None
    observed_at: datetime | None = None


class EvidenceBundle(QueryContract):
    """经过授权和长度限制的研究证据集合。"""

    items: list[EvidenceItem]
    purpose: str
    truncated: bool = False


class QueryPostPublishMetricsInput(QueryContract):
    """读取明确 Published Note 时间窗口指标的输入。"""

    account_ref: int = Field(gt=0)
    published_note_ref: int = Field(gt=0)
    window_start: datetime
    window_end: datetime
    include_private: bool = True

    @model_validator(mode="after")
    def validate_window(self):
        """拒绝结束时间早于开始时间的窗口。"""
        if self.window_end < self.window_start:
            raise ValueError("window_end must not be earlier than window_start")
        return self


class MetricValue(QueryContract):
    """带明确来源的单个指标值。"""

    value: int | Decimal | None
    provenance: str


class MetricWindowResult(QueryContract):
    """指标查询使用的真实时间窗口。"""

    start: datetime
    end: datetime


class PostPublishMetricsResult(QueryContract):
    """公开与用户归因私域指标的统一只读结果。"""

    published_note_ref: int
    publish_url: str | None = None
    account_ref: int | None = Field(default=None, gt=0)
    draft_ref: int | None = Field(default=None, gt=0)
    published_draft_binding_ref: str | None = None
    published_draft_version_number: int | None = Field(default=None, gt=0)
    published_draft_version_ref: int | None = Field(default=None, gt=0)
    publish_package_ref: int | None = Field(default=None, gt=0)
    published_lineage_complete: bool = False
    public_metrics_status: Literal["AVAILABLE", "UNKNOWN"] = "AVAILABLE"
    public_metric_snapshot_ref: int | None = Field(default=None, gt=0)
    public_metrics: dict[str, MetricValue]
    private_metric_snapshot_ref: int | None = Field(default=None, gt=0)
    private_metrics: dict[str, MetricValue] | None = None
    window: MetricWindowResult
    provenance: list[str]
    observed_at: datetime | None = None
    missing_metrics: list[str] = Field(default_factory=list)
