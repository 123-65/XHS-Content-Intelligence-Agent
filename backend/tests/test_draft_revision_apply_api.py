from datetime import timedelta

from fastapi.testclient import TestClient

from app.core.database import SessionLocal
from app.llm.errors import LLMError
from app.main import app
from app.models.agent_conversation import AgentConversation
from app.models.content_draft import ContentDraft
from app.models.draft_revision_plan import DraftRevisionPlan
from app.models.published_note import PublishedNote
from app.models.review_report import ReviewReport
from app.models.strategy_memory import StrategyMemory
from app.schemas.draft_revision_apply import DraftRevisionApplyLLMResult
from app.schemas.llm import LLMStructuredResult, LLMUsage
from tests.test_draft_context_preview_api import _create_account
from tests.test_draft_revision_plan_api import (
    FakeRevisionLLMClient,
    _create_plan as _create_revision_plan,
    _create_revision_fixture,
)


def _client() -> TestClient:
    return TestClient(app)


def _apply_result() -> DraftRevisionApplyLLMResult:
    return DraftRevisionApplyLLMResult.model_validate(
        {
            "title": "A more natural revised title",
            "content": "This is the revised body. It keeps the useful example, removes repeated explanation, and stays evidence-aligned.",
            "tags": ["AI Agent", "content ops"],
            "cta": "If you want, try this with one draft first.",
            "change_summary": "Reduced AI tone, shortened the body, and softened the CTA.",
            "applied_operations": [
                {
                    "operation_order": 1,
                    "target": "TITLE",
                    "action": "REWRITE",
                    "result": "Rewrote title with less template tone.",
                },
                {
                    "operation_order": 2,
                    "target": "BODY",
                    "action": "SHORTEN",
                    "result": "Removed repeated explanation.",
                },
                {
                    "operation_order": 3,
                    "target": "CTA",
                    "action": "SOFTEN",
                    "result": "Softened the CTA.",
                },
            ],
        }
    )


class FakeApplyLLMClient:
    called = 0

    def generate_structured(self, *args, **kwargs) -> LLMStructuredResult:
        FakeApplyLLMClient.called += 1
        data = _apply_result()
        return LLMStructuredResult(
            data=data,
            text=data.model_dump_json(),
            model="qwen-plus",
            provider="qwen",
            usage=LLMUsage(prompt_tokens=22, completion_tokens=33, total_tokens=55),
            estimated_cost=0,
            raw_response_id="fake-b11-apply-response",
            is_mock=False,
        )


class ProviderMissingApplyLLMClient:
    called = 0

    def __init__(self):
        ProviderMissingApplyLLMClient.called += 1
        raise LLMError("LLM_CONFIG_MISSING: provider qwen is not configured")


class InvalidJSONApplyLLMClient:
    called = 0

    def generate_structured(self, *args, **kwargs):
        InvalidJSONApplyLLMClient.called += 1
        raise LLMError("invalid json response")


class InvalidSchemaApplyLLMClient:
    called = 0

    def generate_structured(self, *args, **kwargs) -> LLMStructuredResult:
        InvalidSchemaApplyLLMClient.called += 1
        return LLMStructuredResult(
            data={"title": "missing fields"},
            text='{"title":"missing fields"}',
            model="qwen-plus",
            provider="qwen",
            usage=LLMUsage(prompt_tokens=1, completion_tokens=1, total_tokens=2),
            estimated_cost=0,
            raw_response_id="fake-invalid-b11-schema",
            is_mock=False,
        )


def _create_apply_fixture(monkeypatch) -> tuple[int, int, int, int, int]:
    account_id, experiment_id, draft_id, report_id = _create_revision_fixture(monkeypatch)
    FakeRevisionLLMClient.called = 0
    monkeypatch.setattr("app.services.draft_revision_plan_sev.LLMClient", FakeRevisionLLMClient)
    response = _create_revision_plan(draft_id, account_id, report_id)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "READY"
    return account_id, experiment_id, draft_id, report_id, data["plan_id"]


