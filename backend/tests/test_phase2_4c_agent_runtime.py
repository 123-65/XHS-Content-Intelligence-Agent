from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from app.agent.schemas.execution import WorkflowStatus
from app.agent.tools.execution_context import ToolExecutionContext
from app.agent.workflows.definitions import WorkflowId
from app.core.database import SessionLocal
from app.models.account import AccountProfile
from app.models.workflow_run import WorkflowRun
from app.runtime.agent_runtime import AgentRuntime, WorkflowStartRequest
from app.runtime.workflow_contract_registry import WORKFLOW_RUNTIME_CONTRACTS
from app.runtime.workflow_initial_state_registry import build_initial_state
from app.runtime.workflow_resume import WorkflowResumeRequest
from app.services.workflow_run_sev import WorkflowRunService
from app.services.workflow_run_sev import WorkflowRunServiceError


@pytest.fixture
def account_id():
    with SessionLocal() as db:
        account = AccountProfile(account_name="Runtime Test", positioning="test", target_audience="test")
        db.add(account)
        db.commit()
        db.refresh(account)
        return account.id


def _inputs(account):
    now = datetime.now(UTC)
    return {
        WorkflowId.RESEARCH_V1: {"account_ref": account, "research_goal": "research"},
        WorkflowId.CONTENT_STRATEGY_V1: {"account_ref": account, "strategy_goal": "strategy"},
        WorkflowId.CONTENT_CREATION_V1: {"account_ref": account},
        WorkflowId.CONTENT_REFINEMENT_V1: {"account_ref": account},
        WorkflowId.POST_PUBLISH_REVIEW_V1: {
            "account_ref": account,
            "window_start": now - timedelta(days=7),
            "window_end": now,
        },
    }


class SuccessHandler:
    def __init__(self, workflow_id, calls, fail=False):
        self.workflow_id = workflow_id
        self.calls = calls
        self.fail = fail

    def execute(self, data, context):
        self.calls.append((type(data), context))
        if self.fail:
            raise RuntimeError("private execution detail")
        contract = WORKFLOW_RUNTIME_CONTRACTS[self.workflow_id]
        state = build_initial_state(self.workflow_id, data).model_copy(update={"status": WorkflowStatus.SUCCESS})
        return contract.result_type(status=WorkflowStatus.SUCCESS, state=state)


@pytest.mark.parametrize("workflow_id", list(WorkflowId))
def test_start_builds_all_typed_inputs_and_initial_states(monkeypatch, account_id, workflow_id):
    calls = []
    monkeypatch.setattr(
        "app.runtime.agent_runtime.build_workflow_handler",
        lambda selected: SuccessHandler(selected, calls),
    )
    with SessionLocal() as db:
        result = AgentRuntime(WorkflowRunService(db)).start(
            WorkflowStartRequest(workflow_name=workflow_id, input=_inputs(account_id)[workflow_id]),
            ToolExecutionContext(db=object()),
        )
        snapshot = WorkflowRunService(db).get_run(result.run_ref)
        contract = WORKFLOW_RUNTIME_CONTRACTS[workflow_id]
        assert result.status == WorkflowStatus.SUCCESS and result.checkpoint_version == 3
        assert isinstance(snapshot.input, contract.input_type)
        assert isinstance(snapshot.state, contract.state_type)
        assert len(calls) == 1


@pytest.mark.parametrize("workflow_id", [WorkflowId.CONTENT_REFINEMENT_V1, WorkflowId.POST_PUBLISH_REVIEW_V1])
def test_real_workflows_start_waiting_and_are_durable(account_id, workflow_id):
    with SessionLocal() as db:
        runtime = AgentRuntime(WorkflowRunService(db))
        result = runtime.start(
            WorkflowStartRequest(workflow_name=workflow_id, input=_inputs(account_id)[workflow_id]),
            ToolExecutionContext(db=db),
        )
        assert result.status == WorkflowStatus.WAITING_USER
        assert result.pending_interaction is not None
        assert result.checkpoint_version == 3


def test_invalid_start_creates_no_run(account_id):
    with SessionLocal() as db:
        before = db.query(WorkflowRun).count()
        runtime = AgentRuntime(WorkflowRunService(db))
        with pytest.raises(Exception):
            runtime.start(
                WorkflowStartRequest(workflow_name=WorkflowId.RESEARCH_V1, input={"account_ref": account_id}),
                ToolExecutionContext(db=db),
            )
        assert db.query(WorkflowRun).count() == before
    with pytest.raises(ValidationError):
        WorkflowStartRequest(workflow_name="UNKNOWN", input={})


