from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.agent.context.contracts import (
    AmbiguousReference, ContextResolverInput, IdentityRecord, ObjectRef,
    OpportunityCollection, ResolvedContext, ResolvedObjectType, ResolvedReference,
    ResolutionSource, StructuredContext, TrustedContextRef, UnresolvedReference,
)
from app.agent.context.resolver import ContextResolver
from app.agent.control.semantic_layer import ControlAgentSemanticLayer
from app.agent.planning.execution_service import PlanExecutionService
from app.agent.planning.planner import DeterministicPlanner
from app.agent.schemas.execution import RuntimeAction, WorkflowStatus
from app.agent.schemas.planning import PlanStatus
from app.agent.schemas.semantic import Intent, SemanticReferenceType, TaskSemanticFrame


NOW = datetime(2026, 9, 22, 12, tzinfo=UTC)


def resolved(kind, identity, reference_type=SemanticReferenceType.UNKNOWN):
    return ResolvedReference(reference_type=reference_type, raw_text="测试引用", resolved_ref=ObjectRef(type=kind, id=identity), resolved_object_type=kind, resolution_source=ResolutionSource.ACTIVE_CONTEXT, confidence=1)


def context(*refs, **kwargs):
    return ResolvedContext(account_ref=7, resolved_references=list(refs), **kwargs)


def frame(intent, **kwargs):
    defaults = {"primary_intent": intent, "primary_goal": "完成当前目标", "confidence": .95}
    defaults.update(kwargs)
    return TaskSemanticFrame(**defaults)


def planner():
    return DeterministicPlanner(now=lambda: NOW)


def test_research_with_user_urls_is_ready():
    plan = planner().plan(frame(Intent.RESEARCH, primary_goal="研究这些笔记", note_urls=["https://xhs/note/1"]), context())
    assert plan.status == PlanStatus.READY
    assert plan.action == RuntimeAction.EXECUTE_PLAN
    assert plan.steps[0].workflow_id == "RESEARCH_V1"
    assert plan.steps[0].workflow_input["note_urls"] == ["https://xhs/note/1"]


def test_unknown_semantic_business_failure_uses_safe_split_message():
    message = "当前请求同时包含工作流任务和其他独立目标，请拆分为两个请求。"

    plan = planner().plan(frame(Intent.UNKNOWN, missing_info=[message], confidence=0), context())

    assert plan.status == PlanStatus.NEED_USER_INPUT
    assert plan.missing_inputs == [message]


def test_content_strategy_uses_resolved_research():
    plan = planner().plan(frame(Intent.CONTENT_STRATEGY), context(resolved(ResolvedObjectType.RESEARCH, 100)))
    assert plan.steps[0].workflow_id == "CONTENT_STRATEGY_V1"
    assert plan.steps[0].workflow_input["research_artifact_ref"] == {"type": "RESEARCH", "id": 100}


def test_content_strategy_optional_semantic_preferences_do_not_block_ready_plan():
    semantic = frame(
        Intent.CONTENT_STRATEGY,
        primary_goal="根据刚才那个研究帮我做选题",
        missing_info=["选题数量", "选题偏好"],
    )
    resolved_context = context(resolved(ResolvedObjectType.RESEARCH, 100))

    plan = planner().plan(semantic, resolved_context)

    assert semantic.missing_info == ["选题数量", "选题偏好"]
    assert resolved_context.blocking_missing_info == []
    assert plan.status == PlanStatus.READY
    assert plan.steps[0].workflow_id == "CONTENT_STRATEGY_V1"
    assert plan.steps[0].workflow_input["research_artifact_ref"]["id"] == 100


def test_content_strategy_without_research_still_blocks_even_with_optional_preferences():
    plan = planner().plan(
        frame(Intent.CONTENT_STRATEGY, missing_info=["选题数量"]),
        context(),
    )

    assert plan.status == PlanStatus.NEED_USER_INPUT
    assert plan.missing_inputs == ["research_artifact_ref"]


def test_content_strategy_without_research_needs_input_and_never_runs():
    plan = planner().plan(frame(Intent.CONTENT_STRATEGY), context())
    runtime = FakeRuntime([])
    result = PlanExecutionService(runtime).execute(plan, None)
    assert plan.status == PlanStatus.NEED_USER_INPUT
    assert "research_artifact_ref" in plan.missing_inputs
    assert result.step_results == [] and runtime.calls == []


def test_content_creation_uses_exact_strategy_and_opportunity_and_preserves_constraints():
    plan = planner().plan(frame(Intent.CONTENT_CREATE, constraints=["语气自然一点"]), context(resolved(ResolvedObjectType.CONTENT_STRATEGY, 100), resolved(ResolvedObjectType.CONTENT_OPPORTUNITY, 202)))
    payload = plan.steps[0].workflow_input
    assert plan.steps[0].workflow_id == "CONTENT_CREATION_V1"
    assert payload["strategy_artifact_ref"]["id"] == 100
    assert payload["opportunity_ref"] == 202
    assert payload["constraints"] == ["语气自然一点"]
    assert payload["style_constraints"] == ["语气自然一点"]


