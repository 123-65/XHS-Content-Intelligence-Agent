from types import MappingProxyType

from app.agent.tools.definitions import ToolName
from app.agent.tools.execution_context import ToolExecutionContext
from app.agent.tools.query_tools import (
    QueryArtifactTool,
    QueryGrowthContextTool,
    QueryPostPublishMetricsTool,
    RetrieveResearchEvidenceTool,
)
from app.agent.tools.xhs_tools import CollectXhsAccountsTool, CollectXhsNotesTool
from app.agent.tools.semantic_tools import (
    AnalyzePostPublishReviewTool,
    AnalyzeResearchTool,
    GenerateContentStrategyTool,
    GenerateDraftTool,
    ReviewDraftTool,
    ReviseDraftTool,
)
from app.agent.tools.artifact_tools import (
    CreateContentStrategyArtifactTool,
    CreateDraftVersionTool,
    CreatePostPublishReviewArtifactTool,
    CreateResearchArtifactTool,
    CreateStrategyCandidateTool,
)


TOOL_HANDLER_REGISTRY = MappingProxyType(
    {
        ToolName.QUERY_GROWTH_CONTEXT: QueryGrowthContextTool,
        ToolName.QUERY_ARTIFACT: QueryArtifactTool,
        ToolName.RETRIEVE_RESEARCH_EVIDENCE: RetrieveResearchEvidenceTool,
        ToolName.QUERY_POST_PUBLISH_METRICS: QueryPostPublishMetricsTool,
        ToolName.COLLECT_XHS_NOTES: CollectXhsNotesTool,
        ToolName.COLLECT_XHS_ACCOUNTS: CollectXhsAccountsTool,
        ToolName.ANALYZE_RESEARCH: AnalyzeResearchTool,
        ToolName.GENERATE_CONTENT_STRATEGY: GenerateContentStrategyTool,
        ToolName.GENERATE_DRAFT: GenerateDraftTool,
        ToolName.REVIEW_DRAFT: ReviewDraftTool,
        ToolName.REVISE_DRAFT: ReviseDraftTool,
        ToolName.ANALYZE_POST_PUBLISH_REVIEW: AnalyzePostPublishReviewTool,
        ToolName.CREATE_RESEARCH_ARTIFACT: CreateResearchArtifactTool,
        ToolName.CREATE_CONTENT_STRATEGY_ARTIFACT: CreateContentStrategyArtifactTool,
        ToolName.CREATE_DRAFT_VERSION: CreateDraftVersionTool,
        ToolName.CREATE_POST_PUBLISH_REVIEW_ARTIFACT: CreatePostPublishReviewArtifactTool,
        ToolName.CREATE_STRATEGY_CANDIDATE: CreateStrategyCandidateTool,
    }
)

_PURE_SEMANTIC_TOOLS = frozenset(
    {
        ToolName.ANALYZE_RESEARCH,
        ToolName.GENERATE_CONTENT_STRATEGY,
        ToolName.GENERATE_DRAFT,
        ToolName.REVIEW_DRAFT,
        ToolName.REVISE_DRAFT,
        ToolName.ANALYZE_POST_PUBLISH_REVIEW,
    }
)

_DATABASE_QUERY_TOOLS = frozenset(
    {
        ToolName.QUERY_GROWTH_CONTEXT,
        ToolName.QUERY_ARTIFACT,
        ToolName.QUERY_POST_PUBLISH_METRICS,
    }
)

_EVIDENCE_QUERY_TOOLS = frozenset({ToolName.RETRIEVE_RESEARCH_EVIDENCE})

_COLLECTION_TOOLS = frozenset({ToolName.COLLECT_XHS_NOTES, ToolName.COLLECT_XHS_ACCOUNTS})

_ARTIFACT_TOOLS = frozenset(
    {
        ToolName.CREATE_RESEARCH_ARTIFACT,
        ToolName.CREATE_CONTENT_STRATEGY_ARTIFACT,
        ToolName.CREATE_DRAFT_VERSION,
        ToolName.CREATE_POST_PUBLISH_REVIEW_ARTIFACT,
        ToolName.CREATE_STRATEGY_CANDIDATE,
    }
)


def build_tool_handler(tool_name: ToolName | str, execution_context: ToolExecutionContext):
    """按静态绑定和可信执行上下文构建 Tool，并在构建阶段拒绝缺失依赖。"""
    try:
        normalized = ToolName(tool_name)
        handler_type = TOOL_HANDLER_REGISTRY[normalized]
    except (ValueError, KeyError) as exc:
        raise ValueError(f"Tool 尚未实现: {tool_name}") from exc
    if normalized in _PURE_SEMANTIC_TOOLS:
        return handler_type()
    if execution_context.db is None:
        raise ValueError(f"Tool {normalized.value} 缺少可信数据库会话。")
    if normalized in _EVIDENCE_QUERY_TOOLS:
        if execution_context.evidence_access_scope is None:
            raise ValueError("retrieve_research_evidence 缺少可信 EvidenceAccessScope。")
        return handler_type(db=execution_context.db, access_scope=execution_context.evidence_access_scope)
    if normalized in _COLLECTION_TOOLS:
        if execution_context.collection_access_scope is None:
            raise ValueError(f"{normalized.value} 缺少可信 CollectionAccessScope。")
        return handler_type(db=execution_context.db, access_scope=execution_context.collection_access_scope)
    if normalized in _DATABASE_QUERY_TOOLS:
        return handler_type(db=execution_context.db)
    if normalized in _ARTIFACT_TOOLS:
        return handler_type(db=execution_context.db, runtime_identity=execution_context.runtime_identity)
    raise ValueError(f"Tool {normalized.value} 没有冻结的构建规则。")
