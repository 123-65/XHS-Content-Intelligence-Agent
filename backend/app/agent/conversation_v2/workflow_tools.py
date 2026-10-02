from datetime import UTC, datetime, timedelta
from typing import Any

from pydantic import BaseModel
from pydantic_ai import ModelRetry, RunContext

from app.agent.conversation_v2.deps import ConversationAgentDeps
from app.agent.conversation_v2.decision_context import TOOL_CAPABILITIES
from app.agent.conversation_v2.outcomes import WorkflowToolOutcome
from app.agent.schemas.execution import ArtifactRef, ArtifactType, WorkflowStatus
from app.agent.workflows.definitions import WorkflowId
from app.runtime.agent_runtime import AgentRuntimeError, AgentRuntimeResult, WorkflowStartRequest
from app.runtime.workflow_resume import WorkflowResumeRequest
from app.services.workflow_run_sev import WorkflowRunServiceError


def _public_error(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    return value


def _value(result: Any, key: str) -> Any:
    if result is None:
        return None
    if isinstance(result, BaseModel):
        return getattr(result, key, None)
    if isinstance(result, dict):
        return result.get(key)
    return None


def _artifact(value: Any, artifact_type: ArtifactType) -> ArtifactRef | None:
    if value is None:
        return None
    if isinstance(value, ArtifactRef):
        return value
    if isinstance(value, dict) and value.get("id"):
        return ArtifactRef(type=artifact_type, id=int(value["id"]))
    if isinstance(value, int):
        return ArtifactRef(type=artifact_type, id=value)
    return None


def _artifacts(runtime: AgentRuntimeResult) -> list[ArtifactRef]:
    result = runtime.result
    pairs = (
        ("research_artifact_ref", ArtifactType.RESEARCH),
        ("strategy_artifact_ref", ArtifactType.CONTENT_STRATEGY),
        ("draft_ref", ArtifactType.DRAFT),
        ("review_artifact_ref", ArtifactType.POST_PUBLISH_REVIEW),
    )
    artifacts = [item for key, kind in pairs if (item := _artifact(_value(result, key), kind))]
    for ref in _value(result, "generated_opportunity_refs") or []:
        if item := _artifact(ref, ArtifactType.CONTENT_OPPORTUNITY):
            artifacts.append(item)
    return artifacts


def _message(tool_name: str, runtime: AgentRuntimeResult) -> str:
    subject = {
        "run_research": "研究任务",
        "run_content_strategy": "内容策略任务",
        "run_content_creation": "内容创作任务",
        "run_content_refinement": "草稿修改任务",
        "run_post_publish_review": "发布后复盘任务",
    }[tool_name]
    if runtime.status == WorkflowStatus.WAITING_USER:
        return f"{subject}还需要你补充信息后才能继续。"
    if runtime.status in {WorkflowStatus.SUCCESS, WorkflowStatus.PARTIAL_SUCCESS}:
        return f"{subject}已完成。"
    if runtime.status == WorkflowStatus.FAILED:
        safe_message = getattr(runtime.error, "safe_message", None)
        return f"{subject}执行失败：{safe_message}" if safe_message else f"{subject}执行失败，请稍后重试或调整输入。"
    return f"{subject}已进入执行状态。"


def _record(ctx: RunContext[ConversationAgentDeps], tool_name: str, runtime: AgentRuntimeResult) -> WorkflowToolOutcome:
    pending = runtime.pending_interaction
    error_code = getattr(runtime.error, "code", None)
    if error_code is None and isinstance(runtime.error, dict):
        error_code = runtime.error.get("code")
    return ctx.deps.turn_execution_ledger.record(WorkflowToolOutcome(
        tool_name=tool_name,
        workflow_name=runtime.workflow_name,
        status=runtime.status,
        user_message=_message(tool_name, runtime),
        run_ref=runtime.run_ref,
        checkpoint_version=runtime.checkpoint_version,
        artifact_refs=_artifacts(runtime),
        required_fields=list(pending.required_fields) if pending else [],
        warnings=list(runtime.warnings),
        error_code=error_code,
        safe_error_message=getattr(runtime.error, "safe_message", None),
    ))


def _wait(ctx: RunContext[ConversationAgentDeps], tool_name: str, workflow: WorkflowId, message: str, required: list[str]) -> WorkflowToolOutcome:
    if existing := ctx.deps.turn_execution_ledger.last:
        return existing
    return ctx.deps.turn_execution_ledger.record(WorkflowToolOutcome(
        tool_name=tool_name,
        workflow_name=workflow.value,
        status=WorkflowStatus.WAITING_USER,
        user_message=message,
        required_fields=required,
    ))


def _start(ctx: RunContext[ConversationAgentDeps], tool_name: str, workflow: WorkflowId, payload: dict[str, Any]) -> WorkflowToolOutcome:
    if existing := ctx.deps.turn_execution_ledger.last:
        return existing
    try:
        runtime = ctx.deps.workflow_invoker.start(
            WorkflowStartRequest(workflow_name=workflow, input=payload),
            ctx.deps.execution_context,
        )
        return _record(ctx, tool_name, runtime)
    except AgentRuntimeError as exc:
        return ctx.deps.turn_execution_ledger.record(WorkflowToolOutcome(
            tool_name=tool_name,
            workflow_name=workflow.value,
            status=WorkflowStatus.FAILED,
            user_message="任务启动失败，请检查输入后重试。",
            error_code=exc.code,
        ))


def _resume_pending_research(
    ctx: RunContext[ConversationAgentDeps],
    payload: dict[str, Any],
) -> WorkflowToolOutcome | None:
    """Resume the one trusted pending Research run only for an explicit continuation turn."""
    if existing := ctx.deps.turn_execution_ledger.last:
        return existing
    run_ref = ctx.deps.active_pending_run_ref
    checkpoint_version = ctx.deps.active_pending_checkpoint_version
    pending = ctx.deps.decision_context.pending
    if (
        pending is None
        or pending.workflow_type != WorkflowId.RESEARCH_V1
        or not pending.resumable
        or not pending.requirements_satisfied
        or run_ref is None
        or checkpoint_version is None
    ):
        return None
    try:
        runtime = ctx.deps.workflow_invoker.resume(
            WorkflowResumeRequest(
                run_ref=run_ref,
                expected_checkpoint_version=checkpoint_version,
                new_input=payload,
            ),
            ctx.deps.execution_context,
        )
        return _record(ctx, "run_research", runtime)
    except (AgentRuntimeError, WorkflowRunServiceError) as exc:
        code = getattr(exc, "code", "WORKFLOW_RESUME_FAILED")
        return ctx.deps.turn_execution_ledger.record(WorkflowToolOutcome(
            tool_name="run_research",
            workflow_name=WorkflowId.RESEARCH_V1.value,
            status=WorkflowStatus.FAILED,
            user_message="研究任务恢复失败，请重新发起研究。",
            run_ref=run_ref,
            checkpoint_version=checkpoint_version,
            error_code=code,
        ))


def _validate_tool_selection(ctx: RunContext[ConversationAgentDeps], tool_name: str) -> None:
    """Final objective guard; semantic routing belongs to the gate and the model."""
    context = ctx.deps.decision_context
    capability = TOOL_CAPABILITIES.get(tool_name)
    if capability is None or not context.allows(tool_name):
        raise ModelRetry(f"Tool {tool_name} is not eligible for the server-verified turn context.")
    if context.current_material_types and not context.current_material_types <= capability.accepts_current_materials:
        raise ModelRetry(f"Tool {tool_name} cannot consume the verified current material types.")
    pending = context.pending
    if pending and pending.resumable and pending.requirements_satisfied and capability.workflow_type != pending.workflow_type:
        raise ModelRetry(f"Tool {tool_name} does not match the verified resumable pending workflow.")


def run_research(ctx: RunContext[ConversationAgentDeps], goal: str) -> WorkflowToolOutcome:
    """Run research only when the latest user turn explicitly requests analysis of an authorized XHS account or note. Never call for capability, definition, memory, persona, meta, or follow-up explanation questions, or merely because history contains research."""
    _validate_tool_selection(ctx, "run_research")
    notes = list(ctx.deps.current_materials.note_urls) or list(ctx.deps.recent_note_urls)
    profiles = list(ctx.deps.current_materials.profile_urls) or list(ctx.deps.recent_profile_urls)
    if not notes and not profiles:
        return _wait(ctx, "run_research", WorkflowId.RESEARCH_V1, "请提供要分析的小红书账号或笔记链接。", ["research_material"])
    payload = {
        "account_ref": ctx.deps.account_ref,
        "research_goal": goal,
        "constraints": [],
        "note_urls": notes,
        "profile_urls": profiles,
        "evidence_refs": [],
        "artifact_refs": [],
    }
    return _resume_pending_research(ctx, payload) or _start(ctx, "run_research", WorkflowId.RESEARCH_V1, payload)


def run_content_strategy(ctx: RunContext[ConversationAgentDeps], goal: str) -> WorkflowToolOutcome:
    """Create strategy only when the latest user turn explicitly requests strategy execution from trusted research. Never call for capability, definition, memory, persona, meta, or follow-up explanation questions, or merely because research exists in history."""
    _validate_tool_selection(ctx, "run_content_strategy")
    research_ref = ctx.deps.trusted_workspace.research_ref or ctx.deps.recent_context.research_ref
    if research_ref is None:
        return _wait(ctx, "run_content_strategy", WorkflowId.CONTENT_STRATEGY_V1, "请先选择或完成一份研究材料，我再据此制定策略。", ["research_material"])
    return _start(ctx, "run_content_strategy", WorkflowId.CONTENT_STRATEGY_V1, {
        "account_ref": ctx.deps.account_ref,
        "research_artifact_ref": {"type": ArtifactType.RESEARCH.value, "id": research_ref},
        "strategy_goal": goal,
        "constraints": [],
    })


def run_content_creation(ctx: RunContext[ConversationAgentDeps], goal: str) -> WorkflowToolOutcome:
    """Create a draft only when the latest user turn explicitly requests writing from a trusted opportunity. Never call for capability, definition, memory, persona, meta, or follow-up explanation questions, or merely because strategy exists in history."""
    _validate_tool_selection(ctx, "run_content_creation")
    opportunity_ref = ctx.deps.trusted_workspace.opportunity_ref or ctx.deps.recent_context.opportunity_ref
    strategy_ref = (
        ctx.deps.trusted_workspace.opportunity_strategy_ref
        or ctx.deps.recent_context.opportunity_strategy_ref
    )
    missing = []
    if strategy_ref is None:
        missing.append("content_strategy")
    if opportunity_ref is None:
        missing.append("content_opportunity")
    if missing:
        return _wait(ctx, "run_content_creation", WorkflowId.CONTENT_CREATION_V1, "需要选择一个内容机会或策略。", ["content_context"])
    return _start(ctx, "run_content_creation", WorkflowId.CONTENT_CREATION_V1, {
        "account_ref": ctx.deps.account_ref,
        "strategy_artifact_ref": {"type": ArtifactType.CONTENT_STRATEGY.value, "id": strategy_ref},
        "opportunity_ref": opportunity_ref,
        "constraints": [goal],
        "style_constraints": [],
    })


def run_content_refinement(ctx: RunContext[ConversationAgentDeps], instruction: str) -> WorkflowToolOutcome:
    """Revise a trusted draft only when the latest user turn explicitly requests a concrete edit. Never call for capability, definition, memory, persona, meta, or follow-up explanation questions, or merely because a draft exists in history."""
    _validate_tool_selection(ctx, "run_content_refinement")
    draft_ref = ctx.deps.trusted_workspace.draft_ref or ctx.deps.recent_context.draft_ref
    if draft_ref is None:
        return _wait(ctx, "run_content_refinement", WorkflowId.CONTENT_REFINEMENT_V1, "请先选择要修改的草稿。", ["draft"])
    return _start(ctx, "run_content_refinement", WorkflowId.CONTENT_REFINEMENT_V1, {
        "account_ref": ctx.deps.account_ref,
        "draft_ref": draft_ref,
        "user_feedback": instruction,
        "base_draft_version_ref": None,
        "constraints": [],
    })


def run_post_publish_review(ctx: RunContext[ConversationAgentDeps], goal: str) -> WorkflowToolOutcome:
    """Review a trusted Published Note only when the latest user turn explicitly requests post-publish review. Never call for capability, definition, memory, persona, meta, or follow-up explanation questions, or merely because a published note exists in history."""
    _validate_tool_selection(ctx, "run_post_publish_review")
    published_ref = ctx.deps.trusted_workspace.published_note_ref or ctx.deps.recent_context.published_note_ref
    if published_ref is None:
        return _wait(ctx, "run_post_publish_review", WorkflowId.POST_PUBLISH_REVIEW_V1, "请从本系统中选择一条已发布笔记后再复盘。", ["published_note"])
    window_end = datetime.now(UTC)
    return _start(ctx, "run_post_publish_review", WorkflowId.POST_PUBLISH_REVIEW_V1, {
        "account_ref": ctx.deps.account_ref,
        "published_note_ref": published_ref,
        "window_start": window_end - timedelta(days=7),
        "window_end": window_end,
        "refresh_public_metrics": False,
        "include_private_metrics": True,
    })


WORKFLOW_TOOLS = (
    run_research,
    run_content_strategy,
    run_content_creation,
    run_content_refinement,
    run_post_publish_review,
)
