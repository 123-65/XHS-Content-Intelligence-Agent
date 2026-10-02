from collections.abc import Callable
from types import MappingProxyType

from pydantic import BaseModel

from app.agent.workflows.content_creation import ContentCreationWorkflowInput, ContentCreationWorkflowState
from app.agent.workflows.content_refinement import ContentRefinementWorkflowInput, ContentRefinementWorkflowState
from app.agent.workflows.content_strategy import ContentStrategyWorkflowInput, ContentStrategyWorkflowState
from app.agent.workflows.definitions import WorkflowId
from app.agent.workflows.post_publish_review import PostPublishReviewWorkflowInput, PostPublishReviewWorkflowState
from app.agent.workflows.research import ResearchWorkflowInput, ResearchWorkflowState


def _research(data: ResearchWorkflowInput) -> ResearchWorkflowState:
    return ResearchWorkflowState(
        account_ref=data.account_ref,
        research_goal=data.research_goal,
        constraints=data.constraints,
        requested_evidence_refs=data.evidence_refs,
    )


def _strategy(data: ContentStrategyWorkflowInput) -> ContentStrategyWorkflowState:
    return ContentStrategyWorkflowState(
        account_ref=data.account_ref,
        strategy_goal=data.strategy_goal,
        constraints=data.constraints,
        research_artifact_ref=data.research_artifact_ref,
    )


def _creation(data: ContentCreationWorkflowInput) -> ContentCreationWorkflowState:
    return ContentCreationWorkflowState(
        account_ref=data.account_ref,
        constraints=data.constraints,
        style_constraints=data.style_constraints,
        strategy_artifact_ref=data.strategy_artifact_ref,
        opportunity_ref=data.opportunity_ref,
    )


def _refinement(data: ContentRefinementWorkflowInput) -> ContentRefinementWorkflowState:
    return ContentRefinementWorkflowState(
        account_ref=data.account_ref,
        draft_ref=data.draft_ref,
        base_draft_version_ref=data.base_draft_version_ref,
        user_feedback=data.user_feedback,
        constraints=data.constraints,
    )


def _post_publish(data: PostPublishReviewWorkflowInput) -> PostPublishReviewWorkflowState:
    return PostPublishReviewWorkflowState(**data.model_dump())


INITIAL_STATE_FACTORIES: dict[WorkflowId, Callable[[BaseModel], BaseModel]] = MappingProxyType(
    {
        WorkflowId.RESEARCH_V1: _research,
        WorkflowId.CONTENT_STRATEGY_V1: _strategy,
        WorkflowId.CONTENT_CREATION_V1: _creation,
        WorkflowId.CONTENT_REFINEMENT_V1: _refinement,
        WorkflowId.POST_PUBLISH_REVIEW_V1: _post_publish,
    }
)


def build_initial_state(workflow_name: WorkflowId, workflow_input: BaseModel) -> BaseModel:
    return INITIAL_STATE_FACTORIES[workflow_name](workflow_input)
