from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.agent.schemas.execution import WorkflowStatus
from app.agent.schemas.interaction import PendingInteraction, PendingInteractionType
from app.agent.tools.definitions import ToolError
from app.agent.tools.execution_context import ToolExecutionContext
from app.agent.workflows.content_creation import ContentCreationWorkflowInput, ContentCreationWorkflowState
from app.agent.workflows.content_refinement import ContentRefinementWorkflowInput, ContentRefinementWorkflowState
from app.agent.workflows.content_strategy import ContentStrategyWorkflowInput, ContentStrategyWorkflowState
from app.agent.workflows.definitions import WorkflowId
from app.agent.workflows.post_publish_review import PostPublishReviewWorkflowInput, PostPublishReviewWorkflowState
from app.agent.workflows.research import ResearchWorkflowInput, ResearchWorkflowState
from app.core.database import SessionLocal
from app.models.account import AccountProfile
from app.models.workflow_run import WorkflowRun
from app.runtime.workflow_contract_registry import WORKFLOW_RUNTIME_CONTRACTS
from app.runtime.workflow_resume import WorkflowResumeRequest, WorkflowResumeService
from app.services.workflow_run_sev import WorkflowRunService, WorkflowRunServiceError


NOW = datetime.now(UTC)
BACKEND_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def account_id():
    with SessionLocal() as db:
        account = AccountProfile(account_name="Resume Test", positioning="测试", target_audience="测试用户")
        db.add(account)
        db.commit()
        db.refresh(account)
        return account.id


def _contracts(account):
    return {
        WorkflowId.RESEARCH_V1: (ResearchWorkflowInput(account_ref=account, research_goal="研究"), ResearchWorkflowState(account_ref=account, research_goal="研究")),
        WorkflowId.CONTENT_STRATEGY_V1: (ContentStrategyWorkflowInput(account_ref=account, strategy_goal="策略"), ContentStrategyWorkflowState(account_ref=account, strategy_goal="策略")),
        WorkflowId.CONTENT_CREATION_V1: (ContentCreationWorkflowInput(account_ref=account), ContentCreationWorkflowState(account_ref=account)),
        WorkflowId.CONTENT_REFINEMENT_V1: (ContentRefinementWorkflowInput(account_ref=account), ContentRefinementWorkflowState(account_ref=account)),
        WorkflowId.POST_PUBLISH_REVIEW_V1: (
            PostPublishReviewWorkflowInput(account_ref=account, window_start=NOW - timedelta(days=7), window_end=NOW),
            PostPublishReviewWorkflowState(account_ref=account, window_start=NOW - timedelta(days=7), window_end=NOW),
        ),
    }


def _waiting_run(workflow_id, account):
    data, state = _contracts(account)[workflow_id]
    pending = PendingInteraction(
        type=PendingInteractionType.CLARIFICATION,
        reason="需要用户补充",
        required_fields=["input"],
        resume_token=f"{workflow_id.value}_RESUME",
    )
    with SessionLocal() as db:
        service = WorkflowRunService(db)
        created = service.create_run(workflow_id, data, state)
        running_state = created.state.model_copy(update={"status": WorkflowStatus.RUNNING})
        running = service.mark_running(created.run_ref, 1, running_state)
        waiting_state = running.state.model_copy(update={"status": WorkflowStatus.WAITING_USER, "pending_interaction": pending})
        waiting = service.save_checkpoint(created.run_ref, 2, waiting_state)
        return waiting.run_ref, waiting.checkpoint_version, data.model_dump(mode="json"), pending


