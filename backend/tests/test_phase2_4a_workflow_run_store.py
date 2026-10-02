from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import pytest

from app.agent.schemas.execution import ArtifactRef, ArtifactType, WorkflowStatus
from app.agent.schemas.interaction import PendingInteraction, PendingInteractionType
from app.agent.tools.definitions import ToolError
from app.agent.workflows.content_creation import ContentCreationWorkflowInput, ContentCreationWorkflowState
from app.agent.workflows.content_refinement import ContentRefinementWorkflowInput, ContentRefinementWorkflowState
from app.agent.workflows.content_strategy import ContentStrategyWorkflowInput, ContentStrategyWorkflowState
from app.agent.workflows.definitions import WorkflowId
from app.agent.workflows.post_publish_review import PostPublishReviewWorkflowInput, PostPublishReviewWorkflowState
from app.agent.workflows.research import ResearchStepStatus, ResearchWorkflowInput, ResearchWorkflowResult, ResearchWorkflowState
from app.core.database import SessionLocal
from app.models.account import AccountProfile
from app.models.workflow_run import WorkflowRun
from app.runtime.workflow_contract_registry import WORKFLOW_RUNTIME_CONTRACTS
from app.services.workflow_run_sev import WorkflowRunService, WorkflowRunServiceError


NOW = datetime.now(UTC)
BACKEND_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def account_id():
    with SessionLocal() as db:
        account = AccountProfile(account_name="Workflow Run Test", positioning="测试", target_audience="测试用户")
        db.add(account)
        db.commit()
        db.refresh(account)
        return account.id


def _contracts(account):
    return {
        WorkflowId.RESEARCH_V1: (
            ResearchWorkflowInput(account_ref=account, research_goal="研究", artifact_refs=[ArtifactRef(type=ArtifactType.RESEARCH, id=11)]),
            ResearchWorkflowState(account_ref=account, research_goal="研究", warnings=["INSUFFICIENT_SAMPLE"]),
        ),
        WorkflowId.CONTENT_STRATEGY_V1: (
            ContentStrategyWorkflowInput(account_ref=account, research_artifact_ref=ArtifactRef(type=ArtifactType.RESEARCH, id=11), strategy_goal="策略"),
            ContentStrategyWorkflowState(account_ref=account, strategy_goal="策略", research_artifact_ref=ArtifactRef(type=ArtifactType.RESEARCH, id=11)),
        ),
        WorkflowId.CONTENT_CREATION_V1: (
            ContentCreationWorkflowInput(account_ref=account, strategy_artifact_ref=ArtifactRef(type=ArtifactType.CONTENT_STRATEGY, id=12)),
            ContentCreationWorkflowState(account_ref=account, strategy_artifact_ref=ArtifactRef(type=ArtifactType.CONTENT_STRATEGY, id=12)),
        ),
        WorkflowId.CONTENT_REFINEMENT_V1: (
            ContentRefinementWorkflowInput(account_ref=account, draft_ref=13, user_feedback="更清晰"),
            ContentRefinementWorkflowState(account_ref=account, draft_ref=13, user_feedback="更清晰"),
        ),
        WorkflowId.POST_PUBLISH_REVIEW_V1: (
            PostPublishReviewWorkflowInput(account_ref=account, published_note_ref=14, window_start=NOW - timedelta(days=7), window_end=NOW),
            PostPublishReviewWorkflowState(account_ref=account, published_note_ref=14, window_start=NOW - timedelta(days=7), window_end=NOW),
        ),
    }


def _create_research(service, account, run_ref=None):
    data, state = _contracts(account)[WorkflowId.RESEARCH_V1]
    return service.create_run(WorkflowId.RESEARCH_V1, data, state, run_ref=run_ref)


def _running(snapshot):
    return snapshot.state.model_copy(update={"status": WorkflowStatus.RUNNING, "pending_interaction": None})


