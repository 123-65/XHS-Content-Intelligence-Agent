import pytest
from fastapi.testclient import TestClient

from app.core.database import SessionLocal
from app.llm.errors import LLMError
from app.main import app
from app.models.competitors_analysis import CompetitorAnalysisReport
from app.models.content_draft import ContentDraft
from app.models.content_experiment import ContentExperiment
from app.models.content_opportunity import ContentOpportunity
from app.schemas.llm import LLMStructuredResult, LLMUsage
from app.schemas.content_draft_v2 import DraftGenerateV2Result
from tests.test_draft_context_preview_api import _create_account, _create_experiment, _ready_fixture


def _client() -> TestClient:
    return TestClient(app)


def _draft_result() -> DraftGenerateV2Result:
    return DraftGenerateV2Result.model_validate(
        {
            "title_candidates": ["B8 title one", "B8 title two", "B8 title three"],
            "recommended_title": "B8 title one",
            "cover_text": "B8 cover",
            "cover_subtitle": "B8 subtitle",
            "body_text": "B8 generated draft body from confirmed context.",
            "image_script": [
                {"index": 1, "title": "Hook", "content": "Open with the user pain.", "visual_hint": "cover"},
                {"index": 2, "title": "Evidence", "content": "Use existing evidence.", "visual_hint": "list"},
                {"index": 3, "title": "Method", "content": "Show the workflow.", "visual_hint": "flow"},
                {"index": 4, "title": "Close", "content": "End with a soft CTA.", "visual_hint": "checklist"},
            ],
            "tag_list": ["AI Agent", "content"],
            "keyword_list": ["draft generation", "context preview"],
            "cta_text": "Save this and test it with your next draft.",
        }
    )


class FakeLLMClient:
    called = 0

    def generate_structured_with_context(self, *args, **kwargs) -> LLMStructuredResult:
        FakeLLMClient.called += 1
        data = _draft_result()
        return LLMStructuredResult(
            data=data,
            text=data.model_dump_json(),
            model="qwen-plus",
            provider="qwen",
            usage=LLMUsage(prompt_tokens=10, completion_tokens=20, total_tokens=30),
            estimated_cost=0,
            raw_response_id="fake-b8-draft-response",
            is_mock=False,
        )


class ProviderMissingLLMClient:
    called = 0

    def __init__(self):
        ProviderMissingLLMClient.called += 1
        raise LLMError("LLM_CONFIG_MISSING: provider qwen is not configured")


class InvalidJSONLLMClient:
    called = 0

    def generate_structured_with_context(self, *args, **kwargs):
        InvalidJSONLLMClient.called += 1
        raise LLMError("invalid json response")


def _counts() -> dict[str, int]:
    with SessionLocal() as db:
        return {
            "drafts": db.query(ContentDraft).count(),
            "experiments": db.query(ContentExperiment).count(),
            "opportunities": db.query(ContentOpportunity).count(),
            "reports": db.query(CompetitorAnalysisReport).count(),
        }


def _draft(draft_id: int) -> ContentDraft | None:
    with SessionLocal() as db:
        return db.get(ContentDraft, draft_id)


def _experiment(experiment_id: int) -> ContentExperiment | None:
    with SessionLocal() as db:
        return db.get(ContentExperiment, experiment_id)


def _generate(experiment_id: int, account_id: int, confirmed: bool = True, user_requirements: str | None = "make it natural"):
    return _client().post(
        f"/agent/content-experiments/{experiment_id}/drafts/generate",
        json={
            "account_id": account_id,
            "confirmed": confirmed,
            "user_requirements": user_requirements,
            "draft_type": "xhs_note",
            "tone": "natural",
            "model_profile": "default",
        },
    )


def test_confirmed_false_does_not_call_llm_or_create_draft(monkeypatch):
    account_id, experiment_id, _ = _ready_fixture(status="READY")
    before = _counts()

    def fail_llm(*args, **kwargs):
        raise AssertionError("LLM should not be called before confirmation")

    monkeypatch.setattr("app.services.content_draft_v2_sev.LLMClient", fail_llm)

    response = _generate(experiment_id, account_id, confirmed=False)

    after = _counts()
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "WAITING_CONFIRMATION"
    assert data["draft_id"] is None
    assert data["draft"] is None
    assert after == before


def test_experiment_missing_returns_404():
    account_id = _create_account()

    response = _generate(999999999, account_id)

    assert response.status_code == 404
    assert response.json()["detail"] == "experiment not found"


def test_account_mismatch_returns_400():
    account_id, experiment_id, _ = _ready_fixture(status="READY")
    other_account_id = _create_account()

    response = _generate(experiment_id, other_account_id)

    assert response.status_code == 400
    assert response.json()["detail"] == "experiment account_id does not match"
    assert account_id != other_account_id


