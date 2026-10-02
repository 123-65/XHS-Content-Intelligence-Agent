import logging
from dataclasses import replace
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.agent.schemas.execution import WorkflowStatus
from app.agent.schemas.interaction import PendingInteraction
from app.agent.tools.definitions import ToolError
from app.agent.tools.execution_context import RuntimeExecutionIdentity, ToolExecutionContext
from app.agent.workflows.definitions import WorkflowId
from app.agent.workflows.implementation_registry import build_workflow_handler
from app.runtime.workflow_contract_registry import get_runtime_contract
from app.runtime.workflow_initial_state_registry import build_initial_state
from app.runtime.workflow_resume import WorkflowResumeRequest, WorkflowResumeService
from app.runtime.workflow_recovery import WorkflowRecoveryService
from app.schemas.workflow_run import WorkflowRunErrorSnapshot, WorkflowRunSnapshot
from app.services.workflow_run_sev import WorkflowRunService, WorkflowRunServiceError


logger = logging.getLogger(__name__)


class WorkflowStartRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    workflow_name: WorkflowId
    input: dict[str, Any]


class AgentRuntimeResult(BaseModel):
    """Public-safe runtime view; durable input/state and trusted objects stay internal."""

    model_config = ConfigDict(extra="forbid")
    run_ref: str
    workflow_name: str
    account_ref: int
    status: WorkflowStatus
    checkpoint_version: int
    pending_interaction: PendingInteraction | None = None
    result: Any | None = None
    warnings: list[str] = Field(default_factory=list)
    error: WorkflowRunErrorSnapshot | None = None
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None = None


class AgentRuntimeError(RuntimeError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


class AgentRuntime:
    """Single internal entry point for durable Workflow start, resume, and inspection."""

    def __init__(
        self,
        run_service: WorkflowRunService,
        resume_service: WorkflowResumeService | None = None,
    ):
        self.run_service = run_service
        self.resume_service = resume_service or WorkflowResumeService(run_service)
        self.recovery_service = WorkflowRecoveryService(run_service)

    def start(self, request: WorkflowStartRequest, execution_context: ToolExecutionContext) -> AgentRuntimeResult:
        try:
            contract = get_runtime_contract(request.workflow_name)
            typed_input = contract.input_type.model_validate(request.input)
            initial_state = build_initial_state(request.workflow_name, typed_input)
        except (ValueError, TypeError, ValidationError) as exc:
            raise AgentRuntimeError("WORKFLOW_START_INPUT_INVALID", str(exc)) from exc

        created = self.run_service.create_run(request.workflow_name, typed_input, initial_state)
        claimed = self.run_service.mark_running(created.run_ref, created.checkpoint_version, created.state, execution_mode="START")
        execution_context = replace(
            execution_context,
            runtime_identity=RuntimeExecutionIdentity(run_ref=created.run_ref, workflow_name=request.workflow_name.value),
        )

        try:
            handler = build_workflow_handler(request.workflow_name)
            workflow_result = handler.execute(typed_input, execution_context)
        except Exception:
            logger.exception("Workflow start execution failed for run_ref=%s", created.run_ref)
            failed_state = claimed.state.model_copy(
                update={"status": WorkflowStatus.FAILED, "pending_interaction": None}, deep=True
            )
            safe_error = ToolError(
                code="WORKFLOW_EXECUTION_ERROR",
                category="RUNTIME",
                retryable=False,
                safe_message="Workflow execution failed.",
            )
            saved = self.run_service.save_checkpoint(
                created.run_ref,
                claimed.checkpoint_version,
                failed_state,
                error=safe_error,
                error_source="AgentRuntime",
                execution_token=claimed.execution_token,
            )
            return self._result(saved)

        saved = self._save_result(created.run_ref, claimed.checkpoint_version, workflow_result, claimed.execution_token)
        return self._result(saved)

    def resume(self, request: WorkflowResumeRequest, execution_context: ToolExecutionContext) -> AgentRuntimeResult:
        resumed = self.resume_service.resume(request, execution_context)
        return self._result(self.run_service.get_run(resumed.run_ref))

    def get_run(self, run_ref: str) -> AgentRuntimeResult:
        return self._result(self.run_service.get_run(run_ref))

    def recover(self, run_ref: str, execution_context: ToolExecutionContext) -> AgentRuntimeResult:
        return self._result(self.recovery_service.recover(run_ref, execution_context))

    def _save_result(self, run_ref: str, claimed_version: int, result: BaseModel, execution_token: str) -> WorkflowRunSnapshot:
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
                safe_message="Workflow execution failed.",
            )
            return self.run_service.save_checkpoint(
                run_ref, claimed_version, result.state, error=error, error_source="Workflow", execution_token=execution_token
            )
        raise WorkflowRunServiceError(
            "WORKFLOW_START_RESULT_INVALID", f"Unsupported Workflow status: {result.status}"
        )

    @staticmethod
    def _result(saved: WorkflowRunSnapshot) -> AgentRuntimeResult:
        return AgentRuntimeResult(
            run_ref=saved.run_ref,
            workflow_name=saved.workflow_name.value,
            account_ref=saved.account_id,
            status=saved.status,
            checkpoint_version=saved.checkpoint_version,
            pending_interaction=saved.pending_interaction,
            result=saved.result,
            warnings=saved.warnings,
            error=saved.error,
            created_at=saved.created_at,
            updated_at=saved.updated_at,
            completed_at=saved.completed_at,
        )
