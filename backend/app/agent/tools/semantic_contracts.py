from typing import Any, Literal

from pydantic import Field, model_validator

from app.analysis.competitor.schemas import CompetitorEvidence, CompetitorSemanticResult
from app.agent.schemas.execution import ArtifactRef
from app.agent.tools.query_contracts import EvidenceBundle, PostPublishMetricsResult, QueryContract
from app.schemas.content_strategy import ContentOpportunityResult, EvidenceRef, GeneratedContentStrategy
from app.schemas.draft import DraftContent, DraftReviewLLMResult, DraftRevisionLLMResult
from app.schemas.publication import PostPublishReviewLLMResult


class AnalyzeResearchInput(QueryContract):
    """对已经准备好的事实证据执行研究分析。"""

    account_ref: int = Field(gt=0)
    growth_context: dict[str, Any]
    evidence_bundle: CompetitorEvidence
    research_goal: str = Field(min_length=1)
    constraints: list[str] = Field(default_factory=list)
    source_refs: list[ArtifactRef] = Field(default_factory=list)


class GenerateContentStrategyInput(QueryContract):
    """基于已准备 Research 结果生成策略的纯语义输入。"""

    account_ref: int = Field(gt=0)
    growth_context: dict[str, Any]
    research_result: dict[str, Any]
    historical_opportunities: list[dict[str, Any]] = Field(default_factory=list)
    strategy_memory: list[dict[str, Any]] = Field(default_factory=list)
    evidence_refs: list[EvidenceRef] = Field(min_length=1)
    constraints: list[str] = Field(default_factory=list)


class GenerateDraftInput(QueryContract):
    """以策略、机会和证据正文生成 Draft 的纯语义输入。"""

    account_context: dict[str, Any]
    strategy: dict[str, Any]
    strategy_ref: str = Field(min_length=1)
    opportunity: ContentOpportunityResult
    evidence_bundle: EvidenceBundle
    user_constraints: list[str] = Field(default_factory=list)
    style_constraints: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def require_evidence(self):
        """禁止缺少已授权证据正文时生成 Draft。"""
        if not self.evidence_bundle.items:
            raise ValueError("generate_draft requires EvidenceBundle items")
        return self


class SemanticDraftResult(DraftContent):
    """尚未持久化、但保留内容身份的 Draft 语义结果。"""

    strategy_ref: str
    opportunity_ref: int
    content_goal: str


class ReviewDraftInput(QueryContract):
    """仅评价而不修改 Draft 的输入。"""

    draft: SemanticDraftResult
    strategy: dict[str, Any]
    opportunity: ContentOpportunityResult
    evidence_bundle: EvidenceBundle
    grounding_refs: list[EvidenceRef] = Field(default_factory=list)
    account_context: dict[str, Any]
    review_constraints: list[str] = Field(default_factory=list)


class ReviseDraftInput(QueryContract):
    """按用户反馈或 Review 结果修订 Draft 的输入。"""

    source_draft: SemanticDraftResult
    revision_source: Literal["USER_FEEDBACK", "REVIEW_RESULT"]
    user_instruction: str | None = None
    review_result: DraftReviewLLMResult | None = None
    preserved_constraints: list[str] = Field(default_factory=list)
    evidence_bundle: EvidenceBundle
    opportunity: ContentOpportunityResult | None = None
    grounding_refs: list[EvidenceRef] = Field(default_factory=list)
    context_refs: list[ArtifactRef] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_revision_source(self):
        """校验修订依据，拒绝自动优化等未冻结来源。"""
        if self.revision_source == "USER_FEEDBACK" and not (self.user_instruction or "").strip():
            raise ValueError("USER_FEEDBACK requires user_instruction")
        if self.revision_source == "REVIEW_RESULT" and self.review_result is None:
            raise ValueError("REVIEW_RESULT requires review_result")
        return self


class SemanticRevisedDraftResult(DraftRevisionLLMResult):
    """未持久化且内容身份保持不变的修订结果。"""

    strategy_ref: str
    opportunity_ref: int
    content_goal: str


class AnalyzePostPublishReviewInput(QueryContract):
    """基于已准备发布事实和指标执行复盘的输入。"""

    published_note: dict[str, Any]
    published_draft: dict[str, Any]
    content_strategy: dict[str, Any]
    opportunity: dict[str, Any]
    metrics: PostPublishMetricsResult
    grounding_refs: list[EvidenceRef] = Field(default_factory=list)
    historical_context: list[dict[str, Any]] = Field(default_factory=list)

    @model_validator(mode="after")
    def require_public_metrics(self):
        """允许公开指标 UNKNOWN，但禁止伪造或混用状态。"""
        if self.metrics.public_metrics_status == "UNKNOWN" and self.metrics.public_metrics:
            raise ValueError("UNKNOWN public metrics must be empty")
        if self.metrics.public_metrics_status == "AVAILABLE" and not self.metrics.public_metrics:
            raise ValueError("AVAILABLE public metrics must include measured fields")
        return self


__all__ = [
    "AnalyzePostPublishReviewInput",
    "AnalyzeResearchInput",
    "CompetitorSemanticResult",
    "GenerateContentStrategyInput",
    "GenerateDraftInput",
    "GeneratedContentStrategy",
    "PostPublishReviewLLMResult",
    "ReviewDraftInput",
    "ReviseDraftInput",
    "SemanticDraftResult",
    "SemanticRevisedDraftResult",
]