class FakeHandler:
    def __init__(self, workflow_id, outcome, calls, on_resume=None):
        self.workflow_id = workflow_id
        self.outcome = outcome
        self.calls = calls
        self.on_resume = on_resume

    def resume(self, state, data, context):
        self.calls.append((self.workflow_id, type(state), type(data), context))
        if self.on_resume:
            self.on_resume()
        if self.outcome == "raise":
            raise RuntimeError("secret traceback detail")
        pending = None
        if self.outcome == WorkflowStatus.WAITING_USER:
            pending = PendingInteraction(type=PendingInteractionType.CLARIFICATION, reason="仍需补充", resume_token="next")
        target = self.outcome if isinstance(self.outcome, WorkflowStatus) else WorkflowStatus.SUCCESS
        next_state = state.model_copy(update={"status": target, "pending_interaction": pending}, deep=True)
        contract = WORKFLOW_RUNTIME_CONTRACTS[self.workflow_id]
        fields = {"status": target, "state": next_state, "warnings": list(getattr(next_state, "warnings", [])), "pending_interaction": pending}
        if target == WorkflowStatus.FAILED:
            fields["error"] = ToolError(code="BUSINESS_FAILED", category="TEST", retryable=False, safe_message="业务失败")
        return contract.result_type(**fields)


def _coordinator(monkeypatch, db, workflow_id, outcome, calls, on_resume=None):
    monkeypatch.setattr(
        "app.runtime.workflow_resume.build_workflow_handler",
        lambda selected: FakeHandler(selected, outcome, calls, on_resume),
    )
    return WorkflowResumeService(WorkflowRunService(db))


def test_cross_session_resume_success_and_terminal_repeat_rejected(monkeypatch, account_id):
    run_ref, version, new_input, _ = _waiting_run(WorkflowId.RESEARCH_V1, account_id)
    calls = []
    context = ToolExecutionContext(db=object())
    with SessionLocal() as fresh_db:
        result = _coordinator(monkeypatch, fresh_db, WorkflowId.RESEARCH_V1, WorkflowStatus.SUCCESS, calls).resume(
            WorkflowResumeRequest(run_ref=run_ref, expected_checkpoint_version=version, new_input=new_input), context
        )
        assert result.status == WorkflowStatus.SUCCESS and result.checkpoint_version == version + 2
        assert result.result is not None and result.pending_interaction is None
    with SessionLocal() as another_db:
        with pytest.raises(WorkflowRunServiceError) as terminal:
            _coordinator(monkeypatch, another_db, WorkflowId.RESEARCH_V1, WorkflowStatus.SUCCESS, calls).resume(
                WorkflowResumeRequest(run_ref=run_ref, expected_checkpoint_version=result.checkpoint_version, new_input=new_input), context
            )
        assert terminal.value.code == "WORKFLOW_RUN_TERMINAL"
        assert len(calls) == 1


@pytest.mark.parametrize("outcome", [WorkflowStatus.WAITING_USER, WorkflowStatus.PARTIAL_SUCCESS, WorkflowStatus.FAILED])
def test_resume_persists_waiting_partial_and_failed(monkeypatch, account_id, outcome):
    run_ref, version, new_input, _ = _waiting_run(WorkflowId.CONTENT_REFINEMENT_V1, account_id)
    calls = []
    with SessionLocal() as db:
        result = _coordinator(monkeypatch, db, WorkflowId.CONTENT_REFINEMENT_V1, outcome, calls).resume(
            WorkflowResumeRequest(run_ref=run_ref, expected_checkpoint_version=version, new_input=new_input),
            ToolExecutionContext(db=object()),
        )
        assert result.status == outcome and result.checkpoint_version == version + 2
        if outcome == WorkflowStatus.WAITING_USER:
            assert result.pending_interaction.reason == "仍需补充" and result.result is None
        elif outcome == WorkflowStatus.PARTIAL_SUCCESS:
            assert result.result is not None and result.error is None
        else:
            assert result.result is None and result.error.code == "BUSINESS_FAILED"


