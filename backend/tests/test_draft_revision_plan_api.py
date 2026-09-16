from fastapi.testclient import TestClient

from app.core.database import SessionLocal
from app.llm.errors import LLMError
from app.main import app
from app.models.agent_conversation import AgentConversation
from app.models.content_draft import ContentDraft
from app.models.content_experiment import ContentExperiment
from app.models.draft_revision_plan import DraftRevisionPlan
from app.models.published_note import PublishedNote
from app.models.review_report import ReviewReport
from app.models.strategy_memory import StrategyMemory
from app.schemas.draft_revision_plan import RevisionPlanLLMResult
from app.schemas.llm import LLMStructuredResult, LLMUsage
from tests.test_draft_context_preview_api import _create_account
from tests.test_draft_review_api import _create_reviewable_draft


def _client() -> TestClient:
    return TestClient(app)


def _revision_result() -> RevisionPlanLLMResult:
    return RevisionPlanLLMResult.model_validate(
        {
            "summary": "Make the draft less AI-sounding, shorter, and softer.",
            "operations": [
                {
                    "order": 1,
                    "target": "TITLE",
                    "action": "REWRITE",
                    "reason": "User says the title sounds AI-generated.",
                    "instruction": "Use a concrete, natural title without formulaic exaggeration.",
                    "priority": "HIGH",
                },
                {
                    "order": 2,
                    "target": "BODY",
                    "action": "SHORTEN",
                    "reason": "User says the body is too long.",
                    "instruction": "Keep the core example and remove repeated explanations.",
                    "priority": "HIGH",
                },
                {
                    "order": 3,
                    "target": "CTA",
                    "action": "SOFTEN",
                    "reason": "User says the CTA is too hard.",
                    "instruction": "Use a natural interaction-oriented closing.",
                    "priority": "MEDIUM",
                },
            ],
            "preserve": ["Keep the real second paragraph.", "Keep existing facts and data."],
            "must_not_change": ["Do not add anxiety framing."],
            "risk_fixes": ["Align unsupported claims with evidence."],
            "ready_for_revision": True,
        }
    )


class FakeRevisionLLMClient:
    called = 0

    def generate_structured(self, *args, **kwargs) -> LLMStructuredResult:
        FakeRevisionLLMClient.called += 1
        data = _revision_result()
        return LLMStructuredResult(
            data=data,
            text=data.model_dump_json(),
            model="qwen-plus",
            provider="qwen",
            usage=LLMUsage(prompt_tokens=20, completion_tokens=30, total_tokens=50),
            estimated_cost=0,
            raw_response_id="fake-b10-revision-plan-response",
            is_mock=False,
        )


class ProviderMissingRevisionLLMClient:
    called = 0

    def __init__(self):
        ProviderMissingRevisionLLMClient.called += 1
        raise LLMError("LLM_CONFIG_MISSING: provider qwen is not configured")


class InvalidJSONRevisionLLMClient:
    called = 0

    def generate_structured(self, *args, **kwargs):
        InvalidJSONRevisionLLMClient.called += 1
        raise LLMError("invalid json response")


class InvalidSchemaRevisionLLMClient:
    called = 0

    def generate_structured(self, *args, **kwargs) -> LLMStructuredResult:
        InvalidSchemaRevisionLLMClient.called += 1
        return LLMStructuredResult(
            data={"operations": []},
            text='{"operations":[]}',
            model="qwen-plus",
            provider="qwen",
            usage=LLMUsage(prompt_tokens=1, completion_tokens=1, total_tokens=2),
            estimated_cost=0,
            raw_response_id="fake-invalid-schema",
            is_mock=False,
        )


class UnknownActionRevisionLLMClient:
    called = 0

    def generate_structured(self, *args, **kwargs) -> LLMStructuredResult:
        UnknownActionRevisionLLMClient.called += 1
        payload = _revision_result().model_dump()
        payload["operations"][0]["action"] = "MAGIC_REWRITE"
        return LLMStructuredResult(
            data=payload,
            text=str(payload),
            model="qwen-plus",
            provider="qwen",
            usage=LLMUsage(prompt_tokens=1, completion_tokens=1, total_tokens=2),
            estimated_cost=0,
            raw_response_id="fake-unknown-action",
            is_mock=False,
        )