def test_refinement_uses_draft_and_feedback():
    plan = planner().plan(frame(Intent.CONTENT_REFINE, primary_goal="写得更自然"), context(resolved(ResolvedObjectType.DRAFT, 100)))
    assert plan.steps[0].workflow_id == "CONTENT_REFINEMENT_V1"
    assert plan.steps[0].workflow_input["draft_ref"] == 100
    assert plan.steps[0].workflow_input["user_feedback"] == "写得更自然"


def test_post_publish_review_defaults_to_no_refresh():
    plan = planner().plan(frame(Intent.POST_PUBLISH_REVIEW), context(resolved(ResolvedObjectType.PUBLISHED_NOTE, 500)))
    payload = plan.steps[0].workflow_input
    assert plan.steps[0].workflow_id == "POST_PUBLISH_REVIEW_V1"
    assert payload["published_note_ref"] == 500
    assert payload["refresh_public_metrics"] is False


def test_explicit_refresh_signal_is_preserved():
    plan = planner().plan(frame(Intent.POST_PUBLISH_REVIEW, refresh_public_metrics=True), context(resolved(ResolvedObjectType.PUBLISHED_NOTE, 500)))
    assert plan.steps[0].workflow_input["refresh_public_metrics"] is True


@pytest.mark.parametrize(
    ("intent", "action", "status"),
    [
        (Intent.GENERAL_CHAT, RuntimeAction.RESPOND, PlanStatus.READY),
        (Intent.QUERY_PROFILE, RuntimeAction.QUERY, PlanStatus.READY),
        (Intent.UPDATE_PROFILE, RuntimeAction.CONFIRM, PlanStatus.READY),
        (Intent.QUERY_HISTORY, RuntimeAction.QUERY, PlanStatus.READY),
        (Intent.UPDATE_STRATEGY, RuntimeAction.CONFIRM, PlanStatus.READY),
        (Intent.CANCEL_TASK, RuntimeAction.CANCEL, PlanStatus.READY),
        (Intent.UNKNOWN, RuntimeAction.CLARIFY, PlanStatus.NEED_USER_INPUT),
    ],
)
def test_non_workflow_intents_never_enter_runtime(intent, action, status):
    plan = planner().plan(frame(intent), context())
    runtime = FakeRuntime([])
    PlanExecutionService(runtime).execute(plan, None)
    assert plan.action == action and plan.status == status
    assert plan.steps == [] and runtime.calls == []


def test_unresolved_and_ambiguous_gate_workflow_execution():
    unresolved = UnresolvedReference(reference_type=SemanticReferenceType.ACTIVE_DRAFT, raw_text="这篇", reason="REFERENCE_NOT_FOUND")
    ambiguous = AmbiguousReference(reference_type=SemanticReferenceType.ACTIVE_DRAFT, raw_text="那篇", candidate_refs=[ObjectRef(type=ResolvedObjectType.DRAFT, id=1), ObjectRef(type=ResolvedObjectType.DRAFT, id=2)], reason="MULTIPLE_VALID_CANDIDATES")
    for ctx in (context(unresolved_references=[unresolved]), context(ambiguous_references=[ambiguous])):
        plan = planner().plan(frame(Intent.CONTENT_REFINE), ctx)
        assert plan.status == PlanStatus.NEED_USER_INPUT


def test_multi_goal_plan_is_a_registry_backed_dag():
    plan = planner().plan(frame(Intent.POST_PUBLISH_REVIEW, sub_goals=[Intent.CONTENT_REFINE], primary_goal="分析并自然重写"), context(resolved(ResolvedObjectType.PUBLISHED_NOTE, 500), resolved(ResolvedObjectType.DRAFT, 100)))
    assert [step.workflow_id for step in plan.steps] == ["POST_PUBLISH_REVIEW_V1", "CONTENT_REFINEMENT_V1"]
    assert plan.steps[1].depends_on == [plan.steps[0].step_id]


class FakeRuntime:
    def __init__(self, statuses):
        self.statuses = list(statuses)
        self.calls = []

    def start(self, request, execution_context):
        self.calls.append((request, execution_context))
        status = self.statuses.pop(0)
        return SimpleNamespace(run_ref=f"run_{len(self.calls)}", status=status, pending_interaction=None, result={"ok": True}, error=None)


