from types import MappingProxyType

from app.agent.tools.definitions import CoreToolInput, CoreToolOutput, ToolDefinition, ToolEffect, ToolName
from app.agent.tools.query_contracts import (
    ArtifactResult,
    EvidenceBundle,
    GrowthContextResult,
    PostPublishMetricsResult,
    QueryArtifactInput,
    QueryGrowthContextInput,
    QueryPostPublishMetricsInput,
    RetrieveResearchEvidenceInput,
)
from app.agent.tools.xhs_contracts import (
    CollectXhsAccountsInput,
    CollectXhsAccountsResult,
    CollectXhsNotesInput,
    CollectXhsNotesResult,
)
from app.agent.tools.semantic_contracts import (
    AnalyzePostPublishReviewInput,
    AnalyzeResearchInput,
    CompetitorSemanticResult,
    GenerateContentStrategyInput,
    GenerateDraftInput,
    GeneratedContentStrategy,
    PostPublishReviewLLMResult,
    ReviewDraftInput,
    ReviseDraftInput,
    SemanticDraftResult,
    SemanticRevisedDraftResult,
)
from app.schemas.draft import DraftReviewLLMResult
from app.agent.tools.artifact_contracts import (
    CreateContentStrategyArtifactInput,
    CreateContentStrategyArtifactResult,
    CreateDraftVersionInput,
    CreateDraftVersionResult,
    CreatePostPublishReviewArtifactInput,
    CreatePostPublishReviewArtifactResult,
    CreateResearchArtifactInput,
    CreateResearchArtifactResult,
    CreateStrategyCandidateInput,
    CreateStrategyCandidateResult,
)


def _definition(name: ToolName, description: str, effect: ToolEffect) -> ToolDefinition:
    """构造不绑定实现的 v1 Tool 合同。"""
    return ToolDefinition(
        name=name,
        description=description,
        input_model=CoreToolInput,
        output_model=CoreToolOutput,
        effect=effect,
        version="v1",
    )


TOOL_REGISTRY = MappingProxyType(
    {
        ToolName.QUERY_GROWTH_CONTEXT: _definition(ToolName.QUERY_GROWTH_CONTEXT, "查询账号增长上下文。", ToolEffect.READ_INTERNAL),
        ToolName.QUERY_ARTIFACT: _definition(ToolName.QUERY_ARTIFACT, "查询既有系统产物。", ToolEffect.READ_INTERNAL),
        ToolName.RETRIEVE_RESEARCH_EVIDENCE: _definition(ToolName.RETRIEVE_RESEARCH_EVIDENCE, "读取研究所需事实证据。", ToolEffect.READ_INTERNAL),
        ToolName.QUERY_POST_PUBLISH_METRICS: _definition(ToolName.QUERY_POST_PUBLISH_METRICS, "查询已发布笔记指标快照。", ToolEffect.READ_INTERNAL),
        ToolName.COLLECT_XHS_NOTES: _definition(ToolName.COLLECT_XHS_NOTES, "采集用户授权的小红书笔记公开数据。", ToolEffect.COLLECT_PUBLIC),
        ToolName.COLLECT_XHS_ACCOUNTS: _definition(ToolName.COLLECT_XHS_ACCOUNTS, "采集用户授权的小红书账号公开数据。", ToolEffect.COLLECT_PUBLIC),
        ToolName.ANALYZE_RESEARCH: _definition(ToolName.ANALYZE_RESEARCH, "基于证据生成研究分析。", ToolEffect.PURE),
        ToolName.GENERATE_CONTENT_STRATEGY: _definition(ToolName.GENERATE_CONTENT_STRATEGY, "生成内容策略语义结果。", ToolEffect.PURE),
        ToolName.GENERATE_DRAFT: _definition(ToolName.GENERATE_DRAFT, "生成结构化内容草稿。", ToolEffect.PURE),
        ToolName.REVIEW_DRAFT: _definition(ToolName.REVIEW_DRAFT, "审核内容草稿。", ToolEffect.PURE),
        ToolName.REVISE_DRAFT: _definition(ToolName.REVISE_DRAFT, "按约束修订内容草稿。", ToolEffect.PURE),
        ToolName.ANALYZE_POST_PUBLISH_REVIEW: _definition(ToolName.ANALYZE_POST_PUBLISH_REVIEW, "分析已发布内容表现。", ToolEffect.PURE),
        ToolName.CREATE_RESEARCH_ARTIFACT: _definition(ToolName.CREATE_RESEARCH_ARTIFACT, "保存派生研究产物。", ToolEffect.CREATE_DERIVED),
        ToolName.CREATE_CONTENT_STRATEGY_ARTIFACT: _definition(ToolName.CREATE_CONTENT_STRATEGY_ARTIFACT, "保存派生内容策略产物。", ToolEffect.CREATE_DERIVED),
        ToolName.CREATE_DRAFT_VERSION: _definition(ToolName.CREATE_DRAFT_VERSION, "保存派生 Draft Version。", ToolEffect.CREATE_DERIVED),
        ToolName.CREATE_POST_PUBLISH_REVIEW_ARTIFACT: _definition(ToolName.CREATE_POST_PUBLISH_REVIEW_ARTIFACT, "保存派生发布后复盘产物。", ToolEffect.CREATE_DERIVED),
        ToolName.CREATE_STRATEGY_CANDIDATE: _definition(ToolName.CREATE_STRATEGY_CANDIDATE, "保存待人工确认的策略候选。", ToolEffect.CREATE_DERIVED),
    }
)

