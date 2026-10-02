from datetime import UTC, datetime, timedelta

import pytest

from app.agent.schemas.execution import WorkflowStatus
from app.agent.tools.execution_context import ToolExecutionContext
from app.agent.workflows.definitions import WorkflowId
from app.agent.workflows.research import ResearchWorkflowInput, ResearchWorkflowResult, ResearchWorkflowState
from app.core.database import SessionLocal
from app.models.account import AccountProfile
from app.models.workflow_run import WorkflowRun
from app.runtime.workflow_recovery import WorkflowRecoveryService
from app.services.workflow_run_sev import WorkflowRunService, WorkflowRunServiceError


@pytest.fixture
def account_id():
    with SessionLocal() as db:
        account = AccountProfile(account_name="Recovery Test", positioning="test", target_audience="test")
        db.add(account)
        db.commit()
        db.refresh(account)
        return account.id


def _running(account_id):
    with SessionLocal() as db:
        service = WorkflowRunService(db)
        created = service.create_run(
            WorkflowId.RESEARCH_V1,
            ResearchWorkflowInput(account_ref=account_id, research_goal="recover"),
            ResearchWorkflowState(account_ref=account_id, research_goal="recover"),
        )
        return service.mark_running(created.run_ref, 1, created.state, execution_mode="START")


def _expire(run_ref):
    with SessionLocal() as db:
        record = db.query(WorkflowRun).filter_by(run_ref=run_ref).one()
        record.lease_expires_at = datetime.now(UTC).replace(tzinfo=None) - timedelta(seconds=1)
        db.commit()


def test_start_claim_has_lease_and_nonexpired_recovery_rejected(account_id):
    running = _running(account_id)
    assert running.execution_token and running.lease_expires_at and running.execution_mode == "START"
    with SessionLocal() as db, pytest.raises(WorkflowRunServiceError) as rejected:
        WorkflowRunService(db).claim_recovery(running.run_ref)
    assert rejected.value.code == "WORKFLOW_RUN_NOT_RECOVERABLE"


def test_recovery_rotates_token_fences_old_worker_and_can_finish(monkeypatch, account_id):
    running = _running(account_id)
    old_token = running.execution_token
    _expire(running.run_ref)
    with SessionLocal() as db:
        service = WorkflowRunService(db)
        claimed = service.claim_recovery(running.run_ref)
        assert claimed.execution_token != old_token and claimed.checkpoint_version == 3
        success_state = claimed.state.model_copy(update={"status": WorkflowStatus.SUCCESS})
        result = ResearchWorkflowResult(status=WorkflowStatus.SUCCESS, state=success_state)
        with pytest.raises(WorkflowRunServiceError) as fenced:
            service.save_checkpoint(running.run_ref, 2, success_state, workflow_result=result, execution_token=old_token)
        assert fenced.value.code == "WORKFLOW_EXECUTION_FENCED"
        completed = service.save_checkpoint(running.run_ref, 3, success_state, workflow_result=result, execution_token=claimed.execution_token)
        assert completed.status == WorkflowStatus.SUCCESS
        assert completed.execution_token is None and completed.lease_expires_at is None


def test_recovery_uses_execute_and_current_context(monkeypatch, account_id):
    running = _running(account_id)
    _expire(running.run_ref)
    seen = []

    class Handler:
        def execute(self, data, context):
            seen.append((data, context))
            state = ResearchWorkflowState(account_ref=data.account_ref, research_goal=data.research_goal, status=WorkflowStatus.SUCCESS)
            return ResearchWorkflowResult(status=WorkflowStatus.SUCCESS, state=state)

    monkeypatch.setattr("app.runtime.workflow_recovery.build_workflow_handler", lambda selected: Handler())
    current = ToolExecutionContext(db=object())
    with SessionLocal() as db:
        saved = WorkflowRecoveryService(WorkflowRunService(db)).recover(running.run_ref, current)
    assert saved.status == WorkflowStatus.SUCCESS
    assert seen[0][1].db is current.db
    assert seen[0][1].runtime_identity.run_ref == running.run_ref