def _create_conversation(account_id: int) -> int:
    with SessionLocal() as db:
        conversation = AgentConversation(
            account_id=account_id,
            title="B11 conversation",
            current_state={"active_account_id": account_id},
        )
        db.add(conversation)
        db.commit()
        db.refresh(conversation)
        return conversation.id


def _set_plan_conversation(plan_id: int, conversation_id: int) -> None:
    with SessionLocal() as db:
        plan = db.get(DraftRevisionPlan, plan_id)
        assert plan is not None
        plan.conversation_id = conversation_id
        db.commit()


def _apply(plan_id: int, account_id: int, confirmed: bool = True, **extra):
    payload = {
        "account_id": account_id,
        "confirmed": confirmed,
        "save_as": "NEW_DRAFT",
        "user_extra_requirements": "Keep it practical.",
    }
    payload.update(extra)
    return _client().post(f"/agent/revision-plans/{plan_id}/apply", json=payload)


def _counts() -> dict[str, int]:
    with SessionLocal() as db:
        return {
            "drafts": db.query(ContentDraft).count(),
            "revision_plans": db.query(DraftRevisionPlan).count(),
            "review_reports": db.query(ReviewReport).count(),
            "strategy_memory": db.query(StrategyMemory).count(),
            "published_notes": db.query(PublishedNote).count(),
        }


def _draft_snapshot(draft_id: int) -> dict:
    with SessionLocal() as db:
        draft = db.get(ContentDraft, draft_id)
        assert draft is not None
        return {
            "id": draft.id,
            "title": draft.title,
            "body": draft.body,
            "recommended_title": draft.recommended_title,
            "body_text": draft.body_text,
            "tag_list": draft.tag_list,
            "cta_text": draft.cta_text,
            "version": draft.version,
            "status": draft.status,
            "generation_context": draft.generation_context,
            "updated_at": draft.updated_at,
        }


def test_confirmed_false_does_not_call_llm_or_create_new_draft(monkeypatch):
    account_id, _, _, _, plan_id = _create_apply_fixture(monkeypatch)
    before = _counts()

    def fail_llm(*args, **kwargs):
        raise AssertionError("LLM should not be called before confirmation")

    monkeypatch.setattr("app.services.draft_revision_apply_sev.LLMClient", fail_llm)

    response = _apply(plan_id, account_id, confirmed=False)

    data = response.json()
    assert response.status_code == 200
    assert data["status"] == "WAITING_CONFIRMATION"
    assert data["revised_draft_id"] is None
    assert _counts() == before


def test_plan_not_found_returns_404_without_llm(monkeypatch):
    account_id = _create_account()

    def fail_llm(*args, **kwargs):
        raise AssertionError("LLM should not be called for missing plan")

    monkeypatch.setattr("app.services.draft_revision_apply_sev.LLMClient", fail_llm)

    response = _apply(999999999, account_id)

    assert response.status_code == 404
    assert response.json()["detail"] == "revision plan not found"


def test_plan_not_ready_returns_blocked_without_llm(monkeypatch):
    account_id, _, _, _, plan_id = _create_apply_fixture(monkeypatch)
    with SessionLocal() as db:
        plan = db.get(DraftRevisionPlan, plan_id)
        assert plan is not None
        plan.status = "FAILED"
        db.commit()
    before = _counts()

    def fail_llm(*args, **kwargs):
        raise AssertionError("LLM should not be called for non-ready plan")

    monkeypatch.setattr("app.services.draft_revision_apply_sev.LLMClient", fail_llm)

    response = _apply(plan_id, account_id)

    data = response.json()
    assert response.status_code == 200
    assert data["status"] == "BLOCKED"
    assert data["error_code"] == "REVISION_PLAN_NOT_READY"
    assert _counts() == before


def test_account_mismatch_returns_400_without_llm(monkeypatch):
    _, _, _, _, plan_id = _create_apply_fixture(monkeypatch)
    other_account_id = _create_account()

    def fail_llm(*args, **kwargs):
        raise AssertionError("LLM should not be called for account mismatch")

    monkeypatch.setattr("app.services.draft_revision_apply_sev.LLMClient", fail_llm)

    response = _apply(plan_id, other_account_id)

    assert response.status_code == 400
    assert response.json()["detail"] == "revision_plan account_id does not match"


