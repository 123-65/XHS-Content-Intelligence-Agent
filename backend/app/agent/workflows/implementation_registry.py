from types import MappingProxyType

from app.agent.workflows.definitions import WorkflowId
from app.agent.workflows.content_strategy import ContentStrategyWorkflow
from app.agent.workflows.content_creation import ContentCreationWorkflow
from app.agent.workflows.content_refinement import ContentRefinementWorkflow
from app.agent.workflows.research import ResearchWorkflow
from app.agent.workflows.post_publish_review import PostPublishReviewWorkflow


WORKFLOW_HANDLER_REGISTRY = MappingProxyType(
    {
        WorkflowId.RESEARCH_V1: ResearchWorkflow,
        WorkflowId.CONTENT_STRATEGY_V1: ContentStrategyWorkflow,
        WorkflowId.CONTENT_CREATION_V1: ContentCreationWorkflow,
        WorkflowId.CONTENT_REFINEMENT_V1: ContentRefinementWorkflow,
        WorkflowId.POST_PUBLISH_REVIEW_V1: PostPublishReviewWorkflow,
    }
)


def build_workflow_handler(workflow_id: WorkflowId | str):
    """构建唯一已实现 Workflow，并拒绝未知或尚未实现的 Workflow。"""
    try:
        normalized = WorkflowId(workflow_id)
        handler = WORKFLOW_HANDLER_REGISTRY[normalized]
    except (ValueError, KeyError) as exc:
        raise ValueError(f"Workflow 尚未实现: {workflow_id}") from exc
    return handler()
