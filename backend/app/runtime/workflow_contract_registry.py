from types import MappingProxyType
from typing import NamedTuple

from pydantic import BaseModel

from app.agent.workflows.content_creation import ContentCreationWorkflowInput, ContentCreationWorkflowResult, ContentCreationWorkflowState
from app.agent.workflows.content_refinement import ContentRefinementWorkflowInput, ContentRefinementWorkflowResult, ContentRefinementWorkflowState
from app.agent.workflows.content_strategy import ContentStrategyWorkflowInput, ContentStrategyWorkflowResult, ContentStrategyWorkflowState
from app.agent.workflows.definitions import WorkflowId
from app.agent.workflows.post_publish_review import PostPublishReviewWorkflowInput, PostPublishReviewWorkflowResult, PostPublishReviewWorkflowState
from app.agent.workflows.research import ResearchWorkflowInput, ResearchWorkflowResult, ResearchWorkflowState


class WorkflowRuntimeContract(NamedTuple):
    """一个冻结 Workflow 在 Durable Store 中使用的 typed contracts。"""

    input_type: type[BaseModel]
    state_type: type[BaseModel]
    result_type: type[BaseModel]


WORKFLOW_RUNTIME_CONTRACTS = MappingProxyType(
    {
        WorkflowId.RESEARCH_V1: WorkflowRuntimeContract(ResearchWorkflowInput, ResearchWorkflowState, ResearchWorkflowResult),
        WorkflowId.CONTENT_STRATEGY_V1: WorkflowRuntimeContract(ContentStrategyWorkflowInput, ContentStrategyWorkflowState, ContentStrategyWorkflowResult),
        WorkflowId.CONTENT_CREATION_V1: WorkflowRuntimeContract(ContentCreationWorkflowInput, ContentCreationWorkflowState, ContentCreationWorkflowResult),
        WorkflowId.CONTENT_REFINEMENT_V1: WorkflowRuntimeContract(ContentRefinementWorkflowInput, ContentRefinementWorkflowState, ContentRefinementWorkflowResult),
        WorkflowId.POST_PUBLISH_REVIEW_V1: WorkflowRuntimeContract(PostPublishReviewWorkflowInput, PostPublishReviewWorkflowState, PostPublishReviewWorkflowResult),
    }
)


def get_runtime_contract(workflow_name: WorkflowId | str) -> WorkflowRuntimeContract:
    """返回唯一静态 typed contract；拒绝非正式 Workflow。"""
    try:
        return WORKFLOW_RUNTIME_CONTRACTS[WorkflowId(workflow_name)]
    except (ValueError, KeyError) as exc:
        raise ValueError(f"Unknown Workflow ID: {workflow_name}") from exc
