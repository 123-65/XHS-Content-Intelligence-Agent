from sqlalchemy.orm import Session

from app.agent.product_entry.business_handlers import build_competitor_workflow_handler_registry, build_readonly_action_handler_registry
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
from app.llm.client import LLMClient
from app.services.agent_conversation_sev import AgentConversationService


class AgentChatPreviewService:
    """Agent Chat 预览服务，封装入口 dry-run pipeline。"""

    def __init__(self, pipeline: AgentEntryPreviewPipeline, conversation_service: AgentConversationService | None = None):
        """初始化预览服务。"""
        self.pipeline = pipeline
        self.conversation_service = conversation_service

    def preview(self, request: AgentChatRequest) -> AgentChatResponse:
        """处理 Agent Chat dry-run 请求，返回统一响应。"""
        if not self.conversation_service or request.conversation_id is None:
            return self.pipeline.preview(request)
        conversation, merged_request = self.conversation_service.prepare_agent_request(request)
        response = self.pipeline.preview(merged_request)
        return self.conversation_service.record_agent_response(conversation, merged_request, response)


def build_agent_chat_preview_service(db: Session | None = None) -> AgentChatPreviewService:
    """构建 Agent Chat 预览服务。"""
    llm_client = LLMClient()
    pipeline = AgentEntryPreviewPipeline(
        router=LLMUserInputRouter(llm_client),
        planner=LLMTaskPlanner(llm_client),
    )
    return AgentChatPreviewService(pipeline, AgentConversationService(db) if db else None)


class AgentChatReadonlyExecuteService:
    """Agent Chat 只读执行服务，仅允许白名单只读 Action 进入 REAL 模式。"""

    def __init__(self, router, planner, db: Session, conversation_service: AgentConversationService | None = None):
        """初始化只读执行服务。"""
        self.router = router
        self.planner = planner
        self.db = db
        self.conversation_service = conversation_service

    def execute_readonly(self, request: AgentChatRequest) -> AgentChatResponse:
        """执行只读 Agent Action，仅允许只读白名单 Action 进入 REAL。"""
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

        registry = build_readonly_action_handler_registry(self.db)
        orchestrator = ExecutionOrchestrator(registry)
        execution_result = orchestrator.execute_plan(
            plan,
            plan_validation=plan_validation,
            mode=ExecutionMode.REAL,
            recorder=recorder,
            context={"db": self.db, "account_id": request.account_id, "request_context": request.context},
        )
        response = build_response_from_execution(plan, execution_result, confirmation_card)
        response = response.model_copy(
            update={
                "session_id": request.session_id,
                "router_result": router_result,
                "param_validation": combined_param_validation,
                "plan_validation": plan_validation,
                "trace_id": recorder.trace_id,
                "message": _message_for_readonly_response(response, execution_result),
            }
        )
        recorder.record_response(response)
        trace_payload = to_agent_trace_payload(recorder.build_trace())
        metadata = {
            **response.metadata,
            "business_result": _business_result(execution_result),
            "entry_trace": trace_payload,
            "readonly_registry_actions": [
                Action.NOOP.value,
                Action.ASK_CLARIFICATION.value,
                Action.QUERY_ACCOUNT_PROFILE.value,
                Action.QUERY_COMPETITOR_EVIDENCE.value,
                Action.QUERY_COMMENT_INSIGHT.value,
                Action.QUERY_STRATEGY_MEMORY.value,
                Action.PREVIEW_DRAFT_CONTEXT.value,
            ],
        }
        response = response.model_copy(update={"metadata": metadata})
        if conversation and self.conversation_service:
            return self.conversation_service.record_agent_response(conversation, request, response)
        return response


class AgentChatWorkflowExecuteService:
    """Agent Chat workflow execution service for real collection plus analysis."""

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


