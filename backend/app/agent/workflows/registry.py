from types import MappingProxyType

from app.agent.skills.definitions import SkillId
from app.agent.tools.definitions import ToolName
from app.agent.workflows.definitions import WorkflowDefinition, WorkflowId


WORKFLOW_REGISTRY = MappingProxyType(
    {
        WorkflowId.RESEARCH_V1: WorkflowDefinition(
            id=WorkflowId.RESEARCH_V1,
            skill_id=SkillId.RESEARCH,
            allowed_tools=(
                ToolName.QUERY_GROWTH_CONTEXT,
                ToolName.QUERY_ARTIFACT,
                ToolName.RETRIEVE_RESEARCH_EVIDENCE,
                ToolName.COLLECT_XHS_NOTES,
                ToolName.COLLECT_XHS_ACCOUNTS,
                ToolName.ANALYZE_RESEARCH,
                ToolName.CREATE_RESEARCH_ARTIFACT,
            ),
            input_contract="ResearchWorkflowInput",
            output_contract="ResearchArtifact",
            resumable=True,
            version="v1",
        ),
        WorkflowId.CONTENT_STRATEGY_V1: WorkflowDefinition(
            id=WorkflowId.CONTENT_STRATEGY_V1,
            skill_id=SkillId.CONTENT_STRATEGY,
            allowed_tools=(
                ToolName.QUERY_GROWTH_CONTEXT,
                ToolName.QUERY_ARTIFACT,
                ToolName.GENERATE_CONTENT_STRATEGY,
                ToolName.CREATE_CONTENT_STRATEGY_ARTIFACT,
            ),
            input_contract="ContentStrategyWorkflowInput",
            output_contract="ContentStrategyArtifact",
            resumable=True,
            version="v1",
        ),
        WorkflowId.CONTENT_CREATION_V1: WorkflowDefinition(
            id=WorkflowId.CONTENT_CREATION_V1,
            skill_id=SkillId.CONTENT_CREATION,
            allowed_tools=(
                ToolName.QUERY_GROWTH_CONTEXT,
                ToolName.QUERY_ARTIFACT,
                ToolName.RETRIEVE_RESEARCH_EVIDENCE,
                ToolName.GENERATE_DRAFT,
                ToolName.REVIEW_DRAFT,
                ToolName.REVISE_DRAFT,
                ToolName.CREATE_DRAFT_VERSION,
            ),
            input_contract="ContentCreationWorkflowInput",
            output_contract="DraftArtifact",
            resumable=True,
            version="v1",
        ),
        WorkflowId.CONTENT_REFINEMENT_V1: WorkflowDefinition(
            id=WorkflowId.CONTENT_REFINEMENT_V1,
            skill_id=SkillId.CONTENT_REFINEMENT,
                allowed_tools=(
                    ToolName.QUERY_ARTIFACT,
                    ToolName.QUERY_GROWTH_CONTEXT,
                    ToolName.RETRIEVE_RESEARCH_EVIDENCE,
                    ToolName.REVISE_DRAFT,
                ToolName.CREATE_DRAFT_VERSION,
            ),
            input_contract="ContentRefinementWorkflowInput",
            output_contract="DraftArtifact",
            resumable=True,
            version="v1",
        ),
        WorkflowId.POST_PUBLISH_REVIEW_V1: WorkflowDefinition(
            id=WorkflowId.POST_PUBLISH_REVIEW_V1,
            skill_id=SkillId.POST_PUBLISH_REVIEW,
            allowed_tools=(
                ToolName.QUERY_ARTIFACT,
                ToolName.QUERY_GROWTH_CONTEXT,
                ToolName.QUERY_POST_PUBLISH_METRICS,
                ToolName.COLLECT_XHS_NOTES,
                ToolName.ANALYZE_POST_PUBLISH_REVIEW,
                ToolName.CREATE_POST_PUBLISH_REVIEW_ARTIFACT,
                ToolName.CREATE_STRATEGY_CANDIDATE,
            ),
            input_contract="PostPublishReviewWorkflowInput",
            output_contract="PostPublishReviewArtifact",
            resumable=True,
            version="v1",
        ),
    }
)


def get_workflow(workflow_id: WorkflowId | str) -> WorkflowDefinition:
    """读取冻结 Workflow；未知标识必须明确拒绝。"""
    try:
        normalized = WorkflowId(workflow_id)
        return WORKFLOW_REGISTRY[normalized]
    except (ValueError, KeyError) as exc:
        raise ValueError(f"Unknown Workflow ID: {workflow_id}") from exc


def validate_workflow_tools(workflow_id: WorkflowId | str, tool_ids: list[ToolName | str]) -> tuple[ToolName, ...]:
    """以静态 Allowlist 拒绝未知 Tool 和 Workflow 越权 Tool。"""
    workflow = get_workflow(workflow_id)
    try:
        normalized = tuple(ToolName(tool_id) for tool_id in tool_ids)
    except ValueError as exc:
        raise ValueError("Unknown Tool ID in workflow plan") from exc
    unauthorized = [tool_id for tool_id in normalized if tool_id not in workflow.allowed_tools]
    if unauthorized:
        raise ValueError(f"Workflow {workflow.id} 使用未授权 Tool: {unauthorized}")
    return normalized
