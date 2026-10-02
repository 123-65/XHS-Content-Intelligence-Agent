from typing import Any

from app.analysis.competitor.engine import CompetitorAnalysisEngine
from app.analysis.competitor.llm_analyzer import LLMStructuredCompetitorAnalyzer
from app.agent.tools.definitions import ToolError, ToolResult
from app.agent.tools.semantic_contracts import (
    AnalyzePostPublishReviewInput,
    AnalyzeResearchInput,
    GenerateContentStrategyInput,
    GenerateDraftInput,
    ReviewDraftInput,
    ReviseDraftInput,
    SemanticDraftResult,
    SemanticRevisedDraftResult,
)
from app.schemas.content_strategy import GeneratedContentStrategy
from app.schemas.draft import DraftContent, DraftReviewLLMResult, DraftRevisionLLMResult
from app.schemas.publication import PostPublishReviewLLMResult
from app.services.content_strategy_sev import ContentStrategyService
from app.services.draft_generation_sev import DraftGenerationService
from app.services.draft_review_sev import DraftReviewService
from app.services.draft_revision_sev import DraftRevisionService
from app.services.post_publish_review_v0_sev import PostPublishReviewService


class SemanticToolBase:
    """六个纯语义 Tool 共用的失败结果映射。"""

    def _failure(self, exc: Exception) -> ToolResult:
        """将 Canonical Service 异常映射为统一失败结果，不返回部分语义结果。"""
        known_code = getattr(exc, "code", None)
        code = known_code or ("VALIDATION_ERROR" if isinstance(exc, ValueError) else "INTERNAL_ERROR")
        category = "TIMEOUT" if code == "LLM_TIMEOUT" else "GROUNDING" if str(code).startswith(("GROUNDING", "ANALYSIS_")) else "VALIDATION" if code == "VALIDATION_ERROR" else "INTERNAL"
        safe_message = "业务模型调用超时，请稍后重试。" if code == "LLM_TIMEOUT" else "语义处理失败，输入上下文或结果未通过校验。"
        return ToolResult(
            success=False,
            data=None,
            error=ToolError(code=str(code), category=category, retryable=category in {"INTERNAL", "TIMEOUT"}, safe_message=safe_message),
            metadata={"exception_type": type(exc).__name__},
        )


class AnalyzeResearchTool(SemanticToolBase):
    """调用唯一结构化竞品分析 Owner 并保留 Grounding 门禁。"""

    name = "analyze_research"

    def __init__(self, analyzer: CompetitorAnalysisEngine | None = None):
        """注入 CompetitorAnalysisEngine 实现。"""
        self.analyzer = analyzer or LLMStructuredCompetitorAnalyzer()

    def execute(self, data: AnalyzeResearchInput) -> ToolResult:
        """仅分析已准备 CompetitorEvidence，不采集或查询其他资源。"""
        try:
            if data.evidence_bundle.account_id != data.account_ref:
                raise ValueError("EvidenceBundle 与 account_ref 不一致")
            return ToolResult(success=True, data=self.analyzer.analyze(data.evidence_bundle))
        except Exception as exc:
            return self._failure(exc)


class GenerateContentStrategyTool(SemanticToolBase):
    """调用 ContentStrategyService 的纯语义入口。"""

    name = "generate_content_strategy"

    def __init__(self, service: ContentStrategyService | None = None):
        """注入唯一 Content Strategy Owner。"""
        self.service = service or ContentStrategyService(None)

    def execute(self, data: GenerateContentStrategyInput) -> ToolResult[GeneratedContentStrategy]:
        """生成策略结果，不保存 Strategy Artifact。"""
        try:
            result = self.service.generate_semantic(data.model_dump(mode="json"))
            return ToolResult(success=True, data=GeneratedContentStrategy.model_validate(result))
        except Exception as exc:
            return self._failure(exc)