class UnknownTargetRevisionLLMClient:
    called = 0

    def generate_structured(self, *args, **kwargs) -> LLMStructuredResult:
        UnknownTargetRevisionLLMClient.called += 1
        payload = _revision_result().model_dump()
        payload["operations"][0]["target"] = "PRICE"
        return LLMStructuredResult(
            data=payload,
            text=str(payload),
            model="qwen-plus",
            provider="qwen",
            usage=LLMUsage(prompt_tokens=1, completion_tokens=1, total_tokens=2),
            estimated_cost=0,
            raw_response_id="fake-unknown-target",
            is_mock=False,
        )


def _create_review_report(draft_id: int, account_id: int, experiment_id: int) -> int:
    with SessionLocal() as db:
        report = ReviewReport(
            draft_id=draft_id,
            account_id=account_id,
            experiment_id=experiment_id,
            review_type="DRAFT_REVIEW_B9",
            passed=True,
            score=88,
            quality_score=88,
            conversion_score=83,
            evidence_usage_score=78,
            risk_level="LOW",
            issues=[{"field": "cta", "category": "CTA_RISK", "level": "LOW", "message": "CTA can be softer."}],
            suggestions=["Make the title less AI-sounding.", "Shorten the opening."],
            summary="Draft can move forward after small improvements.",
            status="SUCCESS",
        )
        db.add(report)
        db.commit()
        db.refresh(report)
        return report.id


def _create_revision_fixture(monkeypatch) -> tuple[int, int, int, int]:
    account_id, experiment_id, draft_id = _create_reviewable_draft(monkeypatch)
    report_id = _create_review_report(draft_id, account_id, experiment_id)
    return account_id, experiment_id, draft_id, report_id


def _create_conversation(account_id: int) -> int:
    with SessionLocal() as db:
        conversation = AgentConversation(
            account_id=account_id,
            title="B10 conversation",
            current_state={"active_account_id": account_id},
        )
        db.add(conversation)
        db.commit()
        db.refresh(conversation)
        return conversation.id


def _create_plan(draft_id: int, account_id: int, report_id: int | None, confirmed: bool = True, **extra):
    payload = {
        "account_id": account_id,
        "confirmed": confirmed,
        "review_report_id": report_id,
        "feedback_text": "Title sounds too AI, body is too long, and CTA is too hard.",
    }
    payload.update(extra)
    return _client().post(f"/agent/drafts/{draft_id}/revision-plans", json=payload)


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
            "title": draft.title,
            "body": draft.body,
            "recommended_title": draft.recommended_title,
            "body_text": draft.body_text,
            "cta_text": draft.cta_text,
            "status": draft.status,
            "version": draft.version,
            "updated_at": draft.updated_at,
        }


def _experiment_publish_url(experiment_id: int) -> str | None:
    with SessionLocal() as db:
        experiment = db.get(ContentExperiment, experiment_id)
        assert experiment is not None
        return experiment.publish_url


def test_confirmed_false_does_not_call_llm_or_create_revision_plan(monkeypatch):
    account_id, _, draft_id, report_id = _create_revision_fixture(monkeypatch)
    before = _counts()

    def fail_llm(*args, **kwargs):
        raise AssertionError("LLM should not be called before confirmation")

    monkeypatch.setattr("app.services.draft_revision_plan_sev.LLMClient", fail_llm)

    response = _create_plan(draft_id, account_id, report_id, confirmed=False)

    data = response.json()
    assert response.status_code == 200
    assert data["status"] == "WAITING_CONFIRMATION"
    assert data["plan_id"] is None
    assert _counts() == before


def test_draft_not_found_returns_404_without_llm(monkeypatch):
    account_id = _create_account()

    def fail_llm(*args, **kwargs):
        raise AssertionError("LLM should not be called for missing draft")

    monkeypatch.setattr("app.services.draft_revision_plan_sev.LLMClient", fail_llm)

    response = _create_plan(999999999, account_id, None)

    assert response.status_code == 404
    assert response.json()["detail"] == "draft not found"


def test_account_mismatch_returns_400_without_llm(monkeypatch):
    _, _, draft_id, report_id = _create_revision_fixture(monkeypatch)
    other_account_id = _create_account()

    def fail_llm(*args, **kwargs):
        raise AssertionError("LLM should not be called for account mismatch")

    monkeypatch.setattr("app.services.draft_revision_plan_sev.LLMClient", fail_llm)

    response = _create_plan(draft_id, other_account_id, report_id)

    assert response.status_code == 400
    assert response.json()["detail"] == "draft account_id does not match"


