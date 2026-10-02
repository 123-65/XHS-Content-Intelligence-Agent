import logging
from dataclasses import replace

from app.agent.schemas.execution import WorkflowStatus
from app.agent.tools.definitions import ToolError
from app.agent.tools.execution_context import RuntimeExecutionIdentity, ToolExecutionContext
from app.agent.workflows.implementation_registry import build_workflow_handler
from app.services.workflow_run_sev import WorkflowRunService, WorkflowRunServiceError

logger = logging.getLogger(__name__)


class WorkflowRecoveryService:
    def __init__(self, run_service: WorkflowRunService):
        self.run_service = run_service 

    def recover(self, run_ref: str, execution_context: ToolExecutionContext):
        claimed = self.run_service.claim_recovery(run_ref)
        context = replace(execution_context, runtime_identity=RuntimeExecutionIdentity(run_ref, claimed.workflow_name.value))
        handler = build_workflow_handler(claimed.workflow_name)
        try:
            if claimed.execution_mode == "START":
                result = handler.execute(claimed.input, context)
            elif claimed.execution_mode == "RESUME":
                result = handler.resume(claimed.state, claimed.input, context)
            else:
                raise WorkflowRunServiceError("WORKFLOW_RECOVERY_MODE_INVALID", "Durable execution mode is invalid.")
        except WorkflowRunServiceError:
            raise
        except Exception:
            logger.exception("Workflow recovery failed for run_ref=%s", run_ref)
            failed = claimed.state.model_copy(update={"status": WorkflowStatus.FAILED, "pending_interaction": None}, deep=True)
            return self.run_service.save_checkpoint(
                run_ref, claimed.checkpoint_version, failed,
                error=ToolError(code="WORKFLOW_RECOVERY_EXECUTION_ERROR", category="RUNTIME", retryable=False, safe_message="Workflow recovery failed."),
                error_source="WorkflowRecoveryService", execution_token=claimed.execution_token,
            )
        return self._save(run_ref, claimed, result)

    def _save(self, run_ref, claimed, result):
        kwargs = {"execution_token": claimed.execution_token}
        if result.status == WorkflowStatus.WAITING_USER:
            return self.run_service.save_checkpoint(run_ref, claimed.checkpoint_version, result.state, **kwargs)
        if result.status in {WorkflowStatus.SUCCESS, WorkflowStatus.PARTIAL_SUCCESS}:
            return self.run_service.save_checkpoint(run_ref, claimed.checkpoint_version, result.state, workflow_result=result, **kwargs)
        if result.status == WorkflowStatus.FAILED:
            error = result.error or ToolError(code="WORKFLOW_FAILED", category="WORKFLOW", retryable=False, safe_message="Workflow execution failed.")
            return self.run_service.save_checkpoint(run_ref, claimed.checkpoint_version, result.state, error=error, error_source="Workflow", **kwargs)
        raise WorkflowRunServiceError("WORKFLOW_RECOVERY_RESULT_INVALID", f"Unsupported recovery status: {result.status}")