def test_create_run_unique_ref_and_reject_unknown_workflow(account_id):
    with SessionLocal() as db:
        service = WorkflowRunService(db)
        fixed_ref = f"wfr_test_{uuid4().hex}"
        created = _create_research(service, account_id, fixed_ref)
        assert created.status == WorkflowStatus.PENDING and created.checkpoint_version == 1
        with pytest.raises(WorkflowRunServiceError, match="run_ref") as duplicate:
            _create_research(service, account_id, fixed_ref)
        assert duplicate.value.code == "WORKFLOW_RUN_CONFLICT"
        data, state = _contracts(account_id)[WorkflowId.RESEARCH_V1]
        with pytest.raises(WorkflowRunServiceError) as unknown:
            service.create_run("UNKNOWN", data, state)
        assert unknown.value.code == "WORKFLOW_CONTRACT_INVALID"


def test_all_five_typed_states_round_trip_with_json_semantics(account_id):
    assert set(WORKFLOW_RUNTIME_CONTRACTS) == set(WorkflowId)
    refs = []
    with SessionLocal() as db:
        service = WorkflowRunService(db)
        for workflow_id, (data, state) in _contracts(account_id).items():
            refs.append((workflow_id, service.create_run(workflow_id, data, state).run_ref))
    with SessionLocal() as fresh_db:
        fresh = WorkflowRunService(fresh_db)
        for workflow_id, run_ref in refs:
            loaded = fresh.get_run(run_ref)
            contract = WORKFLOW_RUNTIME_CONTRACTS[workflow_id]
            assert isinstance(loaded.input, contract.input_type)
            assert isinstance(loaded.state, contract.state_type)
            assert loaded.state.model_dump(mode="json") == _contracts(account_id)[workflow_id][1].model_dump(mode="json")
        research = fresh.get_run(refs[0][1])
        assert research.input.artifact_refs[0] == ArtifactRef(type=ArtifactType.RESEARCH, id=11)
        assert research.warnings == ["INSUFFICIENT_SAMPLE"]
        assert research.state.step_states["growth_context"] == ResearchStepStatus.NOT_STARTED


def test_waiting_user_round_trip_and_load_for_resume_from_new_session(account_id):
    with SessionLocal() as db:
        service = WorkflowRunService(db)
        created = _create_research(service, account_id)
        running = service.mark_running(created.run_ref, 1, _running(created))
        pending = PendingInteraction(
            type=PendingInteractionType.CLARIFICATION,
            reason="需要研究样本",
            required_fields=["note_urls"],
            resume_token="research-resume",
        )
        waiting_state = running.state.model_copy(update={"status": WorkflowStatus.WAITING_USER, "pending_interaction": pending})
        waiting = service.save_checkpoint(created.run_ref, 2, waiting_state)
        assert waiting.checkpoint_version == 3
    with SessionLocal() as fresh_db:
        resumed = WorkflowRunService(fresh_db).load_for_resume(created.run_ref)
        assert isinstance(resumed.input, ResearchWorkflowInput)
        assert isinstance(resumed.state, ResearchWorkflowState)
        assert resumed.state.status == WorkflowStatus.WAITING_USER
        assert resumed.pending_interaction == pending
        assert resumed.checkpoint_version == 3


def test_success_result_and_failed_error_round_trip(account_id):
    with SessionLocal() as db:
        service = WorkflowRunService(db)
        success_run = _create_research(service, account_id)
        running = service.mark_running(success_run.run_ref, 1, _running(success_run))
        success_state = running.state.model_copy(update={"status": WorkflowStatus.SUCCESS, "warnings": ["INSUFFICIENT_SAMPLE"]})
        result = ResearchWorkflowResult(status=WorkflowStatus.SUCCESS, state=success_state, warnings=success_state.warnings)
        completed = service.save_checkpoint(success_run.run_ref, 2, success_state, workflow_result=result)
        assert completed.status == WorkflowStatus.SUCCESS and isinstance(completed.result, ResearchWorkflowResult)
        assert completed.warnings == ["INSUFFICIENT_SAMPLE"]

        failed_run = _create_research(service, account_id)
        failed_running = service.mark_running(failed_run.run_ref, 1, _running(failed_run))
        failed_state = failed_running.state.model_copy(update={"status": WorkflowStatus.FAILED})
        failed = service.save_checkpoint(
            failed_run.run_ref, 2, failed_state,
            error=ToolError(code="ANALYSIS_FAILED", category="SEMANTIC", retryable=False, safe_message="分析失败"),
            error_source="analyze_research",
        )
        assert failed.result is None
        assert failed.error.code == "ANALYSIS_FAILED" and failed.error.source == "analyze_research"
        raw = db.query(WorkflowRun).filter_by(run_ref=failed.run_ref).one()
        assert "traceback" not in raw.error_snapshot