def test_feedback_text_empty_returns_400_without_llm(monkeypatch):
    account_id, _, draft_id, report_id = _create_revision_fixture(monkeypatch)

    def fail_llm(*args, **kwargs):
        raise AssertionError("LLM should not be called for empty feedback")

    monkeypatch.setattr("app.services.draft_revision_plan_sev.LLMClient", fail_llm)

    response = _create_plan(draft_id, account_id, report_id, feedback_text="  ")

    assert response.status_code == 400
    assert response.json()["detail"] == "feedback_text must not be empty"


def test_provider_unconfigured_returns_status_without_fake_plan(monkeypatch):
    ProviderMissingRevisionLLMClient.called = 0
    account_id, _, draft_id, report_id = _create_revision_fixture(monkeypatch)
    before = _counts()
    monkeypatch.setattr("app.services.draft_revision_plan_sev.LLMClient", ProviderMissingRevisionLLMClient)

    response = _create_plan(draft_id, account_id, report_id)

    data = response.json()
    assert response.status_code == 200
    assert data["status"] == "PROVIDER_NOT_CONFIGURED"
    assert data["plan_id"] is None
    assert "LLM_CONFIG_MISSING" in data["error_message"]
    assert ProviderMissingRevisionLLMClient.called == 1
    assert _counts() == before


def test_fake_llm_client_creates_revision_plan_without_mutating_draft(monkeypatch):
    FakeRevisionLLMClient.called = 0
    account_id, experiment_id, draft_id, report_id = _create_revision_fixture(monkeypatch)
    conversation_id = _create_conversation(account_id)
    before_counts = _counts()
    before_draft = _draft_snapshot(draft_id)
    monkeypatch.setattr("app.services.draft_revision_plan_sev.LLMClient", FakeRevisionLLMClient)

    response = _create_plan(
        draft_id,
        account_id,
        report_id,
        conversation_id=conversation_id,
        feedback_scope=["TITLE", "BODY", "CTA"],
    )

    data = response.json()
    assert response.status_code == 200
    assert data["status"] == "READY"
    assert data["plan_id"]
    assert data["review_report_id"] == report_id
    assert data["summary"].startswith("Make the draft")
    assert [item["target"] for item in data["operations"]] == ["TITLE", "BODY", "CTA"]
    assert data["feedback_scope"] == ["TITLE", "BODY", "CTA"]
    assert data["preserve"]
    assert data["must_not_change"]
    assert data["risk_fixes"]
    assert data["ready_for_revision"] is True
    assert FakeRevisionLLMClient.called == 1
    assert _draft_snapshot(draft_id) == before_draft
    after_counts = _counts()
    assert after_counts["revision_plans"] == before_counts["revision_plans"] + 1
    assert after_counts["drafts"] == before_counts["drafts"]
    assert after_counts["review_reports"] == before_counts["review_reports"]
    assert after_counts["strategy_memory"] == before_counts["strategy_memory"]
    assert after_counts["published_notes"] == before_counts["published_notes"]
    assert _experiment_publish_url(experiment_id) is None
    with SessionLocal() as db:
        plan = db.get(DraftRevisionPlan, data["plan_id"])
        assert plan is not None
        assert plan.feedback_text.startswith("Title sounds")
        assert plan.base_draft_updated_at == before_draft["updated_at"]
        conversation = db.get(AgentConversation, conversation_id)
        assert conversation is not None
        assert conversation.current_state["current_target_type"] == "DRAFT"
        assert conversation.current_state["current_target_id"] == draft_id
        assert conversation.current_state["last_action"] == "CREATE_REVISION_PLAN"


def test_latest_review_report_is_used_when_request_does_not_specify_one(monkeypatch):
    FakeRevisionLLMClient.called = 0
    account_id, _, draft_id, report_id = _create_revision_fixture(monkeypatch)
    monkeypatch.setattr("app.services.draft_revision_plan_sev.LLMClient", FakeRevisionLLMClient)

    response = _create_plan(draft_id, account_id, None)

    data = response.json()
    assert response.status_code == 200
    assert data["status"] == "READY"
    assert data["review_report_id"] == report_id


def test_invalid_json_returns_failed_without_plan(monkeypatch):
    InvalidJSONRevisionLLMClient.called = 0
    account_id, _, draft_id, report_id = _create_revision_fixture(monkeypatch)
    before = _counts()
    monkeypatch.setattr("app.services.draft_revision_plan_sev.LLMClient", InvalidJSONRevisionLLMClient)

    response = _create_plan(draft_id, account_id, report_id)

    data = response.json()
    assert response.status_code == 200
    assert data["status"] == "FAILED"
    assert data["plan_id"] is None
    assert data["error_code"] == "LLM_OUTPUT_PARSE_FAILED"
    assert InvalidJSONRevisionLLMClient.called == 1
    assert _counts() == before


