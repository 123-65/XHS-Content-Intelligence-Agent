from datetime import UTC, datetime, timedelta
from uuid import uuid4

from pydantic import BaseModel

from app.agent.schemas.execution import WorkflowStatus
from app.agent.schemas.interaction import PendingInteraction
from app.agent.tools.definitions import ToolError
from app.agent.workflows.definitions import WorkflowId
from app.repositories.workflow_run_repo import WorkflowRunRepository, WorkflowRunRepositoryError
from app.runtime.workflow_contract_registry import get_runtime_contract
from app.schemas.workflow_run import WorkflowResumeSnapshot, WorkflowRunErrorSnapshot, WorkflowRunSnapshot


TERMINAL_STATUSES = frozenset(
    {WorkflowStatus.SUCCESS, WorkflowStatus.PARTIAL_SUCCESS, WorkflowStatus.FAILED, WorkflowStatus.CANCELLED}
)
WORKFLOW_EXECUTION_LEASE_SECONDS = 1800

ALLOWED_TRANSITIONS = {
    WorkflowStatus.PENDING: frozenset({WorkflowStatus.RUNNING, WorkflowStatus.CANCELLED}),
    WorkflowStatus.RUNNING: frozenset(
        {WorkflowStatus.WAITING_USER, WorkflowStatus.SUCCESS, WorkflowStatus.PARTIAL_SUCCESS, WorkflowStatus.FAILED, WorkflowStatus.CANCELLED}
    ),
    WorkflowStatus.WAITING_USER: frozenset({WorkflowStatus.RUNNING, WorkflowStatus.CANCELLED}),
}


class WorkflowRunServiceError(RuntimeError):
    """Workflow Run Service 的稳定业务错误。"""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


