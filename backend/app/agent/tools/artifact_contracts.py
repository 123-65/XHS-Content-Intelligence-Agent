from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, RootModel, model_validator

from app.agent.schemas.execution import ArtifactRef, ArtifactType
from app.analysis.competitor.schemas import CompetitorEvidence, CompetitorSemanticResult, EvidenceRef as ResearchEvidenceRef
from app.schemas.content_strategy import ContentStrategyResult, EvidenceRef
from app.schemas.draft import DraftContent, DraftPersistenceMetadata
from app.schemas.publication import PostPublishReviewLLMResult, StrategyCandidate


class ArtifactContract(BaseModel):
    """拒绝未声明字段的 Artifact Tool 合同基础类。"""

    model_config = ConfigDict(extra="forbid")


class CreateResearchArtifactInput(ArtifactContract):
    """保存已经完成分析与 Grounding 的 Research 结果。"""

    account_ref: int = Field(gt=0)
    research_result: CompetitorSemanticResult
    research_evidence: CompetitorEvidence
    evidence_refs: list[ResearchEvidenceRef] = Field(default_factory=list)
    source_refs: list[ArtifactRef] = Field(default_factory=list)
    report_name: str = Field(min_length=1, max_length=128)
    keyword: str | None = Field(default=None, max_length=128)
    target_metric: str = Field(default="engagement", max_length=32)
    analysis_engine: Literal["LLM_STRUCTURED_V1"] = "LLM_STRUCTURED_V1"
    sample_state: dict[str, str | bool] = Field(default_factory=dict)


class CreateResearchArtifactResult(ArtifactContract):
    """返回真实 CompetitorAnalysisReport 主键及其 lineage。"""

    artifact_ref: ArtifactRef
    artifact_type: Literal[ArtifactType.RESEARCH] = ArtifactType.RESEARCH
    created_at: datetime | None = None
    evidence_refs: list[ResearchEvidenceRef]
    lineage_refs: list[ArtifactRef]


class CreateContentStrategyArtifactInput(ArtifactContract):
    """保存正式 ContentStrategyResult，不重新映射 Opportunity。"""

    account_ref: int = Field(gt=0)
    research_artifact_ref: int = Field(gt=0)
    strategy_result: ContentStrategyResult


class CreateContentStrategyArtifactResult(ArtifactContract):
    """返回 Strategy Artifact 与真实派生 Opportunity 主键。"""

    artifact_ref: ArtifactRef
    artifact_type: Literal[ArtifactType.CONTENT_STRATEGY] = ArtifactType.CONTENT_STRATEGY
    research_artifact_ref: int
    generated_opportunity_refs: list[int]
    created_at: datetime | None = None


class CreateDraftV1Input(ArtifactContract):
    """创建 Draft Root 与 V1；draft_ref 永久表示 ContentDraft.id。"""

    action: Literal["CREATE_V1"]
    account_ref: int = Field(gt=0)
    strategy_artifact_ref: int = Field(gt=0)
    opportunity_ref: int = Field(gt=0)
    content_goal: str = Field(min_length=1)
    content: DraftContent
    metadata: DraftPersistenceMetadata = Field(default_factory=DraftPersistenceMetadata)
    context: dict = Field(default_factory=dict)


class AppendDraftVersionInput(ArtifactContract):
    """追加版本；parent_draft_ref 永久表示父 ContentDraftVersion.id。"""

    action: Literal["APPEND"]
    draft_ref: int = Field(gt=0)
    parent_draft_ref: int = Field(gt=0)
    created_from: Literal["REVIEW_REVISION", "USER_REVISION"]
    content: DraftContent
    metadata: DraftPersistenceMetadata = Field(default_factory=DraftPersistenceMetadata)
    context: dict = Field(default_factory=dict)
    applied_changes: list[str] = Field(default_factory=list)


class CreateDraftVersionInput(RootModel[CreateDraftV1Input | AppendDraftVersionInput]):
    """区分创建 V1 与追加 Revision，Revision 不暴露 Root Identity 修改字段。"""


class CreateDraftVersionResult(ArtifactContract):
    """区分稳定 Draft Root Ref、Version Ref 与父 Version Ref。"""

    draft_ref: int
    draft_version_ref: int
    version: int
    parent_draft_ref: int | None
    created_from: Literal["GENERATED", "REVIEW_REVISION", "USER_REVISION"]
    created_at: datetime | None = None


class ArtifactGenerationMetadata(ArtifactContract):
    """保存显式生成审计信息，不要求伪造完整 LLM 响应。"""

    prompt_tokens: int = Field(default=0, ge=0)
    completion_tokens: int = Field(default=0, ge=0)
    total_tokens: int = Field(default=0, ge=0)
    estimated_cost: float = Field(default=0, ge=0)
    raw_response_id: str | None = None


class CreatePostPublishReviewArtifactInput(ArtifactContract):
    """保存已完成语义分析的 Post-publish Review。"""

    account_ref: int = Field(gt=0)
    published_note_ref: int = Field(gt=0)
    draft_ref: int = Field(gt=0)
    strategy_ref: int = Field(gt=0)
    opportunity_ref: int = Field(gt=0)
    review_result: PostPublishReviewLLMResult
    metric_snapshot_refs: list[EvidenceRef] = Field(default_factory=list)
    evidence_refs: list[EvidenceRef] = Field(default_factory=list)
    metadata: ArtifactGenerationMetadata = Field(default_factory=ArtifactGenerationMetadata)

    @model_validator(mode="after")
    def validate_evidence_refs(self):
        """确保持久化结果声明的证据没有超出 Tool 输入。"""
        allowed = {(item.kind, item.id) for item in [*self.metric_snapshot_refs, *self.evidence_refs]}
        used = {(item.kind, item.id) for item in self.review_result.evidence_refs}
        for candidate in self.review_result.strategy_candidates:
            used.update((item.kind, item.id) for item in candidate.supporting_refs)
            used.update((item.kind, item.id) for item in candidate.contradicting_refs)
        if not used.issubset(allowed):
            raise ValueError("PostPublishReview evidence lineage mismatch")
        return self


class CreatePostPublishReviewArtifactResult(ArtifactContract):
    """返回稳定 ReviewReport Artifact Ref。"""

    artifact_ref: ArtifactRef
    artifact_type: Literal[ArtifactType.POST_PUBLISH_REVIEW] = ArtifactType.POST_PUBLISH_REVIEW
    published_note_ref: int
    created_at: datetime | None = None


class CreateStrategyCandidateInput(ArtifactContract):
    """从 Review 快照创建服务器固定为 PROPOSED 的 durable Candidate。"""

    account_ref: int = Field(gt=0)
    post_publish_review_ref: int = Field(gt=0)
    candidate: StrategyCandidate

    @model_validator(mode="after")
    def require_proposed(self):
        """禁止调用者借 Artifact Tool 创建已确认或已拒绝状态。"""
        if self.candidate.status != "PROPOSED":
            raise ValueError("Strategy Candidate 创建状态必须为 PROPOSED")
        return self


class CreateStrategyCandidateResult(ArtifactContract):
    """返回以数据库主键为身份的 Candidate Ref。"""

    strategy_candidate_ref: str
    status: Literal["PROPOSED"]
    review_report_ref: int
    created_at: datetime | None = None
