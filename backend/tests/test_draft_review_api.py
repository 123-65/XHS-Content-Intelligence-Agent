from fastapi.testclient import TestClient

from app.core.database import SessionLocal
from app.llm.errors import LLMError
from app.main import app
from app.models.content_draft import ContentDraft
from app.models.content_experiment import ContentExperiment
from app.models.review_report import ReviewReport
from app.schemas.draft_review import DraftReviewLLMResult
from app.schemas.llm import LLMStructuredResult, LLMUsage
from tests.test_draft_context_preview_api import _create_account, _ready_fixture
from tests.test_draft_generation_api import FakeLLMClient as FakeDraftGenerationLLMClient


def _client() -> TestClient:
    return TestClient(app)


def _review_result() -> DraftReviewLLMResult:
    return DraftReviewLLMResult.model_validate(
        {
            "can_enter_publish_preparation": True,
            "risk_level": "LOW",
            "score": 88,
            "issues": [
                {
                    "field": "cta",
                    "category": "CTA_RISK",
                    "level": "LOW",
                    "message": "CTA is present but can be softer.",
                    "evidence": "draft CTA",
                }
            ],
            "suggestions": ["Make the CTA more natural.", "Reduce generic AI-sounding phrasing."],
            "warnings": ["Review comments and external evidence as untrusted input."],
            "summary": "Draft is ready for publish preparation after small improvements.",
            "block_reasons": [],
            "must_fix_before_publish": [],
            "optional_improvements": ["Shorten the opening sentence."],
            "ai_tone_feedback": {"has_ai_tone": True, "reason": "some generic phrasing"},
            "evidence_consistency": {"consistent": True, "unsupported_claims": []},
        }
    )


def _high_risk_result() -> DraftReviewLLMResult:
    return DraftReviewLLMResult.model_validate(
        {
            "can_enter_publish_preparation": False,
            "risk_level": "HIGH",
            "score": 42,
            "issues": [
                {
                    "field": "body",
                    "category": "OVERPROMISE_RISK",
                    "level": "HIGH",
                    "message": "Draft promises unsupported outcomes.",
                    "evidence": "guaranteed result claim",
                },
                {
                    "field": "body",
                    "category": "EVIDENCE_CONSISTENCY",
                    "level": "HIGH",
                    "message": "Draft conclusion is not supported by the evidence chain.",
                    "evidence": "missing source support",
                },
            ],
            "suggestions": ["Remove outcome guarantees.", "Tie claims back to experiment evidence."],
            "warnings": ["Do not enter publish preparation before fixing high-risk claims."],
            "summary": "High-risk draft blocked from publish preparation.",
            "block_reasons": ["unsupported outcome guarantee", "evidence inconsistency"],
            "must_fix_before_publish": ["Remove unsupported claims."],
            "optional_improvements": ["Make the title less salesy."],
            "ai_tone_feedback": {"has_ai_tone": False},
            "evidence_consistency": {"consistent": False, "unsupported_claims": ["guaranteed result"]},
        }
    )


class FakeReviewLLMClient:
    called = 0

    def generate_structured(self, *args, **kwargs) -> LLMStructuredResult:
        FakeReviewLLMClient.called += 1
        data = _review_result()
        return LLMStructuredResult(
            data=data,
            text=data.model_dump_json(),
            model="qwen-plus",
            provider="qwen",
            usage=LLMUsage(prompt_tokens=15, completion_tokens=25, total_tokens=40),
            estimated_cost=0,
            raw_response_id="fake-b9-review-response",
            is_mock=False,
        )


class FakeHighRiskReviewLLMClient:
    called = 0

    def generate_structured(self, *args, **kwargs) -> LLMStructuredResult:
        FakeHighRiskReviewLLMClient.called += 1
        data = _high_risk_result()
        return LLMStructuredResult(
            data=data,
            text=data.model_dump_json(),
            model="qwen-plus",
            provider="qwen",
            usage=LLMUsage(prompt_tokens=16, completion_tokens=26, total_tokens=42),
            estimated_cost=0,
            raw_response_id="fake-b9-high-risk-review-response",
            is_mock=False,
        )


