from datetime import UTC, datetime

import pytest

from app.agent.schemas.execution import ArtifactRef, ArtifactType
from app.agent.tools.artifact_contracts import CreateResearchArtifactInput, CreateResearchArtifactResult
from app.agent.tools.artifact_contracts import (
    AppendDraftVersionInput,
    CreateContentStrategyArtifactInput,
    CreateContentStrategyArtifactResult,
    CreateDraftVersionInput,
    CreateDraftVersionResult,
    CreatePostPublishReviewArtifactInput,
    CreatePostPublishReviewArtifactResult,
    CreateStrategyCandidateInput,
    CreateStrategyCandidateResult,
)
from app.agent.tools.definitions import ToolName, ToolResult
from app.agent.tools.execution_context import RuntimeExecutionIdentity, ToolExecutionContext
from app.agent.workflows.definitions import WorkflowId
from app.agent.workflows.research import ResearchWorkflowInput, ResearchWorkflowState
from app.core.database import SessionLocal
from app.models.account import AccountProfile
from app.models.workflow_operation import WorkflowOperation
from app.repositories.workflow_operation_repo import WorkflowOperationRepository
from app.runtime.agent_runtime import AgentRuntime, WorkflowStartRequest
from app.runtime.durable_operation import DurableOperationError, DurableOperationExecutor, describe_operation
from app.services.workflow_run_sev import WorkflowRunService


def _research_input(account_id: int) -> CreateResearchArtifactInput:
    return CreateResearchArtifactInput(
        account_ref=account_id,
        research_result={
            "persona": {"positioning": "test", "expertise": [], "target_audience": [], "value_proposition": "test", "tone_and_style": [], "confidence": 0.5, "evidence": []},
            "content_pillars": [], "audience_demands": [], "high_performing_patterns": [],
            "content_style": {"structure": [], "tone": [], "hooks": [], "visual_patterns": [], "evidence_note_ids": []},
            "follow_recommendation": {"why_follow": "test", "what_to_learn": [], "what_not_to_copy": [], "confidence": 0.5, "evidence": []},
            "content_opportunities": [], "conversion_signals": [], "risk_points": [], "data_gaps": [],
        },
        research_evidence={
            "account_id": account_id, "accounts": [], "notes": [], "comments": [],
            "computed_metrics": {"note_count": 0, "comment_count": 0, "account_count": 0, "average_likes": 0, "average_collects": 0, "average_comments": 0, "ranked_notes": []},
            "used_account_ids": [], "used_note_ids": [], "used_comment_ids": [], "ocr_note_ids": [], "data_gaps": [],
        },
        report_name="ledger-test",
    )


@pytest.fixture
def durable_run():
    with SessionLocal() as db:
        account = AccountProfile(account_name="Ledger Test", positioning="test", target_audience="test")
        db.add(account)
        db.commit()
        db.refresh(account)
        run = WorkflowRunService(db).create_run(
            WorkflowId.RESEARCH_V1,
            ResearchWorkflowInput(account_ref=account.id, research_goal="test"),
            ResearchWorkflowState(account_ref=account.id, research_goal="test"),
        )
        return account.id, run.run_ref


def _success_result(object_id: int) -> ToolResult[CreateResearchArtifactResult]:
    return ToolResult(
        success=True,
        data=CreateResearchArtifactResult(
            artifact_ref=ArtifactRef(type=ArtifactType.RESEARCH, id=object_id),
            created_at=datetime.now(UTC),
            evidence_refs=[],
            lineage_refs=[],
        ),
    )


def test_success_replays_typed_result_across_sessions(durable_run):
    account_id, run_ref = durable_run
    data = _research_input(account_id)
    calls = []
    identity = RuntimeExecutionIdentity(run_ref=run_ref, workflow_name=WorkflowId.RESEARCH_V1.value)
    with SessionLocal() as db:
        first = DurableOperationExecutor(db, identity).execute(
            ToolName.CREATE_RESEARCH_ARTIFACT, data, lambda: calls.append("write") or _success_result(500)
        )
        assert first.data.artifact_ref.id == 500
    with SessionLocal() as db:
        replay = DurableOperationExecutor(db, identity).execute(
            ToolName.CREATE_RESEARCH_ARTIFACT, data, lambda: calls.append("duplicate") or _success_result(501)
        )
        assert isinstance(replay.data, CreateResearchArtifactResult)
        assert replay.data.artifact_ref.id == 500
        assert calls == ["write"]
        assert db.query(WorkflowOperation).filter_by(run_ref=run_ref).count() == 1