_IMPLEMENTED_TOOL_MODELS = {
    ToolName.QUERY_GROWTH_CONTEXT: (QueryGrowthContextInput, GrowthContextResult),
    ToolName.QUERY_ARTIFACT: (QueryArtifactInput, ArtifactResult),
    ToolName.RETRIEVE_RESEARCH_EVIDENCE: (RetrieveResearchEvidenceInput, EvidenceBundle),
    ToolName.QUERY_POST_PUBLISH_METRICS: (QueryPostPublishMetricsInput, PostPublishMetricsResult),
}

_IMPLEMENTED_TOOL_MODELS.update(
    {
        ToolName.COLLECT_XHS_NOTES: (CollectXhsNotesInput, CollectXhsNotesResult),
        ToolName.COLLECT_XHS_ACCOUNTS: (CollectXhsAccountsInput, CollectXhsAccountsResult),
    }
)

_IMPLEMENTED_TOOL_MODELS.update(
    {
        ToolName.CREATE_RESEARCH_ARTIFACT: (CreateResearchArtifactInput, CreateResearchArtifactResult),
        ToolName.CREATE_CONTENT_STRATEGY_ARTIFACT: (
            CreateContentStrategyArtifactInput,
            CreateContentStrategyArtifactResult,
        ),
        ToolName.CREATE_DRAFT_VERSION: (CreateDraftVersionInput, CreateDraftVersionResult),
        ToolName.CREATE_POST_PUBLISH_REVIEW_ARTIFACT: (
            CreatePostPublishReviewArtifactInput,
            CreatePostPublishReviewArtifactResult,
        ),
        ToolName.CREATE_STRATEGY_CANDIDATE: (
            CreateStrategyCandidateInput,
            CreateStrategyCandidateResult,
        ),
    }
)

_IMPLEMENTED_TOOL_MODELS.update(
    {
        ToolName.ANALYZE_RESEARCH: (AnalyzeResearchInput, CompetitorSemanticResult),
        ToolName.GENERATE_CONTENT_STRATEGY: (GenerateContentStrategyInput, GeneratedContentStrategy),
        ToolName.GENERATE_DRAFT: (GenerateDraftInput, SemanticDraftResult),
        ToolName.REVIEW_DRAFT: (ReviewDraftInput, DraftReviewLLMResult),
        ToolName.REVISE_DRAFT: (ReviseDraftInput, SemanticRevisedDraftResult),
        ToolName.ANALYZE_POST_PUBLISH_REVIEW: (AnalyzePostPublishReviewInput, PostPublishReviewLLMResult),
    }
)

TOOL_REGISTRY = MappingProxyType(
    {
        name: definition.model_copy(
            update={"input_model": _IMPLEMENTED_TOOL_MODELS[name][0], "output_model": _IMPLEMENTED_TOOL_MODELS[name][1]}
        )
        if name in _IMPLEMENTED_TOOL_MODELS
        else definition
        for name, definition in TOOL_REGISTRY.items()
    }
)


def get_tool(tool_id: ToolName | str) -> ToolDefinition:
    """读取冻结 Tool；未知标识必须明确拒绝。"""
    try:
        normalized = ToolName(tool_id)
        return TOOL_REGISTRY[normalized]
    except (ValueError, KeyError) as exc:
        raise ValueError(f"Unknown Tool ID: {tool_id}") from exc