class GenerateDraftTool(SemanticToolBase):
    """调用 DraftGenerationService 的纯语义入口。"""

    name = "generate_draft"

    def __init__(self, service: DraftGenerationService | None = None):
        """注入唯一 Draft Generation Owner。"""
        self.service = service or DraftGenerationService(None)

    def execute(self, data: GenerateDraftInput) -> ToolResult[SemanticDraftResult]:
        """生成不持久化 Draft，并由代码保持 Strategy、Opportunity 与 Goal 身份。"""
        try:
            embedded_strategy_ref = data.strategy.get("strategy_ref")
            if embedded_strategy_ref is not None and embedded_strategy_ref != data.strategy_ref:
                raise ValueError("strategy identity mismatch")
            content = DraftContent.model_validate(self.service.generate_semantic(data.model_dump(mode="json")))
            result = SemanticDraftResult(
                **content.model_dump(),
                strategy_ref=data.strategy_ref,
                opportunity_ref=data.opportunity.source_opportunity_id,
                content_goal=data.opportunity.content_goal,
            )
            return ToolResult(success=True, data=result)
        except Exception as exc:
            return self._failure(exc)


class ReviewDraftTool(SemanticToolBase):
    """调用 DraftReviewService 的纯评价入口。"""

    name = "review_draft"

    def __init__(self, service: DraftReviewService | None = None):
        """注入唯一 Draft Review Owner。"""
        self.service = service or DraftReviewService(None)

    def execute(self, data: ReviewDraftInput) -> ToolResult[DraftReviewLLMResult]:
        """评价 Draft，不修改正文或创建 Review Artifact。"""
        try:
            payload = data.model_dump(mode="json")
            payload["evidence_refs"] = _review_evidence_refs(data)
            payload.pop("grounding_refs", None)
            result = self.service.review_semantic(payload)
            return ToolResult(success=True, data=DraftReviewLLMResult.model_validate(result))
        except Exception as exc:
            return self._failure(exc)


class ReviseDraftTool(SemanticToolBase):
    """调用 DraftRevisionService 的纯语义修订入口。"""

    name = "revise_draft"

    def __init__(self, service: DraftRevisionService | None = None):
        """注入唯一 Draft Revision Owner。"""
        self.service = service or DraftRevisionService(None)

    def execute(self, data: ReviseDraftInput) -> ToolResult[SemanticRevisedDraftResult]:
        """修订表达并由代码复制不可变内容身份，不保存版本。"""
        try:
            content = DraftRevisionLLMResult.model_validate(self.service.revise_semantic(data.model_dump(mode="json")))
            result = SemanticRevisedDraftResult(
                **content.model_dump(),
                strategy_ref=data.source_draft.strategy_ref,
                opportunity_ref=data.source_draft.opportunity_ref,
                content_goal=data.source_draft.content_goal,
            )
            return ToolResult(success=True, data=result)
        except Exception as exc:
            return self._failure(exc)


class AnalyzePostPublishReviewTool(SemanticToolBase):
    """调用 PostPublishReviewService 的纯语义复盘入口。"""

    name = "analyze_post_publish_review"

    def __init__(self, service: PostPublishReviewService | None = None):
        """注入唯一 Post-publish Review Owner。"""
        self.service = service or PostPublishReviewService(None)

    def execute(self, data: AnalyzePostPublishReviewInput) -> ToolResult[PostPublishReviewLLMResult]:
        """分析发布表现并只返回 PROPOSED Candidate，不写入 Memory。"""
        try:
            payload = data.model_dump(mode="json")
            payload["evidence_refs"] = [item.model_dump(mode="json") for item in data.grounding_refs]
            result = PostPublishReviewLLMResult.model_validate(self.service.review_semantic(payload))
            if any(item.status != "PROPOSED" for item in result.strategy_candidates):
                raise ValueError("Strategy Candidate 必须保持 PROPOSED")
            return ToolResult(success=True, data=result)
        except Exception as exc:
            return self._failure(exc)


def _domain_evidence_refs(bundle) -> list[dict[str, Any]]:
    """把证据 Bundle 中可表达的事实引用映射到现有 Domain EvidenceRef。"""
    return [
        {"kind": "competitor_note", "id": item.evidence_ref.id}
        for item in bundle.items
        if item.evidence_type.value == "NOTE"
    ]


def _review_evidence_refs(data: ReviewDraftInput) -> list[dict[str, Any]]:
    """Expose only verified lineage grounding and retrieved Note identities to Review."""
    refs = [item.model_dump(mode="json") for item in data.grounding_refs]
    refs.extend(_domain_evidence_refs(data.evidence_bundle))
    return list({(item["kind"], item["id"]): item for item in refs}.values())