def test_input_account_state_injection_version_and_status_rejected_before_workflow(monkeypatch, account_id):
    run_ref, version, new_input, _ = _waiting_run(WorkflowId.RESEARCH_V1, account_id)
    calls = []
    context = ToolExecutionContext(db=object())
    with SessionLocal() as db:
        coordinator = _coordinator(monkeypatch, db, WorkflowId.RESEARCH_V1, WorkflowStatus.SUCCESS, calls)
        for payload, code in (
            ({**new_input, "account_ref": account_id + 1}, "WORKFLOW_RUN_ACCOUNT_MISMATCH"),
            ({**new_input, "state_snapshot": {}}, "WORKFLOW_RESUME_INPUT_INVALID"),
        ):
            with pytest.raises(WorkflowRunServiceError) as rejected:
                coordinator.resume(WorkflowResumeRequest(run_ref=run_ref, expected_checkpoint_version=version, new_input=payload), context)
            assert rejected.value.code == code
        with pytest.raises(WorkflowRunServiceError) as stale:
            coordinator.resume(WorkflowResumeRequest(run_ref=run_ref, expected_checkpoint_version=version - 1, new_input=new_input), context)
        assert stale.value.code == "WORKFLOW_CHECKPOINT_CONFLICT"
        assert calls == []

    with pytest.raises(ValidationError):
        WorkflowResumeRequest(run_ref=run_ref, expected_checkpoint_version=version, new_input=new_input, state_snapshot={})


def test_running_and_corrupt_pending_are_rejected(monkeypatch, account_id):
    run_ref, version, new_input, _ = _waiting_run(WorkflowId.RESEARCH_V1, account_id)
    calls = []
    with SessionLocal() as db:
        service = WorkflowRunService(db)
        waiting = service.get_run(run_ref)
        running = service.mark_running(run_ref, version, waiting.state.model_copy(update={"status": WorkflowStatus.RUNNING, "pending_interaction": None}))
        with pytest.raises(WorkflowRunServiceError) as active:
            _coordinator(monkeypatch, db, WorkflowId.RESEARCH_V1, WorkflowStatus.SUCCESS, calls).resume(
                WorkflowResumeRequest(run_ref=run_ref, expected_checkpoint_version=running.checkpoint_version, new_input=new_input), ToolExecutionContext(db=object())
            )
        assert active.value.code == "WORKFLOW_RUN_ALREADY_RUNNING"

    corrupt_ref, corrupt_version, corrupt_input, _ = _waiting_run(WorkflowId.RESEARCH_V1, account_id)
    with SessionLocal() as db:
        record = db.query(WorkflowRun).filter_by(run_ref=corrupt_ref).one()
        record.pending_interaction = None
        db.commit()
    with SessionLocal() as db:
        with pytest.raises(WorkflowRunServiceError) as corrupt:
            _coordinator(monkeypatch, db, WorkflowId.RESEARCH_V1, WorkflowStatus.SUCCESS, calls).resume(
                WorkflowResumeRequest(run_ref=corrupt_ref, expected_checkpoint_version=corrupt_version, new_input=corrupt_input), ToolExecutionContext(db=object())
            )
        assert corrupt.value.code == "WORKFLOW_RUN_CORRUPTED" and calls == []


def test_concurrent_resume_only_claim_winner_executes(monkeypatch, account_id):
    run_ref, version, new_input, _ = _waiting_run(WorkflowId.CONTENT_STRATEGY_V1, account_id)
    calls_a, calls_b, loser_errors = [], [], []
    context_a, context_b = ToolExecutionContext(db=object()), ToolExecutionContext(db=object())
    with SessionLocal() as db_a, SessionLocal() as db_b:
        loser = _coordinator(monkeypatch, db_b, WorkflowId.CONTENT_STRATEGY_V1, WorkflowStatus.SUCCESS, calls_b)

        def compete_after_claim():
            try:
                loser.resume(WorkflowResumeRequest(run_ref=run_ref, expected_checkpoint_version=version, new_input=new_input), context_b)
            except WorkflowRunServiceError as exc:
                loser_errors.append(exc.code)

        winner = _coordinator(monkeypatch, db_a, WorkflowId.CONTENT_STRATEGY_V1, WorkflowStatus.SUCCESS, calls_a, compete_after_claim)
        result = winner.resume(WorkflowResumeRequest(run_ref=run_ref, expected_checkpoint_version=version, new_input=new_input), context_a)
        assert result.status == WorkflowStatus.SUCCESS
        assert loser_errors == ["WORKFLOW_RUN_ALREADY_RUNNING"]
        assert len(calls_a) == 1 and calls_b == []