def test_experiment_not_ready_is_blocked_without_llm(monkeypatch):
    account_id, experiment_id, _ = _ready_fixture(status="DRAFT")
    before = _counts()

    def fail_llm(*args, **kwargs):
        raise AssertionError("LLM should not be called for non-READY experiments")

    monkeypatch.setattr("app.services.content_draft_v2_sev.LLMClient", fail_llm)

    response = _generate(experiment_id, account_id)

    after = _counts()
    data = response.json()
    assert response.status_code == 200
    assert data["status"] == "BLOCKED"
    assert data["error_code"] == "EXPERIMENT_NOT_READY"
    assert data["draft_id"] is None
    assert after == before


def test_b7_preview_not_ready_blocks_generation_without_llm(monkeypatch):
    account_id = _create_account()
    experiment_id = _create_experiment(account_id, status="READY")
    before = _counts()

    def fail_llm(*args, **kwargs):
        raise AssertionError("LLM should not be called when B7 context is not ready")

    monkeypatch.setattr("app.services.content_draft_v2_sev.LLMClient", fail_llm)

    response = _generate(experiment_id, account_id)

    after = _counts()
    data = response.json()
    assert response.status_code == 200
    assert data["status"] == "DATA_INSUFFICIENT"
    assert data["draft_id"] is None
    assert data["missing_context"]
    assert after == before


def test_provider_unconfigured_returns_status_without_fake_draft(monkeypatch):
    ProviderMissingLLMClient.called = 0
    monkeypatch.setattr("app.services.content_draft_v2_sev.LLMClient", ProviderMissingLLMClient)
    account_id, experiment_id, _ = _ready_fixture(status="READY")
    before = _counts()

    response = _generate(experiment_id, account_id)

    after = _counts()
    data = response.json()
    assert response.status_code == 200
    assert data["status"] == "PROVIDER_NOT_CONFIGURED"
    assert data["provider"] == "unknown"
    assert data["draft_id"] is None
    assert data["draft"] is None
    assert ProviderMissingLLMClient.called == 1
    assert after == before


def test_fake_llm_client_generates_and_persists_content_draft_v2(monkeypatch):
    FakeLLMClient.called = 0
    monkeypatch.setattr("app.services.content_draft_v2_sev.LLMClient", FakeLLMClient)
    account_id, experiment_id, _ = _ready_fixture(status="READY")
    before = _counts()

    response = _generate(experiment_id, account_id, user_requirements="keep it useful")

    after = _counts()
    data = response.json()
    assert response.status_code == 200
    assert data["status"] == "CREATED"
    assert data["draft_id"]
    assert data["provider"] == "qwen"
    assert data["draft"] == {
        "title": "B8 title one",
        "content": "B8 generated draft body from confirmed context.",
        "tags": ["AI Agent", "content"],
        "cta": "Save this and test it with your next draft.",
    }
    assert FakeLLMClient.called == 1
    assert after["drafts"] == before["drafts"] + 1
    assert after["experiments"] == before["experiments"]
    assert after["opportunities"] == before["opportunities"]
    assert after["reports"] == before["reports"]
    persisted = _draft(data["draft_id"])
    assert persisted is not None
    assert persisted.recommended_title == "B8 title one"
    experiment = _experiment(experiment_id)
    assert experiment is not None
    assert experiment.publish_url is None
    assert persisted.status == "GENERATED"


def test_invalid_llm_output_returns_failed_without_draft(monkeypatch):
    InvalidJSONLLMClient.called = 0
    monkeypatch.setattr("app.services.content_draft_v2_sev.LLMClient", InvalidJSONLLMClient)
    account_id, experiment_id, _ = _ready_fixture(status="READY")
    before = _counts()

    response = _generate(experiment_id, account_id)

    after = _counts()
    data = response.json()
    assert response.status_code == 200
    assert data["status"] == "FAILED"
    assert data["error_code"] == "LLM_RESPONSE_INVALID"
    assert data["draft_id"] is None
    assert data["draft"] is None
    assert InvalidJSONLLMClient.called == 1
    assert after == before


def test_b8_does_not_call_external_workflows_or_publish(monkeypatch):
    FakeLLMClient.called = 0
    monkeypatch.setattr("app.services.content_draft_v2_sev.LLMClient", FakeLLMClient)

    def forbidden_call(*args, **kwargs):
        raise AssertionError("B8 must not call refresh/report/experiment creation workflows")

    monkeypatch.setattr("app.services.competitor_report_sev.CompetitorReportService.create_report", forbidden_call)
    monkeypatch.setattr("app.services.evidence_refresh_run_sev.EvidenceRefreshRunService.create_run", forbidden_call)
    monkeypatch.setattr("app.services.operation_experiment_sev.OperationExperimentService.create_from_recommendation", forbidden_call)
    account_id, experiment_id, _ = _ready_fixture(status="READY")

    response = _generate(experiment_id, account_id)

    data = response.json()
    assert response.status_code == 200
    assert data["status"] == "CREATED"
    draft = _draft(data["draft_id"])
    assert draft is not None
    experiment = _experiment(experiment_id)
    assert experiment is not None
    assert experiment.publish_url is None
    assert FakeLLMClient.called == 1