def test_source_draft_id_mismatch_returns_blocked_without_llm(monkeypatch):
    account_id, _, _, _, plan_id = _create_apply_fixture(monkeypatch)
    before = _counts()

    def fail_llm(*args, **kwargs):
        raise AssertionError("LLM should not be called for source mismatch")

    monkeypatch.setattr("app.services.draft_revision_apply_sev.LLMClient", fail_llm)

    response = _apply(plan_id, account_id, source_draft_id=999999)

    data = response.json()
    assert response.status_code == 200
    assert data["status"] == "BLOCKED"
    assert data["error_code"] == "SOURCE_DRAFT_MISMATCH"
    assert _counts() == before


def test_stale_plan_returns_stale_without_llm_or_new_draft(monkeypatch):
    account_id, _, source_draft_id, _, plan_id = _create_apply_fixture(monkeypatch)
    with SessionLocal() as db:
        plan = db.get(DraftRevisionPlan, plan_id)
        draft = db.get(ContentDraft, source_draft_id)
        assert plan is not None and draft is not None
        draft.updated_at = plan.base_draft_updated_at + timedelta(seconds=5)
        db.commit()
    before = _counts()

    def fail_llm(*args, **kwargs):
        raise AssertionError("LLM should not be called for stale plan")

    monkeypatch.setattr("app.services.draft_revision_apply_sev.LLMClient", fail_llm)

    response = _apply(plan_id, account_id)

    data = response.json()
    assert response.status_code == 200
    assert data["status"] == "STALE_PLAN"
    assert data["error_code"] == "STALE_PLAN"
    assert data["revised_draft_id"] is None
    assert _counts() == before


def test_provider_unconfigured_returns_status_without_fake_draft(monkeypatch):
    ProviderMissingApplyLLMClient.called = 0
    account_id, _, _, _, plan_id = _create_apply_fixture(monkeypatch)
    before = _counts()
    monkeypatch.setattr("app.services.draft_revision_apply_sev.LLMClient", ProviderMissingApplyLLMClient)

    response = _apply(plan_id, account_id)

    data = response.json()
    assert response.status_code == 200
    assert data["status"] == "PROVIDER_NOT_CONFIGURED"
    assert data["revised_draft_id"] is None
    assert "LLM_CONFIG_MISSING" in data["error_message"]
    assert ProviderMissingApplyLLMClient.called == 1
    assert _counts() == before


def test_fake_llm_client_creates_new_traceable_draft_without_mutating_source(monkeypatch):
    FakeApplyLLMClient.called = 0
    account_id, _, source_draft_id, report_id, plan_id = _create_apply_fixture(monkeypatch)
    conversation_id = _create_conversation(account_id)
    _set_plan_conversation(plan_id, conversation_id)
    before_counts = _counts()
    before_source = _draft_snapshot(source_draft_id)
    monkeypatch.setattr("app.services.draft_revision_apply_sev.LLMClient", FakeApplyLLMClient)

    response = _apply(plan_id, account_id)

    data = response.json()
    assert response.status_code == 200
    assert data["status"] == "CREATED"
    assert data["revised_draft_id"]
    assert data["source_draft_id"] == source_draft_id
    assert data["review_report_id"] == report_id
    assert data["draft"]["title"] == "A more natural revised title"
    assert data["draft"]["content"].startswith("This is the revised body")
    assert data["summary"].startswith("Reduced AI tone")
    assert data["applied_operations"][0]["action"] == "REWRITE"
    assert FakeApplyLLMClient.called == 1
    assert _draft_snapshot(source_draft_id) == before_source
    after_counts = _counts()
    assert after_counts["drafts"] == before_counts["drafts"] + 1
    assert after_counts["revision_plans"] == before_counts["revision_plans"]
    assert after_counts["review_reports"] == before_counts["review_reports"]
    assert after_counts["strategy_memory"] == before_counts["strategy_memory"]
    assert after_counts["published_notes"] == before_counts["published_notes"]
    revised = _draft_snapshot(data["revised_draft_id"])
    assert revised["id"] != source_draft_id
    assert revised["status"] == "REVISED"
    assert revised["version"] == before_source["version"] + 1
    assert revised["generation_context"]["source_draft_id"] == source_draft_id
    assert revised["generation_context"]["revised_from_draft_id"] == source_draft_id
    assert revised["generation_context"]["revision_plan_id"] == plan_id
    assert revised["generation_context"]["review_report_id"] == report_id
    with SessionLocal() as db:
        conversation = db.get(AgentConversation, conversation_id)
        assert conversation is not None
        assert conversation.current_state["current_target_type"] == "DRAFT"
        assert conversation.current_state["current_target_id"] == data["revised_draft_id"]
        assert conversation.current_state["last_action"] == "APPLY_REVISION_PLAN"