def build_agent_chat_readonly_execute_service(db: Session) -> AgentChatReadonlyExecuteService:
    """构建 Agent Chat 只读执行服务。"""
    llm_client = LLMClient()
    return AgentChatReadonlyExecuteService(
        router=LLMUserInputRouter(llm_client),
        planner=LLMTaskPlanner(llm_client),
        db=db,
        conversation_service=AgentConversationService(db),
    )


def build_agent_chat_workflow_execute_service(db: Session) -> AgentChatWorkflowExecuteService:
    """Build Agent Chat workflow execution service."""
    llm_client = _UnavailableLLMClient()
    return AgentChatWorkflowExecuteService(
        router=LLMUserInputRouter(llm_client),
        planner=LLMTaskPlanner(llm_client),
        db=db,
        conversation_service=AgentConversationService(db),
    )


class _UnavailableLLMClient:
    """Fail-fast placeholder; deterministic workflow branches do not call it."""

    def generate_text(self, *args, **kwargs):
        raise RuntimeError("LLM is not configured for this deterministic workflow branch")


def _business_result(execution_result: PlanExecutionResult) -> dict | None:
    """提取只读业务结果，供前端展示。"""
    if execution_result.status != ExecutionStatus.SUCCESS:
        return None
    result = {}
    for step in execution_result.step_results:
        if step.action == Action.QUERY_ACCOUNT_PROFILE and step.output:
            result["account_profile"] = step.output
        if step.action == Action.QUERY_COMPETITOR_EVIDENCE and step.output:
            result["competitor_evidence"] = step.output
        if step.action == Action.QUERY_COMMENT_INSIGHT and step.output:
            result["comment_insight"] = step.output
        if step.action == Action.QUERY_STRATEGY_MEMORY and step.output:
            result["strategy_memory"] = step.output
        if step.action == Action.PREVIEW_DRAFT_CONTEXT and step.output:
            result["draft_context_preview"] = step.output
    if not result:
        return None
    if set(result) == {"account_profile"}:
        return {**result["account_profile"], **result}
    return result


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
            "status": step.status.value,
            "started_at": step.started_at.isoformat() if step.started_at else None,
            "finished_at": step.finished_at.isoformat() if step.finished_at else None,
            "duration_ms": _duration_ms(step.started_at, step.finished_at),
            "input_summary": _timeline_input_summary(plan_steps.get(step.step_order)),
            "output_summary": _timeline_output_summary(step.action, step.output, step.message),
            "provider": step.output.get("provider") or step.output.get("source_type"),
            "data_source": step.output.get("data_source"),
            "data_count": step.output.get("data_count") or {},
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
        return f"保存 {counts.get('notes_saved', 0)} 篇笔记 / {counts.get('comments_saved', 0)} 条评论 / {counts.get('images', 0)} 个图片 URL"
    if action == Action.COLLECT_XHS_ACCOUNTS:
        return f"保存 {counts.get('accounts_saved', 0)} 个账号 / {counts.get('recent_notes_saved', 0)} 篇近期笔记"
    if action == Action.ANALYZE_COMPETITOR_DATA:
        return f"分析 {output.get('note_count', 0)} 篇笔记 / {output.get('comment_count', 0)} 条评论，report_id={output.get('report_id', '-')}"
    return output.get("summary") or output.get("status") or message


def _duration_ms(started_at, finished_at) -> int | None:
    if not started_at or not finished_at:
        return None
    return max(0, int((finished_at - started_at).total_seconds() * 1000))


def _message_for_readonly_response(response: AgentChatResponse, execution_result: PlanExecutionResult) -> str:
    """为只读执行结果生成用户可读消息。"""
    if execution_result.status == ExecutionStatus.SUCCESS:
        return "只读查询执行完成。"
    return response.message


def _message_for_workflow_response(execution_result: PlanExecutionResult) -> str:
    if execution_result.status == ExecutionStatus.SUCCESS:
        return "竞品分析 workflow 执行完成。"
    if execution_result.status == ExecutionStatus.FAILED:
        return "竞品分析 workflow 执行失败，请展开时间线查看失败步骤。"
    return execution_result.message or "竞品分析 workflow 已停止。"