class WorkflowRunService:
    """负责 typed Workflow snapshot、状态迁移与乐观 checkpoint，不执行 Workflow。"""

    def __init__(self, db=None, repository: WorkflowRunRepository | None = None):
        self.repository = repository or WorkflowRunRepository(db)

    def create_run(
        self,
        workflow_name: WorkflowId | str,
        workflow_input: BaseModel,
        workflow_state: BaseModel,
        *,
        run_ref: str | None = None,
    ) -> WorkflowRunSnapshot:
        """用正式 typed Input 与初始 State 创建 durable Run。"""
        workflow_id, typed_input, typed_state = self._validate_contracts(workflow_name, workflow_input, workflow_state)
        if typed_state.status != WorkflowStatus.PENDING:
            raise WorkflowRunServiceError("INVALID_STATUS_TRANSITION", "新 Run 必须从 PENDING 创建。")
        account_id = self._account_id(typed_input, typed_state)
        try:
            record = self.repository.create_run(
                run_ref=run_ref or f"wfr_{uuid4().hex}",
                workflow_name=workflow_id.value,
                account_id=account_id,
                status=WorkflowStatus.PENDING.value,
                input_snapshot=typed_input.model_dump(mode="json"),
                state_snapshot=typed_state.model_dump(mode="json"),
                result_snapshot=None,
                pending_interaction=None,
                error_snapshot=None,
                warnings=list(getattr(typed_state, "warnings", [])),
            )
        except WorkflowRunRepositoryError as exc:
            raise WorkflowRunServiceError(exc.code, str(exc)) from exc
        return self._restore_record(record)

    def save_checkpoint(
        self,
        run_ref: str,
        expected_checkpoint_version: int,
        workflow_state: BaseModel,
        *,
        workflow_result: BaseModel | None = None,
        error: WorkflowRunErrorSnapshot | ToolError | None = None,
        error_source: str = "WORKFLOW",
        execution_token: str | None = None,
    ) -> WorkflowRunSnapshot:
        """校验状态语义后，以 CAS 保存一个完整 checkpoint。"""
        record = self._require_run(run_ref)
        current = WorkflowStatus(record.status)
        if current in TERMINAL_STATUSES:
            raise WorkflowRunServiceError("WORKFLOW_RUN_TERMINAL", "Terminal Workflow Run 不允许继续保存或恢复。")
        if current == WorkflowStatus.RUNNING and execution_token is not None and record.execution_token != execution_token:
            raise WorkflowRunServiceError("WORKFLOW_EXECUTION_FENCED", "Workflow execution token is no longer current.")
        if record.checkpoint_version != expected_checkpoint_version:
            raise WorkflowRunServiceError("WORKFLOW_CHECKPOINT_CONFLICT", "Workflow checkpoint 已被其他请求更新。")
        workflow_id = WorkflowId(record.workflow_name)
        contract = get_runtime_contract(workflow_id)
        state = contract.state_type.model_validate(workflow_state)
        target = state.status
        self._validate_transition(current, target)
        pending = getattr(state, "pending_interaction", None)
        result_snapshot, error_snapshot = self._validate_outcome(
            contract.result_type, target, workflow_result, error, error_source, pending
        )
        fields = {
            "status": target.value,
            "state_snapshot": state.model_dump(mode="json"),
            "result_snapshot": result_snapshot,
            "pending_interaction": pending.model_dump(mode="json") if pending else None,
            "error_snapshot": error_snapshot,
            "warnings": list(getattr(state, "warnings", [])),
            "execution_token": None if target != WorkflowStatus.RUNNING else record.execution_token,
            "lease_expires_at": None if target != WorkflowStatus.RUNNING else record.lease_expires_at,
        }
        try:
            if target in {WorkflowStatus.SUCCESS, WorkflowStatus.PARTIAL_SUCCESS}:
                saved = self.repository.mark_completed(run_ref, expected_checkpoint_version, expected_execution_token=execution_token, **fields)
            elif target == WorkflowStatus.FAILED:
                saved = self.repository.mark_failed(run_ref, expected_checkpoint_version, expected_execution_token=execution_token, **fields)
            elif target == WorkflowStatus.CANCELLED:
                saved = self.repository.mark_cancelled(run_ref, expected_checkpoint_version, expected_execution_token=execution_token, **fields)
            else:
                saved = self.repository.save_checkpoint(run_ref, expected_checkpoint_version, expected_execution_token=execution_token, **fields)
        except WorkflowRunRepositoryError as exc:
            raise WorkflowRunServiceError(exc.code, str(exc)) from exc
        return self._restore_record(saved)

    def mark_running(self, run_ref: str, expected_checkpoint_version: int, workflow_state: BaseModel, *, execution_mode=None, workflow_input=None) -> WorkflowRunSnapshot:
        """将 PENDING 或 WAITING_USER checkpoint 转为 RUNNING。"""
        if workflow_state.status not in {WorkflowStatus.PENDING, WorkflowStatus.WAITING_USER, WorkflowStatus.RUNNING}:
            raise WorkflowRunServiceError("INVALID_STATUS_TRANSITION", "mark_running requires a recoverable pre-execution State.")
        token = uuid4().hex
        lease = datetime.now(UTC).replace(tzinfo=None) + timedelta(seconds=WORKFLOW_EXECUTION_LEASE_SECONDS)
        record = self._require_run(run_ref)
        execution_mode = execution_mode or ("RESUME" if WorkflowStatus(record.status) == WorkflowStatus.WAITING_USER else "START")
        expected_status = WorkflowStatus.PENDING if execution_mode == "START" else WorkflowStatus.WAITING_USER
        if WorkflowStatus(record.status) != expected_status:
            if WorkflowStatus(record.status) in TERMINAL_STATUSES:
                raise WorkflowRunServiceError("WORKFLOW_RUN_TERMINAL", "Terminal Workflow Run cannot be claimed.")
            raise WorkflowRunServiceError("INVALID_STATUS_TRANSITION", "Workflow Run cannot be claimed in its current status.")
        fields = {
            "status": WorkflowStatus.RUNNING.value,
            "state_snapshot": workflow_state.model_dump(mode="json"),
            "pending_interaction": None,
            "execution_token": token,
            "lease_expires_at": lease,
            "execution_mode": execution_mode,
        }
        if workflow_input is not None:
            fields["input_snapshot"] = workflow_input.model_dump(mode="json")
        try:
            saved = self.repository.save_checkpoint(run_ref, expected_checkpoint_version, **fields)
        except WorkflowRunRepositoryError as exc:
            raise WorkflowRunServiceError(exc.code, str(exc)) from exc
        return self._restore_record(saved)

    def claim_recovery(self, run_ref: str) -> WorkflowRunSnapshot:
        record = self._require_run(run_ref)
        now = datetime.now(UTC).replace(tzinfo=None)
        if WorkflowStatus(record.status) != WorkflowStatus.RUNNING or not record.lease_expires_at or record.lease_expires_at >= now:
            raise WorkflowRunServiceError("WORKFLOW_RUN_NOT_RECOVERABLE", "Workflow Run is not an expired RUNNING execution.")
        token = uuid4().hex
        try:
            saved = self.repository.save_checkpoint(
                run_ref, record.checkpoint_version, expected_execution_token=record.execution_token,
                execution_token=token,
                lease_expires_at=now + timedelta(seconds=WORKFLOW_EXECUTION_LEASE_SECONDS),
            )
        except WorkflowRunRepositoryError as exc:
            raise WorkflowRunServiceError(exc.code, str(exc)) from exc
        return self._restore_record(saved)

    def load_for_resume(self, run_ref: str) -> WorkflowResumeSnapshot:
        """读取未来 Runtime Resume 所需的 typed Input、State 与版本。"""
        record = self._require_run(run_ref)
        status = WorkflowStatus(record.status)
        if status in TERMINAL_STATUSES:
            raise WorkflowRunServiceError("WORKFLOW_RUN_TERMINAL", "Terminal Workflow Run 不可 Resume。")
        restored = self._restore_record(record)
        return WorkflowResumeSnapshot(
            run_ref=restored.run_ref,
            workflow_name=restored.workflow_name,
            account_id=restored.account_id,
            input=restored.input,
            state=restored.state,
            checkpoint_version=restored.checkpoint_version,
            pending_interaction=restored.pending_interaction,
        )

    def get_run(self, run_ref: str) -> WorkflowRunSnapshot:
        """读取 Run 的完整 typed snapshot，包括终态 Result 或 Error。"""
        return self._restore_record(self._require_run(run_ref))

    def _restore_record(self, record) -> WorkflowRunSnapshot:
        workflow_id = WorkflowId(record.workflow_name)
        contract = get_runtime_contract(workflow_id)
        return WorkflowRunSnapshot(
            run_ref=record.run_ref,
            workflow_name=workflow_id,
            account_id=record.account_id,
            status=WorkflowStatus(record.status),
            input=contract.input_type.model_validate(record.input_snapshot),
            state=contract.state_type.model_validate(record.state_snapshot),
            result=contract.result_type.model_validate(record.result_snapshot) if record.result_snapshot else None,
            pending_interaction=PendingInteraction.model_validate(record.pending_interaction) if record.pending_interaction else None,
            error=WorkflowRunErrorSnapshot.model_validate(record.error_snapshot) if record.error_snapshot else None,
            warnings=list(record.warnings or []),
            checkpoint_version=record.checkpoint_version,
            created_at=record.created_at,
            updated_at=record.updated_at,
            completed_at=record.completed_at,
            execution_token=record.execution_token,
            lease_expires_at=record.lease_expires_at,
            execution_mode=record.execution_mode,
        )

    def _validate_contracts(self, workflow_name, workflow_input, workflow_state):
        try:
            workflow_id = WorkflowId(workflow_name)
            contract = get_runtime_contract(workflow_id)
            return workflow_id, contract.input_type.model_validate(workflow_input), contract.state_type.model_validate(workflow_state)
        except (ValueError, TypeError) as exc:
            raise WorkflowRunServiceError("WORKFLOW_CONTRACT_INVALID", str(exc)) from exc

    @staticmethod
    def _validate_transition(current, target):
        if target not in ALLOWED_TRANSITIONS.get(current, frozenset()):
            raise WorkflowRunServiceError("INVALID_STATUS_TRANSITION", f"不允许 {current.value} → {target.value}。")

    @staticmethod
    def _validate_outcome(result_type, status, result, error, error_source, pending):
        if status == WorkflowStatus.WAITING_USER:
            if pending is None:
                raise WorkflowRunServiceError("PENDING_INTERACTION_REQUIRED", "WAITING_USER 必须包含 PendingInteraction。")
        elif pending is not None:
            raise WorkflowRunServiceError("PENDING_INTERACTION_FORBIDDEN", "非 WAITING_USER 不应保存 PendingInteraction。")
        if status in {WorkflowStatus.SUCCESS, WorkflowStatus.PARTIAL_SUCCESS}:
            if result is None:
                raise WorkflowRunServiceError("WORKFLOW_RESULT_REQUIRED", "成功终态必须包含 typed Result。")
            return result_type.model_validate(result).model_dump(mode="json"), None
        if status == WorkflowStatus.FAILED:
            if error is None:
                raise WorkflowRunServiceError("WORKFLOW_ERROR_REQUIRED", "FAILED 必须包含结构化 Error。")
            if isinstance(error, ToolError):
                error = WorkflowRunErrorSnapshot(**error.model_dump(), source=error_source)
            return None, WorkflowRunErrorSnapshot.model_validate(error).model_dump(mode="json")
        if result is not None or error is not None:
            raise WorkflowRunServiceError("WORKFLOW_OUTCOME_FORBIDDEN", "非终态不能保存 Result 或 Error。")
        return None, None

    def _require_run(self, run_ref):
        record = self.repository.get_by_run_ref(run_ref)
        if record is None:
            raise WorkflowRunServiceError("WORKFLOW_RUN_NOT_FOUND", "Workflow Run 不存在。")
        return record

    @staticmethod
    def _account_id(workflow_input, workflow_state):
        input_account = getattr(workflow_input, "account_ref", None)
        state_account = getattr(workflow_state, "account_ref", None)
        if input_account is None or input_account != state_account:
            raise WorkflowRunServiceError("WORKFLOW_ACCOUNT_MISMATCH", "Input 与 State account_ref 不一致。")
        return input_account