def test_uncaught_exception_is_persisted_as_safe_failure(monkeypatch, account_id):
    calls = []
    monkeypatch.setattr(
        "app.runtime.agent_runtime.build_workflow_handler",
        lambda selected: SuccessHandler(selected, calls, fail=True),
    )
    with SessionLocal() as db:
        runtime = AgentRuntime(WorkflowRunService(db))
        result = runtime.start(
            WorkflowStartRequest(workflow_name=WorkflowId.RESEARCH_V1, input=_inputs(account_id)[WorkflowId.RESEARCH_V1]),
            ToolExecutionContext(db=db),
        )
        assert result.status == WorkflowStatus.FAILED and result.checkpoint_version == 3
        assert result.error.code == "WORKFLOW_EXECUTION_ERROR"
        assert "private" not in result.error.model_dump_json()


def test_partial_success_persists_typed_result(monkeypatch, account_id):
    class PartialHandler:
        def execute(self, data, context):
            state = build_initial_state(WorkflowId.RESEARCH_V1, data).model_copy(
                update={"status": WorkflowStatus.PARTIAL_SUCCESS, "warnings": ["partial"]}
            )
            return WORKFLOW_RUNTIME_CONTRACTS[WorkflowId.RESEARCH_V1].result_type(
                status=WorkflowStatus.PARTIAL_SUCCESS, state=state, warnings=["partial"]
            )

    monkeypatch.setattr("app.runtime.agent_runtime.build_workflow_handler", lambda selected: PartialHandler())
    with SessionLocal() as db:
        result = AgentRuntime(WorkflowRunService(db)).start(
            WorkflowStartRequest(workflow_name=WorkflowId.RESEARCH_V1, input=_inputs(account_id)[WorkflowId.RESEARCH_V1]),
            ToolExecutionContext(db=db),
        )
        assert result.status == WorkflowStatus.PARTIAL_SUCCESS
        assert result.result is not None and result.warnings == ["partial"]
        assert result.checkpoint_version == 3 and result.completed_at is not None


def test_final_checkpoint_conflict_propagates_without_reexecution(monkeypatch, account_id):
    calls = []
    monkeypatch.setattr("app.runtime.agent_runtime.build_workflow_handler", lambda selected: SuccessHandler(selected, calls))
    with SessionLocal() as db:
        service = WorkflowRunService(db)
        original = service.save_checkpoint
        save_calls = 0

        def conflicting_save(*args, **kwargs):
            nonlocal save_calls
            save_calls += 1
            if save_calls == 1:
                raise WorkflowRunServiceError("WORKFLOW_CHECKPOINT_CONFLICT", "concurrent writer")
            return original(*args, **kwargs)

        service.save_checkpoint = conflicting_save
        with pytest.raises(WorkflowRunServiceError) as conflict:
            AgentRuntime(service).start(
                WorkflowStartRequest(workflow_name=WorkflowId.RESEARCH_V1, input=_inputs(account_id)[WorkflowId.RESEARCH_V1]),
                ToolExecutionContext(db=db),
            )
        assert conflict.value.code == "WORKFLOW_CHECKPOINT_CONFLICT"
        assert len(calls) == 1


def test_get_run_is_safe_and_resume_delegates_once(monkeypatch, account_id):
    with SessionLocal() as first_db:
        first = AgentRuntime(WorkflowRunService(first_db)).start(
            WorkflowStartRequest(workflow_name=WorkflowId.CONTENT_REFINEMENT_V1, input=_inputs(account_id)[WorkflowId.CONTENT_REFINEMENT_V1]),
            ToolExecutionContext(db=first_db),
        )
    calls = []

    class ResumeHandler:
        def resume(self, state, data, context):
            calls.append(context)
            state = state.model_copy(update={"status": WorkflowStatus.SUCCESS, "pending_interaction": None}, deep=True)
            return WORKFLOW_RUNTIME_CONTRACTS[WorkflowId.CONTENT_REFINEMENT_V1].result_type(status=WorkflowStatus.SUCCESS, state=state)

    monkeypatch.setattr("app.runtime.workflow_resume.build_workflow_handler", lambda selected: ResumeHandler())
    with SessionLocal() as second_db:
        runtime = AgentRuntime(WorkflowRunService(second_db))
        resumed = runtime.resume(
            WorkflowResumeRequest(run_ref=first.run_ref, expected_checkpoint_version=3, new_input={"draft_ref": 1}),
            ToolExecutionContext(db=second_db),
        )
        public = runtime.get_run(first.run_ref).model_dump()
        assert resumed.status == WorkflowStatus.SUCCESS and resumed.checkpoint_version == 5
        assert len(calls) == 1
        assert {"input", "state", "account_id", "scope"}.isdisjoint(public)
        assert public["created_at"] and public["updated_at"] and public["completed_at"]