def test_invalid_json_returns_failed_without_new_draft(monkeypatch):
    InvalidJSONApplyLLMClient.called = 0
    account_id, _, _, _, plan_id = _create_apply_fixture(monkeypatch)
    before = _counts()
    monkeypatch.setattr("app.services.draft_revision_apply_sev.LLMClient", InvalidJSONApplyLLMClient)

    response = _apply(plan_id, account_id)

    data = response.json()
    assert response.status_code == 200
    assert data["status"] == "FAILED"
    assert data["error_code"] == "LLM_OUTPUT_PARSE_FAILED"
    assert data["revised_draft_id"] is None
    assert InvalidJSONApplyLLMClient.called == 1
    assert _counts() == before


def test_schema_invalid_returns_failed_without_new_draft(monkeypatch):
    InvalidSchemaApplyLLMClient.called = 0
    account_id, _, _, _, plan_id = _create_apply_fixture(monkeypatch)
    before = _counts()
    monkeypatch.setattr("app.services.draft_revision_apply_sev.LLMClient", InvalidSchemaApplyLLMClient)

    response = _apply(plan_id, account_id)

    data = response.json()
    assert response.status_code == 200
    assert data["status"] == "FAILED"
    assert data["error_code"] == "LLM_SCHEMA_INVALID"
    assert data["revised_draft_id"] is None
    assert InvalidSchemaApplyLLMClient.called == 1
    assert _counts() == before


def test_b11_does_not_call_forbidden_workflows(monkeypatch):
    FakeApplyLLMClient.called = 0
    account_id, _, source_draft_id, _, plan_id = _create_apply_fixture(monkeypatch)
    before_source = _draft_snapshot(source_draft_id)
    monkeypatch.setattr("app.services.draft_revision_apply_sev.LLMClient", FakeApplyLLMClient)

    def forbidden_call(*args, **kwargs):
        raise AssertionError("B11 must not call refresh/report/experiment/publish/memory workflows")

    monkeypatch.setattr("app.services.competitor_report_sev.CompetitorReportService.create_report", forbidden_call)
    monkeypatch.setattr("app.services.evidence_refresh_run_sev.EvidenceRefreshRunService.create_run", forbidden_call)
    monkeypatch.setattr("app.services.operation_run_sev.OperationRunService.create_run", forbidden_call)
    monkeypatch.setattr("app.services.operation_experiment_sev.OperationExperimentService.create_from_recommendation", forbidden_call)
    monkeypatch.setattr("app.services.content_draft_v2_sev.ContentDraftV2Service.generate_draft", forbidden_call)
    monkeypatch.setattr("app.services.content_draft_v2_sev.ContentDraftV2Service.regenerate_draft", forbidden_call)
    monkeypatch.setattr("app.services.post_publish_sev.PostPublishService.publish", forbidden_call, raising=False)

    response = _apply(plan_id, account_id)

    data = response.json()
    assert response.status_code == 200
    assert data["status"] == "CREATED"
    assert _draft_snapshot(source_draft_id) == before_source
