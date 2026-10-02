from sqlalchemy.orm import Session

from app.agent.product_entry.business_handlers import build_competitor_workflow_handler_registry
from app.agent.product_entry.confirmation import build_confirmation_card
from app.agent.product_entry.execution import ExecutionMode, ExecutionStatus, PlanExecutionResult
from app.agent.product_entry.executor import ExecutionOrchestrator, build_response_from_execution
from app.agent.product_entry.llm_router import LLMUserInputRouter
from app.agent.product_entry.pipeline import (
    AgentEntryPreviewPipeline,
    apply_param_validation_to_plan,
    build_agent_input_from_chat_request,
    build_plan_validation_result,
    merge_param_validation_results,
)
from app.agent.product_entry.schemas import Action, AgentChatRequest, AgentChatResponse, Plan, PlanStep
from app.agent.product_entry.task_planner import LLMTaskPlanner
from app.agent.product_entry.trace import AgentEntryTraceRecorder, to_agent_trace_payload
from app.agent.product_entry.validators import validate_param_sources, validate_plan_params, validate_plan_result
from app.services.agent_conversation_sev import AgentConversationService


class AgentChatWorkflowExecuteService:
    """Agent Chat 正式 workflow 执行服务。"""

    def __init__(self, router, planner, db: Session, conversation_service: AgentConversationService | None = None):
        self.router = router
        self.planner = planner
        self.db = db
        self.conversation_service = conversation_service

    def execute_workflow(self, request: AgentChatRequest) -> AgentChatResponse:
        conversation = None
        if self.conversation_service and request.conversation_id is not None:
            conversation, request = self.conversation_service.prepare_agent_request(request)
        agent_input = build_agent_input_from_chat_request(request)
        recorder = AgentEntryTraceRecorder(session_id=request.session_id)
        recorder.user_id = request.user_id
        recorder.record_input(agent_input)

        pipeline = AgentEntryPreviewPipeline(self.router, self.planner)
        router_result = pipeline._route(agent_input, recorder)
        plan = pipeline._plan(agent_input, router_result, recorder)
        param_validation = validate_plan_params(plan)
        recorder.record_param_validation(param_validation)
        source_validation = validate_param_sources(agent_input, router_result, plan)
        recorder.record_param_validation(source_validation)
        combined_param_validation = merge_param_validation_results(param_validation, source_validation)
        plan = apply_param_validation_to_plan(plan, combined_param_validation)
        plan = validate_plan_result(plan)
        plan_validation = build_plan_validation_result(plan, combined_param_validation)
        recorder.record_plan_validation(plan_validation)

        confirmation_card = build_confirmation_card(plan, plan_validation)
        recorder.record_confirmation_card(confirmation_card)
        registry = build_competitor_workflow_handler_registry(self.db)
        orchestrator = ExecutionOrchestrator(registry)
        execution_result = orchestrator.execute_plan(
            plan,
            plan_validation=plan_validation,
            mode=ExecutionMode.REAL,
            recorder=recorder,
            context={"db": self.db, "account_id": request.account_id, "request_context": request.context},
        )
        response = build_response_from_execution(plan, execution_result, confirmation_card).model_copy(
            update={
                "session_id": request.session_id,
                "router_result": router_result,
                "param_validation": combined_param_validation,
                "plan_validation": plan_validation,
                "trace_id": recorder.trace_id,
                "message": _message_for_workflow_response(execution_result),
            }
        )
        recorder.record_response(response)
        metadata = {
            **response.metadata,
            "business_result": _workflow_business_result(execution_result),
            "entry_trace": to_agent_trace_payload(recorder.build_trace()),
            "workflow_timeline": _workflow_timeline(execution_result, plan),
            "workflow_registry_actions": [
                Action.COLLECT_XHS_NOTES.value,
                Action.COLLECT_XHS_ACCOUNTS.value,
                Action.ANALYZE_COMPETITOR_DATA.value,
            ],
        }
        response = response.model_copy(update={"metadata": metadata})
        if conversation and self.conversation_service:
            return self.conversation_service.record_agent_response(conversation, request, response)
        return response


def build_agent_chat_workflow_execute_service(db: Session) -> AgentChatWorkflowExecuteService:
    """构建当前正式 Agent Chat workflow 执行服务。"""
    llm_client = _UnavailableLLMClient()
    return AgentChatWorkflowExecuteService(
        router=LLMUserInputRouter(llm_client),
        planner=LLMTaskPlanner(llm_client),
        db=db,
        conversation_service=AgentConversationService(db),
    )