def test_strategy_draft_review_and_candidate_results_replay_without_second_write(durable_run):
    account_id, run_ref = durable_run
    now = datetime.now(UTC)
    cases = [
        (
            ToolName.CREATE_CONTENT_STRATEGY_ARTIFACT,
            CreateContentStrategyArtifactInput.model_construct(account_ref=account_id, research_artifact_ref=31),
            CreateContentStrategyArtifactResult(
                artifact_ref=ArtifactRef(type=ArtifactType.CONTENT_STRATEGY, id=51),
                research_artifact_ref=31,
                generated_opportunity_refs=[61],
                created_at=now,
            ),
        ),
        (
            ToolName.CREATE_DRAFT_VERSION,
            CreateDraftVersionInput(root=AppendDraftVersionInput(
                action="APPEND", draft_ref=100, parent_draft_ref=201, created_from="USER_REVISION",
                content={"title": "V2", "body": "body"},
            )),
            CreateDraftVersionResult(
                draft_ref=100, draft_version_ref=202, version=2,
                parent_draft_ref=201, created_from="USER_REVISION", created_at=now,
            ),
        ),
        (
            ToolName.CREATE_POST_PUBLISH_REVIEW_ARTIFACT,
            CreatePostPublishReviewArtifactInput.model_construct(
                account_ref=account_id, published_note_ref=31, draft_ref=100, strategy_ref=51, opportunity_ref=61
            ),
            CreatePostPublishReviewArtifactResult(
                artifact_ref=ArtifactRef(type=ArtifactType.POST_PUBLISH_REVIEW, id=71),
                published_note_ref=31,
                created_at=now,
            ),
        ),
        (
            ToolName.CREATE_STRATEGY_CANDIDATE,
            CreateStrategyCandidateInput.model_construct(
                account_ref=account_id,
                post_publish_review_ref=71,
                candidate=type("CandidateIdentity", (), {"candidate_index": 2})(),
            ),
            CreateStrategyCandidateResult(
                strategy_candidate_ref="STRATEGY_CANDIDATE:81",
                status="PROPOSED",
                review_report_ref=71,
                created_at=now,
            ),
        ),
    ]
    identity = RuntimeExecutionIdentity(run_ref, WorkflowId.RESEARCH_V1.value)
    for tool_name, data, output in cases:
        calls = []
        with SessionLocal() as db:
            first = DurableOperationExecutor(db, identity).execute(
                tool_name, data, lambda output=output: calls.append("write") or ToolResult(success=True, data=output)
            )
            assert first.data == output
        with SessionLocal() as db:
            replay = DurableOperationExecutor(db, identity).execute(
                tool_name, data, lambda output=output: calls.append("duplicate") or ToolResult(success=True, data=output)
            )
            assert replay.data == output
            assert calls == ["write"]


def test_identity_mismatch_rejects_without_business_write(durable_run):
    account_id, run_ref = durable_run
    data = _research_input(account_id)
    descriptor = describe_operation(ToolName.CREATE_RESEARCH_ARTIFACT, data)
    with SessionLocal() as db:
        WorkflowOperationRepository(db).create_succeeded(
            run_ref=run_ref,
            workflow_name=WorkflowId.RESEARCH_V1.value,
            operation_key=descriptor.operation_key,
            tool_name=ToolName.CREATE_DRAFT_VERSION.value,
            identity_fingerprint=descriptor.identity_fingerprint,
            result_snapshot=_success_result(500).model_dump(mode="json"),
        )
        db.commit()
    calls = []
    with SessionLocal() as db, pytest.raises(DurableOperationError) as mismatch:
        DurableOperationExecutor(db, RuntimeExecutionIdentity(run_ref, WorkflowId.RESEARCH_V1.value)).execute(
            ToolName.CREATE_RESEARCH_ARTIFACT, data, lambda: calls.append("write") or _success_result(501)
        )
    assert mismatch.value.code == "OPERATION_IDENTITY_MISMATCH" and calls == []


def test_business_failure_creates_no_ledger(durable_run):
    account_id, run_ref = durable_run
    failure = ToolResult(success=False, error={"code": "FAIL", "category": "TEST", "retryable": True, "safe_message": "failed"})
    with SessionLocal() as db:
        result = DurableOperationExecutor(db, RuntimeExecutionIdentity(run_ref, WorkflowId.RESEARCH_V1.value)).execute(
            ToolName.CREATE_RESEARCH_ARTIFACT, _research_input(account_id), lambda: failure
        )
        assert not result.success
    with SessionLocal() as db:
        assert db.query(WorkflowOperation).filter_by(run_ref=run_ref).count() == 0


def test_agent_runtime_injects_server_run_identity(monkeypatch, durable_run):
    account_id, _ = durable_run
    seen = []

    class Handler:
        def execute(self, data, context):
            seen.append(context.runtime_identity)
            state = ResearchWorkflowState(account_ref=data.account_ref, research_goal=data.research_goal, status="SUCCESS")
            from app.agent.workflows.research import ResearchWorkflowResult
            return ResearchWorkflowResult(status="SUCCESS", state=state)

    monkeypatch.setattr("app.runtime.agent_runtime.build_workflow_handler", lambda selected: Handler())
    supplied = ToolExecutionContext(db=object())
    with SessionLocal() as db:
        result = AgentRuntime(WorkflowRunService(db)).start(
            WorkflowStartRequest(workflow_name=WorkflowId.RESEARCH_V1, input={"account_ref": account_id, "research_goal": "test"}),
            supplied,
        )
    assert supplied.runtime_identity is None
    assert seen[0].run_ref == result.run_ref
    assert seen[0].workflow_name == WorkflowId.RESEARCH_V1.value
