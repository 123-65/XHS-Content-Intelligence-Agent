from types import MappingProxyType

from app.agent.context.contracts import ResolvedObjectType
from app.agent.workflows.definitions import WorkflowId


def _ids(context, kind):
    return [item.resolved_ref.id for item in context.resolved_references if item.resolved_object_type == kind]


def _research(frame, context, pending):
    return {"note_urls": frame.note_urls, "profile_urls": frame.profile_urls, "constraints": frame.constraints}


def _strategy(frame, context, pending):
    refs = _ids(context, ResolvedObjectType.RESEARCH)
    return {"research_artifact_ref": {"type": "RESEARCH", "id": refs[0]}} if len(refs) == 1 else {}


def _creation(frame, context, pending):
    opportunities = _ids(context, ResolvedObjectType.CONTENT_OPPORTUNITY)
    strategies = _ids(context, ResolvedObjectType.CONTENT_STRATEGY)
    payload = {"constraints": frame.constraints, "style_constraints": frame.constraints}
    if len(opportunities) == 1:
        payload["opportunity_ref"] = opportunities[0]
    if len(strategies) == 1:
        payload["strategy_artifact_ref"] = {"type": "CONTENT_STRATEGY", "id": strategies[0]}
    return payload


def _refinement(frame, context, pending):
    drafts = _ids(context, ResolvedObjectType.DRAFT)
    payload = {"constraints": frame.constraints}
    if len(drafts) == 1:
        payload["draft_ref"] = drafts[0]
    if frame.primary_goal:
        payload["user_feedback"] = frame.primary_goal
    return payload


def _review(frame, context, pending):
    notes = _ids(context, ResolvedObjectType.PUBLISHED_NOTE)
    payload = {"refresh_public_metrics": frame.refresh_public_metrics}
    if len(notes) == 1:
        payload["published_note_ref"] = notes[0]
    return payload


WORKFLOW_RESUME_INPUT_BUILDER_REGISTRY = MappingProxyType({
    WorkflowId.RESEARCH_V1: _research,
    WorkflowId.CONTENT_STRATEGY_V1: _strategy,
    WorkflowId.CONTENT_CREATION_V1: _creation,
    WorkflowId.CONTENT_REFINEMENT_V1: _refinement,
    WorkflowId.POST_PUBLISH_REVIEW_V1: _review,
})


def build_resume_input(workflow_id, frame, context, pending):
    return WORKFLOW_RESUME_INPUT_BUILDER_REGISTRY[WorkflowId(workflow_id)](frame, context, pending)