def test_ready_plan_calls_agent_runtime_only_once_for_single_step():
    plan = planner().plan(frame(Intent.CONTENT_CREATE), context(resolved(ResolvedObjectType.CONTENT_STRATEGY, 100), resolved(ResolvedObjectType.CONTENT_OPPORTUNITY, 202)))
    runtime = FakeRuntime([WorkflowStatus.SUCCESS])
    result = PlanExecutionService(runtime).execute(plan, "trusted-context")
    assert len(runtime.calls) == 1
    assert runtime.calls[0][0].workflow_name == "CONTENT_CREATION_V1"
    assert runtime.calls[0][0].input["opportunity_ref"] == 202
    assert result.status == WorkflowStatus.SUCCESS


def test_full_semantic_resolver_planner_runtime_chain_starts_only_creation():
    semantic_client = SimpleNamespace(generate_structured=lambda **kwargs: SimpleNamespace(data={
        "primary_intent": "CONTENT_CREATE",
        "primary_goal": "用第二个选题写一篇",
        "constraints": ["语气自然一点"],
        "references": [{"type": "ORDINAL_OPPORTUNITY", "raw_text": "第二个选题", "ordinal": 2}],
        "confidence": .98,
    }))
    semantic_frame = ControlAgentSemanticLayer(semantic_client).understand("用第二个选题帮我写一篇，语气自然一点")
    strategy = TrustedContextRef(ref=ObjectRef(type=ResolvedObjectType.CONTENT_STRATEGY, id=100), account_ref=7)
    opportunities = [TrustedContextRef(ref=ObjectRef(type=ResolvedObjectType.CONTENT_OPPORTUNITY, id=item), account_ref=7) for item in (201, 202, 203)]
    identities = {item.ref: IdentityRecord(ref=item.ref, account_ref=7) for item in [strategy, *opportunities]}
    reader = SimpleNamespace(
        get_identity=lambda item: identities.get(item),
        list_published_between=lambda *args: [],
        latest_published=lambda *args: None,
    )
    resolved_context = ContextResolver(reader, now=lambda: NOW).resolve(ContextResolverInput(
        account_ref=7,
        semantic_frame=semantic_frame,
        active_context=StructuredContext(opportunity_collections=[OpportunityCollection(strategy_ref=strategy, opportunity_refs=opportunities)]),
    ))
    plan = planner().plan(semantic_frame, resolved_context)
    runtime = FakeRuntime([WorkflowStatus.SUCCESS])
    PlanExecutionService(runtime).execute(plan, "trusted-context")
    assert len(runtime.calls) == 1
    assert runtime.calls[0][0].workflow_name == "CONTENT_CREATION_V1"
    assert runtime.calls[0][0].input["opportunity_ref"] == 202
    assert runtime.calls[0][0].input["constraints"] == ["语气自然一点"]


@pytest.mark.parametrize("status", [WorkflowStatus.WAITING_USER, WorkflowStatus.FAILED])
def test_waiting_or_failed_stops_dependent_step(status):
    plan = planner().plan(frame(Intent.POST_PUBLISH_REVIEW, sub_goals=[Intent.CONTENT_REFINE]), context(resolved(ResolvedObjectType.PUBLISHED_NOTE, 500), resolved(ResolvedObjectType.DRAFT, 100)))
    runtime = FakeRuntime([status, WorkflowStatus.SUCCESS])
    result = PlanExecutionService(runtime).execute(plan, None)
    assert len(runtime.calls) == 1
    assert result.status == status
    assert result.stopped_before_step == "step_2"


def test_success_allows_already_materialized_dependent_step():
    plan = planner().plan(frame(Intent.POST_PUBLISH_REVIEW, sub_goals=[Intent.CONTENT_REFINE]), context(resolved(ResolvedObjectType.PUBLISHED_NOTE, 500), resolved(ResolvedObjectType.DRAFT, 100)))
    runtime = FakeRuntime([WorkflowStatus.SUCCESS, WorkflowStatus.PARTIAL_SUCCESS])
    result = PlanExecutionService(runtime).execute(plan, None)
    assert len(runtime.calls) == 2
    assert result.status == WorkflowStatus.PARTIAL_SUCCESS


def test_planner_and_execution_architecture_boundaries():
    root = Path(__file__).resolve().parents[1] / "app" / "agent" / "planning"
    planner_source = "\n".join((root / name).read_text(encoding="utf-8") for name in ("planner.py", "input_builders.py"))
    execution_source = (root / "execution_service.py").read_text(encoding="utf-8")
    assert not any(token in planner_source for token in ("app.llm", "app.repositories", "sqlalchemy", "Provider", "build_workflow_handler", ".execute("))
    assert not any(token in execution_source for token in ("app.llm", "app.repositories", "sqlalchemy", "build_tool_handler", "build_workflow_handler"))
    assert ".start(" in execution_source