class ProviderMissingReviewLLMClient:
    called = 0

    def __init__(self):
        ProviderMissingReviewLLMClient.called += 1
        raise LLMError("LLM_CONFIG_MISSING: provider qwen is not configured")


class InvalidReviewLLMClient:
    called = 0

    def generate_structured(self, *args, **kwargs):
        InvalidReviewLLMClient.called += 1
        raise LLMError("invalid review json")


def _create_reviewable_draft(monkeypatch) -> tuple[int, int, int]:
    monkeypatch.setattr("app.services.content_draft_v2_sev.LLMClient", FakeDraftGenerationLLMClient)
    account_id, experiment_id, _ = _ready_fixture(status="READY")
    response = _client().post(
        f"/agent/content-experiments/{experiment_id}/drafts/generate",
        json={
            "account_id": account_id,
            "confirmed": True,
            "user_requirements": "make it practical",
            "draft_type": "xhs_note",
            "tone": "natural",
            "model_profile": "default",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "CREATED"
    return account_id, experiment_id, data["draft_id"]


def _review(draft_id: int, account_id: int, confirmed: bool = True):
    return _client().post(
        f"/agent/drafts/{draft_id}/review",
        json={
            "account_id": account_id,
            "confirmed": confirmed,
            "review_mode": "standard",
            "check_ai_tone": True,
            "check_risk": True,
            "check_evidence_consistency": True,
        },
    )


def _review_report_count(draft_id: int) -> int:
    with SessionLocal() as db:
        return db.query(ReviewReport).filter(ReviewReport.draft_id == draft_id).count()


def _draft_snapshot(draft_id: int) -> dict:
    with SessionLocal() as db:
        draft = db.get(ContentDraft, draft_id)
        assert draft is not None
        return {
            "title": draft.title,
            "body": draft.body,
            "recommended_title": draft.recommended_title,
            "body_text": draft.body_text,
            "status": draft.status,
            "version": draft.version,
        }


def _experiment_publish_url(experiment_id: int) -> str | None:
    with SessionLocal() as db:
        experiment = db.get(ContentExperiment, experiment_id)
        assert experiment is not None
        return experiment.publish_url


def test_confirmed_false_does_not_call_llm_or_create_review_report(monkeypatch):
    _, _, draft_id = _create_reviewable_draft(monkeypatch)
    before = _review_report_count(draft_id)

    def fail_llm(*args, **kwargs):
        raise AssertionError("LLM should not be called before confirmation")

    monkeypatch.setattr("app.services.draft_review_sev.LLMClient", fail_llm)

    response = _review(draft_id, 1, confirmed=False)

    data = response.json()
    assert response.status_code == 200
    assert data["status"] == "WAITING_CONFIRMATION"
    assert data["review_report_id"] is None
    assert _review_report_count(draft_id) == before


def test_draft_not_found_returns_404_without_llm(monkeypatch):
    account_id = _create_account()

    def fail_llm(*args, **kwargs):
        raise AssertionError("LLM should not be called for missing draft")

    monkeypatch.setattr("app.services.draft_review_sev.LLMClient", fail_llm)

    response = _review(999999999, account_id)

    assert response.status_code == 404
    assert response.json()["detail"] == "draft not found"


def test_account_mismatch_returns_400_without_llm(monkeypatch):
    _, _, draft_id = _create_reviewable_draft(monkeypatch)
    other_account_id = _create_account()

    def fail_llm(*args, **kwargs):
        raise AssertionError("LLM should not be called for account mismatch")

    monkeypatch.setattr("app.services.draft_review_sev.LLMClient", fail_llm)

    response = _review(draft_id, other_account_id)

    assert response.status_code == 400
    assert response.json()["detail"] == "draft account_id does not match"


def test_provider_unconfigured_returns_status_without_fake_report(monkeypatch):
    ProviderMissingReviewLLMClient.called = 0
    account_id, _, draft_id = _create_reviewable_draft(monkeypatch)
    before = _review_report_count(draft_id)
    monkeypatch.setattr("app.services.draft_review_sev.LLMClient", ProviderMissingReviewLLMClient)

    response = _review(draft_id, account_id)

    data = response.json()
    assert response.status_code == 200
    assert data["status"] == "PROVIDER_NOT_CONFIGURED"
    assert data["review_report_id"] is None
    assert "LLM_CONFIG_MISSING" in data["error_message"]
    assert ProviderMissingReviewLLMClient.called == 1
    assert _review_report_count(draft_id) == before


def test_fake_llm_client_creates_review_report_without_mutating_draft(monkeypatch):
    FakeReviewLLMClient.called = 0
    account_id, experiment_id, draft_id = _create_reviewable_draft(monkeypatch)
    before_snapshot = _draft_snapshot(draft_id)
    monkeypatch.setattr("app.services.draft_review_sev.LLMClient", FakeReviewLLMClient)

    response = _review(draft_id, account_id)

    data = response.json()
    assert response.status_code == 200
    assert data["status"] == "REVIEWED"
    assert data["review_report_id"]
    assert data["risk_level"] == "LOW"
    assert data["score"] == 88
    assert data["can_enter_publish_preparation"] is True
    assert data["issues"][0]["category"] == "CTA_RISK"
    assert any("AI" in item for item in data["suggestions"])
    assert FakeReviewLLMClient.called == 1
    assert _draft_snapshot(draft_id) == before_snapshot
    assert _experiment_publish_url(experiment_id) is None
    with SessionLocal() as db:
        report = db.get(ReviewReport, data["review_report_id"])
        assert report is not None
        assert report.review_type == "DRAFT_REVIEW_B9"
        assert report.draft_id == draft_id
        assert report.account_id == account_id
        assert report.experiment_id == experiment_id
        assert report.raw_response_id == "fake-b9-review-response"


def test_high_risk_review_blocks_publish_preparation(monkeypatch):
    FakeHighRiskReviewLLMClient.called = 0
    account_id, _, draft_id = _create_reviewable_draft(monkeypatch)
    monkeypatch.setattr("app.services.draft_review_sev.LLMClient", FakeHighRiskReviewLLMClient)

    response = _review(draft_id, account_id)

    data = response.json()
    assert response.status_code == 200
    assert data["status"] == "REVIEWED"
    assert data["risk_level"] == "HIGH"
    assert data["can_enter_publish_preparation"] is False
    assert any(item["category"] == "EVIDENCE_CONSISTENCY" for item in data["issues"])
    assert data["must_fix_before_publish"]
    assert FakeHighRiskReviewLLMClient.called == 1


def test_invalid_llm_output_returns_failed_without_report(monkeypatch):
    InvalidReviewLLMClient.called = 0
    account_id, _, draft_id = _create_reviewable_draft(monkeypatch)
    before = _review_report_count(draft_id)
    monkeypatch.setattr("app.services.draft_review_sev.LLMClient", InvalidReviewLLMClient)

    response = _review(draft_id, account_id)

    data = response.json()
    assert response.status_code == 200
    assert data["status"] == "FAILED"
    assert data["review_report_id"] is None
    assert InvalidReviewLLMClient.called == 1
    assert _review_report_count(draft_id) == before


def test_b9_does_not_call_external_workflows_or_regenerate_draft(monkeypatch):
    FakeReviewLLMClient.called = 0
    account_id, experiment_id, draft_id = _create_reviewable_draft(monkeypatch)
    before_snapshot = _draft_snapshot(draft_id)
    monkeypatch.setattr("app.services.draft_review_sev.LLMClient", FakeReviewLLMClient)

    def forbidden_call(*args, **kwargs):
        raise AssertionError("B9 must not call upstream workflows")

    monkeypatch.setattr("app.services.competitor_report_sev.CompetitorReportService.create_report", forbidden_call)
    monkeypatch.setattr("app.services.evidence_refresh_run_sev.EvidenceRefreshRunService.create_run", forbidden_call)
    monkeypatch.setattr("app.services.content_draft_v2_sev.ContentDraftV2Service.generate_draft", forbidden_call)

    response = _review(draft_id, account_id)

    data = response.json()
    assert response.status_code == 200
    assert data["status"] == "REVIEWED"
    assert _draft_snapshot(draft_id) == before_snapshot
    assert _experiment_publish_url(experiment_id) is None