def test_schema_invalid_returns_failed_without_plan(monkeypatch):
    InvalidSchemaRevisionLLMClient.called = 0
    account_id, _, draft_id, report_id = _create_revision_fixture(monkeypatch)
    before = _counts()
    monkeypatch.setattr("app.services.draft_revision_plan_sev.LLMClient", InvalidSchemaRevisionLLMClient)

    response = _create_plan(draft_id, account_id, report_id)

    data = response.json()
    assert response.status_code == 200
    assert data["status"] == "FAILED"
    assert data["plan_id"] is None
    assert data["error_code"] == "LLM_SCHEMA_INVALID"
    assert InvalidSchemaRevisionLLMClient.called == 1
    assert _counts() == before


def test_unknown_action_returns_failed_without_plan(monkeypatch):
    UnknownActionRevisionLLMClient.called = 0
    account_id, _, draft_id, report_id = _create_revision_fixture(monkeypatch)
    before = _counts()
    monkeypatch.setattr("app.services.draft_revision_plan_sev.LLMClient", UnknownActionRevisionLLMClient)

    response = _create_plan(draft_id, account_id, report_id)

    data = response.json()
    assert response.status_code == 200
    assert data["status"] == "FAILED"
    assert data["plan_id"] is None
    assert data["error_code"] == "LLM_SCHEMA_INVALID"
    assert UnknownActionRevisionLLMClient.called == 1
    assert _counts() == before


def test_unknown_target_returns_failed_without_plan(monkeypatch):
    UnknownTargetRevisionLLMClient.called = 0
    account_id, _, draft_id, report_id = _create_revision_fixture(monkeypatch)
    before = _counts()
    monkeypatch.setattr("app.services.draft_revision_plan_sev.LLMClient", UnknownTargetRevisionLLMClient)

    response = _create_plan(draft_id, account_id, report_id)

    data = response.json()
    assert response.status_code == 200
    assert data["status"] == "FAILED"
    assert data["plan_id"] is None
    assert data["error_code"] == "LLM_SCHEMA_INVALID"
    assert UnknownTargetRevisionLLMClient.called == 1
    assert _counts() == before


def test_get_and_list_revision_plans(monkeypatch):
    FakeRevisionLLMClient.called = 0
    account_id, _, draft_id, report_id = _create_revision_fixture(monkeypatch)
    monkeypatch.setattr("app.services.draft_revision_plan_sev.LLMClient", FakeRevisionLLMClient)
    created = _create_plan(draft_id, account_id, report_id).json()

    listed = _client().get(f"/agent/drafts/{draft_id}/revision-plans")
    fetched = _client().get(f"/agent/revision-plans/{created['plan_id']}")

    assert listed.status_code == 200
    assert listed.json()[0]["id"] == created["plan_id"]
    assert fetched.status_code == 200
    assert fetched.json()["id"] == created["plan_id"]


def test_b10_does_not_call_forbidden_workflows(monkeypatch):
    FakeRevisionLLMClient.called = 0
    account_id, _, draft_id, report_id = _create_revision_fixture(monkeypatch)
    before_draft = _draft_snapshot(draft_id)
    monkeypatch.setattr("app.services.draft_revision_plan_sev.LLMClient", FakeRevisionLLMClient)

    def forbidden_call(*args, **kwargs):
        raise AssertionError("B10 must not call generation, refresh, publish, or memory workflows")

    monkeypatch.setattr("app.services.competitor_report_sev.CompetitorReportService.create_report", forbidden_call)
    monkeypatch.setattr("app.services.evidence_refresh_run_sev.EvidenceRefreshRunService.create_run", forbidden_call)
    monkeypatch.setattr("app.services.operation_run_sev.OperationRunService.create_run", forbidden_call)
    monkeypatch.setattr("app.services.operation_experiment_sev.OperationExperimentService.create_from_recommendation", forbidden_call)
    monkeypatch.setattr("app.services.content_draft_v2_sev.ContentDraftV2Service.generate_draft", forbidden_call)
    monkeypatch.setattr("app.services.content_draft_v2_sev.ContentDraftV2Service.regenerate_draft", forbidden_call)
    monkeypatch.setattr("app.services.post_publish_sev.PostPublishService.publish", forbidden_call, raising=False)

    response = _create_plan(draft_id, account_id, report_id)

    data = response.json()
    assert response.status_code == 200
    assert data["status"] == "READY"
    assert _draft_snapshot(draft_id) == before_draft