def test_checkpoint_conflict_preserves_version_four(account_id):
    with SessionLocal() as db:
        service = WorkflowRunService(db)
        created = _create_research(service, account_id)
        running = service.mark_running(created.run_ref, 1, _running(created))
        pending = PendingInteraction(type=PendingInteractionType.CLARIFICATION, reason="补充", resume_token="token")
        waiting_state = running.state.model_copy(update={"status": WorkflowStatus.WAITING_USER, "pending_interaction": pending})
        waiting = service.save_checkpoint(created.run_ref, 2, waiting_state)
        run_ref = waiting.run_ref
    with SessionLocal() as db_a, SessionLocal() as db_b:
        service_a, service_b = WorkflowRunService(db_a), WorkflowRunService(db_b)
        read_a, read_b = service_a.load_for_resume(run_ref), service_b.load_for_resume(run_ref)
        assert read_a.checkpoint_version == read_b.checkpoint_version == 3
        resumed_state = read_a.state.model_copy(update={"status": WorkflowStatus.RUNNING, "pending_interaction": None})
        version_four = service_a.save_checkpoint(run_ref, 3, resumed_state)
        assert version_four.checkpoint_version == 4
        with pytest.raises(WorkflowRunServiceError) as stale:
            service_b.save_checkpoint(run_ref, 3, resumed_state)
        assert stale.value.code == "WORKFLOW_CHECKPOINT_CONFLICT"
    with SessionLocal() as fresh_db:
        assert WorkflowRunService(fresh_db).get_run(run_ref).checkpoint_version == 4


def test_invalid_transition_pending_and_terminal_runs_are_closed(account_id):
    with SessionLocal() as db:
        service = WorkflowRunService(db)
        created = _create_research(service, account_id)
        invalid = created.state.model_copy(update={"status": WorkflowStatus.SUCCESS})
        result = ResearchWorkflowResult(status=WorkflowStatus.SUCCESS, state=invalid)
        with pytest.raises(WorkflowRunServiceError) as transition:
            service.save_checkpoint(created.run_ref, 1, invalid, workflow_result=result)
        assert transition.value.code == "INVALID_STATUS_TRANSITION"

        running = service.mark_running(created.run_ref, 1, _running(created))
        success_state = running.state.model_copy(update={"status": WorkflowStatus.SUCCESS})
        success_result = ResearchWorkflowResult(status=WorkflowStatus.SUCCESS, state=success_state)
        completed = service.save_checkpoint(created.run_ref, 2, success_state, workflow_result=success_result)
        for action in (
            lambda: service.save_checkpoint(completed.run_ref, 3, success_state, workflow_result=success_result),
            lambda: service.mark_running(completed.run_ref, 3, success_state.model_copy(update={"status": WorkflowStatus.RUNNING})),
            lambda: service.load_for_resume(completed.run_ref),
        ):
            with pytest.raises(WorkflowRunServiceError) as terminal:
                action()
            assert terminal.value.code == "WORKFLOW_RUN_TERMINAL"


def test_pending_gate_and_architecture_boundary(account_id):
    with SessionLocal() as db:
        service = WorkflowRunService(db)
        created = _create_research(service, account_id)
        running = service.mark_running(created.run_ref, 1, _running(created))
        missing = running.state.model_copy(update={"status": WorkflowStatus.WAITING_USER, "pending_interaction": None})
        with pytest.raises(WorkflowRunServiceError) as error:
            service.save_checkpoint(created.run_ref, 2, missing)
        assert error.value.code == "PENDING_INTERACTION_REQUIRED"

    sources = "\n".join((BACKEND_ROOT / path).read_text(encoding="utf-8") for path in (
        "app/services/workflow_run_sev.py", "app/repositories/workflow_run_repo.py", "app/runtime/workflow_contract_registry.py"
    ))
    for forbidden in ("build_tool_handler", "handler.execute(", "workflow.resume(", "app.llm", "app.crawler", "fastapi", "app.repositories.draft", "app.repositories.publication"):
        assert forbidden not in sources