class _UnavailableLLMClient:
    """确定性 workflow 分支之外的 LLM 调用快速失败。"""

    def generate_text(self, *args, **kwargs):
        raise RuntimeError("LLM is not configured for this deterministic workflow branch")


def _workflow_business_result(execution_result: PlanExecutionResult) -> dict | None:
    result = {}
    for step in execution_result.step_results:
        if step.action == Action.COLLECT_XHS_NOTES:
            result["xhs_notes_collection"] = step.output
        if step.action == Action.COLLECT_XHS_ACCOUNTS:
            result["xhs_accounts_collection"] = step.output
        if step.action == Action.ANALYZE_COMPETITOR_DATA:
            result["competitor_analysis"] = step.output
    return result or None


def _workflow_timeline(execution_result: PlanExecutionResult, plan: Plan | None = None) -> list[dict]:
    plan_steps = {step.step_no: step for step in plan.steps} if plan else {}
    return [
        {
            "step_order": step.step_order,
            "action": step.action.value,
            "status": step.output.get("status") if step.output.get("status") in {"PARTIAL_SUCCESS", "FAILED"} else step.status.value,
            "started_at": step.started_at.isoformat() if step.started_at else None,
            "finished_at": step.finished_at.isoformat() if step.finished_at else None,
            "duration_ms": _duration_ms(step.started_at, step.finished_at),
            "input_summary": _timeline_input_summary(plan_steps.get(step.step_order)),
            "output_summary": _timeline_output_summary(step.action, step.output, step.message),
            "provider": step.output.get("provider") or step.output.get("source_type"),
            "data_source": step.output.get("data_source"),
            "data_count": step.output.get("data_count") or {},
            "analysis_engine": step.output.get("analysis_engine"),
            "evidence_note_count": step.output.get("evidence_note_count"),
            "evidence_comment_count": step.output.get("evidence_comment_count"),
            "data_gaps": step.output.get("data_gaps") or [],
            "grounding_status": step.output.get("grounding_status"),
            "evidence_ids": step.output.get("evidence_ids") or (step.output.get("evidence") if isinstance(step.output.get("evidence"), dict) else {}),
            "created_ids": step.output.get("evidence_ids") or (step.output.get("evidence") if isinstance(step.output.get("evidence"), dict) else {}),
            "warnings": step.output.get("warnings") or [],
            "error_code": step.error_code or step.output.get("error_code"),
            "error_message": step.message if step.status.value == "FAILED" else step.output.get("error_message"),
        }
        for step in execution_result.step_results
    ]


def _timeline_input_summary(step: PlanStep | None) -> str | None:
    if not step:
        return None
    if step.action == Action.COLLECT_XHS_NOTES:
        return f"{len(step.input_params.get('note_urls') or [])} 个笔记链接"
    if step.action == Action.COLLECT_XHS_ACCOUNTS:
        return f"{len(step.input_params.get('competitor_account_ids_or_urls') or [])} 个同行账号"
    if step.action == Action.ANALYZE_COMPETITOR_DATA:
        return "分析已入库的真实竞品数据"
    return step.description


def _timeline_output_summary(action: Action, output: dict, message: str | None) -> str | None:
    counts = output.get("data_count") or {}
    if action == Action.COLLECT_XHS_NOTES:
        return (
            f"保存 {counts.get('notes_saved', 0)} 篇笔记 / "
            f"收到 {counts.get('comments_received', 0)} 条评论 / "
            f"保存 {counts.get('comments_saved', 0)} 条评论 / {counts.get('images', 0)} 个图片 URL"
        )
    if action == Action.COLLECT_XHS_ACCOUNTS:
        return f"保存 {counts.get('accounts_saved', 0)} 个账号 / {counts.get('recent_notes_saved', 0)} 篇近期笔记"
    if action == Action.ANALYZE_COMPETITOR_DATA:
        return f"分析 {output.get('note_count', 0)} 篇笔记 / {output.get('comment_count', 0)} 条评论，report_id={output.get('report_id', '-')}"
    return output.get("summary") or output.get("status") or message


def _duration_ms(started_at, finished_at) -> int | None:
    if not started_at or not finished_at:
        return None
    return max(0, int((finished_at - started_at).total_seconds() * 1000))


def _message_for_workflow_response(execution_result: PlanExecutionResult) -> str:
    if execution_result.status == ExecutionStatus.SUCCESS:
        return "竞品分析 workflow 执行完成。"
    if execution_result.status == ExecutionStatus.FAILED:
        return "竞品分析 workflow 执行失败，请展开时间线查看失败步骤。"
    return execution_result.message or "竞品分析 workflow 已停止。"
