from datetime import UTC, datetime, timedelta
from types import MappingProxyType

from app.agent.context.contracts import ResolvedContext, ResolvedObjectType
from app.agent.schemas.execution import ArtifactRef, ArtifactType
from app.agent.schemas.semantic import TaskSemanticFrame
from app.agent.workflows.content_creation import ContentCreationWorkflowInput
from app.agent.workflows.content_refinement import ContentRefinementWorkflowInput
from app.agent.workflows.content_strategy import ContentStrategyWorkflowInput
from app.agent.workflows.definitions import WorkflowId
from app.agent.workflows.post_publish_review import PostPublishReviewWorkflowInput
from app.agent.workflows.research import ResearchWorkflowInput


class WorkflowInputMissing(ValueError):
    def __init__(self, fields: list[str]):
        super().__init__(", ".join(fields))
        self.fields = fields


def _refs(context: ResolvedContext, object_type: ResolvedObjectType):
    return [item.resolved_ref for item in context.resolved_references if item.resolved_object_type == object_type]


def _one(context, object_type, field):
    refs = _refs(context, object_type)
    if len(refs) != 1:
        raise WorkflowInputMissing([field])
    return refs[0]


def _research(frame, context, now):
    if not frame.note_urls and not frame.profile_urls:
        raise WorkflowInputMissing(["note_urls_or_profile_urls"])
    return ResearchWorkflowInput(account_ref=context.account_ref, research_goal=frame.primary_goal or "研究用户提供的材料", constraints=[*frame.constraints, *frame.scope_limits], note_urls=frame.note_urls, profile_urls=frame.profile_urls)


def _strategy(frame, context, now):
    research = _one(context, ResolvedObjectType.RESEARCH, "research_artifact_ref")
    return ContentStrategyWorkflowInput(account_ref=context.account_ref, research_artifact_ref=ArtifactRef(type=ArtifactType.RESEARCH, id=int(research.id)), strategy_goal=frame.primary_goal or "制定内容策略", constraints=[*frame.constraints, *frame.scope_limits])


def _creation(frame, context, now):
    opportunity = _one(context, ResolvedObjectType.CONTENT_OPPORTUNITY, "opportunity_ref")
    strategies = _refs(context, ResolvedObjectType.CONTENT_STRATEGY)
    strategy = strategies[0] if len(strategies) == 1 else context.context_facts.get("active_strategy_ref")
    if strategy is None or strategy.type != ResolvedObjectType.CONTENT_STRATEGY:
        raise WorkflowInputMissing(["strategy_artifact_ref"])
    constraints = [*frame.constraints, *frame.scope_limits]
    return ContentCreationWorkflowInput(account_ref=context.account_ref, strategy_artifact_ref=ArtifactRef(type=ArtifactType.CONTENT_STRATEGY, id=int(strategy.id)), opportunity_ref=int(opportunity.id), constraints=constraints, style_constraints=list(frame.constraints))


def _refinement(frame, context, now):
    draft = _one(context, ResolvedObjectType.DRAFT, "draft_ref")
    feedback = frame.primary_goal or frame.expected_deliverable
    if not feedback:
        raise WorkflowInputMissing(["user_feedback"])
    return ContentRefinementWorkflowInput(account_ref=context.account_ref, draft_ref=int(draft.id), user_feedback=feedback, constraints=[*frame.constraints, *frame.scope_limits])


def _post_publish(frame, context, now):
    note = _one(context, ResolvedObjectType.PUBLISHED_NOTE, "published_note_ref")
    end = now().astimezone(UTC)
    return PostPublishReviewWorkflowInput(account_ref=context.account_ref, published_note_ref=int(note.id), window_start=end - timedelta(days=30), window_end=end, refresh_public_metrics=frame.refresh_public_metrics)


WORKFLOW_INPUT_BUILDER_REGISTRY = MappingProxyType({
    WorkflowId.RESEARCH_V1: _research,
    WorkflowId.CONTENT_STRATEGY_V1: _strategy,
    WorkflowId.CONTENT_CREATION_V1: _creation,
    WorkflowId.CONTENT_REFINEMENT_V1: _refinement,
    WorkflowId.POST_PUBLISH_REVIEW_V1: _post_publish,
})


def build_workflow_input(workflow_id, frame, context, now=None):
    return WORKFLOW_INPUT_BUILDER_REGISTRY[workflow_id](frame, context, now or (lambda: datetime.now(UTC)))
