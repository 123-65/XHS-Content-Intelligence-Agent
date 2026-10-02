import logging
from dataclasses import replace
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.agent.schemas.execution import WorkflowStatus
from app.agent.schemas.interaction import PendingInteraction
from app.agent.tools.definitions import ToolError
from app.agent.tools.execution_context import RuntimeExecutionIdentity, ToolExecutionContext
from app.agent.workflows.implementation_registry import build_workflow_handler
from app.runtime.workflow_contract_registry import get_runtime_contract
from app.schemas.workflow_run import WorkflowRunErrorSnapshot
from app.services.workflow_run_sev import WorkflowRunService, WorkflowRunServiceError


logger = logging.getLogger(__name__)


class WorkflowResumeRequest(BaseModel):
    """跨请求 Resume 的唯一不可信输入；内部 State 永远不接受用户提交。"""

    model_config = ConfigDict(extra="forbid")
    run_ref: str = Field(min_length=1)
    expected_checkpoint_version: int = Field(ge=1)
    new_input: dict[str, Any]


class WorkflowResumeResult(BaseModel):
    """不暴露 ORM、Handler、Scope 或 traceback 的 Runtime Resume 结果。"""

    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)
    run_ref: str
    workflow_name: str
    status: WorkflowStatus
    checkpoint_version: int
    pending_interaction: PendingInteraction | None = None
    result: Any | None = None
    warnings: list[str] = Field(default_factory=list)
    error: WorkflowRunErrorSnapshot | None = None


class WorkflowResumeService:
    """协调 durable load、CAS claim、Workflow.resume 与 final checkpoint。"""

    def __init__(self, run_service: WorkflowRunService):
        self.run_service = run_service

    def resume(self, request: WorkflowResumeRequest, execution_context: ToolExecutionContext) -> WorkflowResumeResult:
        """只允许 WAITING_USER Run 在当前可信 ToolExecutionContext 中恢复。"""
        snapshot = self._load_waiting(request)
        typed_input = self._typed_new_input(snapshot, request.new_input)
        claimed = self.run_service.mark_running(
            request.run_ref,
            request.expected_checkpoint_version,
            snapshot.state,
            execution_mode="RESUME",
            workflow_input=typed_input,
        )
        execution_context = replace(
            execution_context,
            runtime_identity=RuntimeExecutionIdentity(
                run_ref=snapshot.run_ref,
                workflow_name=snapshot.workflow_name.value,
            ),
        )
        try:
            handler = build_workflow_handler(snapshot.workflow_name)
            workflow_result = handler.resume(claimed.state, typed_input, execution_context)
            saved = self._save_result(request.run_ref, claimed.checkpoint_version, workflow_result, claimed.execution_token)
        except WorkflowRunServiceError:
            raise
        except Exception as exc:
            logger.exception("Workflow resume execution failed for run_ref=%s", request.run_ref)
            failed_state = claimed.state.model_copy(
                update={"status": WorkflowStatus.FAILED, "pending_interaction": None}, deep=True
            )
            safe_error = ToolError(
                code="WORKFLOW_RESUME_EXECUTION_ERROR",
                category="RUNTIME",
                retryable=False,
                safe_message="Workflow 恢复执行失败。",
            )
            try:
                saved = self.run_service.save_checkpoint(
                    request.run_ref,
                    claimed.checkpoint_version,
                    failed_state,
                    error=safe_error,
                    error_source="WorkflowResumeService",
                    execution_token=claimed.execution_token,
                )
            except Exception:
                logger.exception("Failed to persist resume failure for run_ref=%s", request.run_ref)
                raise
        return self._result(saved)

    def _load_waiting(self, request):
        snapshot = self.run_service.get_run(request.run_ref)
        if snapshot.status == WorkflowStatus.RUNNING:
            raise WorkflowRunServiceError("WORKFLOW_RUN_ALREADY_RUNNING", "Workflow Run 已在执行中。")
        if snapshot.status in {
            WorkflowStatus.SUCCESS,
            WorkflowStatus.PARTIAL_SUCCESS,
            WorkflowStatus.FAILED,
            WorkflowStatus.CANCELLED,
        }:
            raise WorkflowRunServiceError("WORKFLOW_RUN_TERMINAL", "Terminal Workflow Run 不可 Resume。")
        if snapshot.status != WorkflowStatus.WAITING_USER:
            raise WorkflowRunServiceError("WORKFLOW_RUN_NOT_WAITING", "只有 WAITING_USER Workflow Run 可以 Resume。")
        if snapshot.pending_interaction is None or snapshot.state.pending_interaction is None:
            raise WorkflowRunServiceError("WORKFLOW_RUN_CORRUPTED", "WAITING_USER Run 缺少 PendingInteraction。")
        if snapshot.pending_interaction != snapshot.state.pending_interaction:
            raise WorkflowRunServiceError("WORKFLOW_RUN_CORRUPTED", "PendingInteraction checkpoint 不一致。")
        if snapshot.checkpoint_version != request.expected_checkpoint_version:
            raise WorkflowRunServiceError("WORKFLOW_CHECKPOINT_CONFLICT", "Workflow checkpoint 已被其他请求更新。")
        return snapshot

    @staticmethod
    def _typed_new_input(snapshot, new_input):
        contract = get_runtime_contract(snapshot.workflow_name)
        submitted_account = new_input.get("account_ref")
        if submitted_account is not None and submitted_account != snapshot.account_id:
            raise WorkflowRunServiceError("WORKFLOW_RUN_ACCOUNT_MISMATCH", "Resume account_ref 与 durable Run 不一致。")
        merged = snapshot.input.model_dump(mode="json")
        merged.update(new_input)
        merged["account_ref"] = snapshot.account_id
        try:
            typed = contract.input_type.model_validate(merged)
        except ValidationError as exc:
            raise WorkflowRunServiceError("WORKFLOW_RESUME_INPUT_INVALID", str(exc)) from exc
        if typed.account_ref != snapshot.account_id or snapshot.state.account_ref != snapshot.account_id:
            raise WorkflowRunServiceError("WORKFLOW_RUN_ACCOUNT_MISMATCH", "Resume Input、State 与 durable account identity 不一致。")
        return typed

    def _save_result(self, run_ref, claimed_version, result, execution_token):
        if result.status == WorkflowStatus.WAITING_USER:
            return self.run_service.save_checkpoint(run_ref, claimed_version, result.state, execution_token=execution_token)
        if result.status in {WorkflowStatus.SUCCESS, WorkflowStatus.PARTIAL_SUCCESS}:
            return self.run_service.save_checkpoint(
                run_ref, claimed_version, result.state, workflow_result=result, execution_token=execution_token
            )
        if result.status == WorkflowStatus.FAILED:
            error = result.error or ToolError(
                code="WORKFLOW_FAILED",
                category="WORKFLOW",
                retryable=False,
                safe_message="Workflow 执行失败。",
            )
            return self.run_service.save_checkpoint(
                run_ref, claimed_version, result.state, error=error, error_source="Workflow", execution_token=execution_token
            )
        raise WorkflowRunServiceError("WORKFLOW_RESUME_RESULT_INVALID", f"Resume 返回不支持的状态：{result.status}")

    def _result(self, saved):
        return WorkflowResumeResult(
            run_ref=saved.run_ref,
            workflow_name=saved.workflow_name.value,
            status=saved.status,
            checkpoint_version=saved.checkpoint_version,
            pending_interaction=saved.pending_interaction,
            result=saved.result,
            warnings=saved.warnings,
            error=saved.error,
        )