def test_all_five_handlers_receive_typed_state_and_current_scope(monkeypatch, account_id):
    for workflow_id in WorkflowId:
        run_ref, version, new_input, _ = _waiting_run(workflow_id, account_id)
        calls = []
        current_scope = ToolExecutionContext(db=object())
        with SessionLocal() as db:
            result = _coordinator(monkeypatch, db, workflow_id, WorkflowStatus.WAITING_USER, calls).resume(
                WorkflowResumeRequest(run_ref=run_ref, expected_checkpoint_version=version, new_input=new_input), current_scope
            )
        contract = WORKFLOW_RUNTIME_CONTRACTS[workflow_id]
        assert result.status == WorkflowStatus.WAITING_USER
        assert calls[0][0] == workflow_id
        assert calls[0][1] is contract.state_type and calls[0][2] is contract.input_type
        assert calls[0][3].db is current_scope.db
        assert calls[0][3].evidence_access_scope is current_scope.evidence_access_scope
        assert calls[0][3].collection_access_scope is current_scope.collection_access_scope
        assert calls[0][3].runtime_identity.run_ref == run_ref
        assert calls[0][3].runtime_identity.workflow_name == workflow_id.value


def test_real_research_and_refinement_handlers_resume_across_sessions(account_id):
    cases = []
    for workflow_id in (WorkflowId.RESEARCH_V1, WorkflowId.CONTENT_REFINEMENT_V1):
        data, state = _contracts(account_id)[workflow_id]
        if workflow_id == WorkflowId.RESEARCH_V1:
            state = state.model_copy(update={"growth_context": {}})
        pending = PendingInteraction(type=PendingInteractionType.CLARIFICATION, reason="补充", resume_token="real")
        with SessionLocal() as db_a:
            service = WorkflowRunService(db_a)
            created = service.create_run(workflow_id, data, state)
            running = service.mark_running(created.run_ref, 1, created.state.model_copy(update={"status": WorkflowStatus.RUNNING}))
            waiting = service.save_checkpoint(
                created.run_ref, 2,
                running.state.model_copy(update={"status": WorkflowStatus.WAITING_USER, "pending_interaction": pending}),
            )
            cases.append((workflow_id, waiting.run_ref, waiting.checkpoint_version, data.model_dump(mode="json")))

    for workflow_id, run_ref, version, new_input in cases:
        with SessionLocal() as db_b:
            result = WorkflowResumeService(WorkflowRunService(db_b)).resume(
                WorkflowResumeRequest(run_ref=run_ref, expected_checkpoint_version=version, new_input=new_input),
                ToolExecutionContext(db=db_b),
            )
            assert result.workflow_name == workflow_id.value
            assert result.status == WorkflowStatus.WAITING_USER
            assert result.checkpoint_version == version + 2
            assert result.pending_interaction is not None


def test_unhandled_exception_is_safe_failed_without_traceback(monkeypatch, account_id):
    run_ref, version, new_input, _ = _waiting_run(WorkflowId.RESEARCH_V1, account_id)
    with SessionLocal() as db:
        result = _coordinator(monkeypatch, db, WorkflowId.RESEARCH_V1, "raise", []).resume(
            WorkflowResumeRequest(run_ref=run_ref, expected_checkpoint_version=version, new_input=new_input), ToolExecutionContext(db=object())
        )
        assert result.status == WorkflowStatus.FAILED and result.checkpoint_version == version + 2
        assert result.error.code == "WORKFLOW_RESUME_EXECUTION_ERROR"
        raw = db.query(WorkflowRun).filter_by(run_ref=run_ref).one()
        assert "traceback" not in str(raw.error_snapshot).lower()
        assert "secret traceback detail" not in str(raw.error_snapshot)


def test_resume_service_architecture_boundary():
    source = (BACKEND_ROOT / "app/runtime/workflow_resume.py").read_text(encoding="utf-8")
    assert "build_workflow_handler" in source and ".resume(" in source
    for forbidden in ("sqlalchemy", "app.repositories", "app.llm", "app.crawler", "fastapi", "EvidenceAccessScope(", "CollectionAccessScope("):
        assert forbidden not in source
