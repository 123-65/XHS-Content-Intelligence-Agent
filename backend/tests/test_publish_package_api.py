from fastapi.testclient import TestClient

from app.core.database import SessionLocal
from app.main import app
from app.models.competitor_comment import CompetitorComment
from app.models.content_draft import ContentDraft
from app.models.content_experiment import ContentExperiment
from app.models.content_opportunity import ContentOpportunity
from app.models.note_comment_snapshot import NoteCommentSnapshot
from app.models.publish_package import PublishPackage
from app.models.published_note import PublishedNote
from app.models.review_report import ReviewReport
from app.models.strategy_memory import StrategyMemory
from tests.test_draft_context_preview_api import _create_account
from tests.test_draft_revision_apply_api import FakeApplyLLMClient, _apply, _create_apply_fixture


def _client() -> TestClient:
    return TestClient(app)


def _create_final_draft(monkeypatch) -> tuple[int, int, int, int, int]:
    account_id, experiment_id, source_draft_id, _, plan_id = _create_apply_fixture(monkeypatch)
    FakeApplyLLMClient.called = 0
    monkeypatch.setattr("app.services.draft_revision_apply_sev.LLMClient", FakeApplyLLMClient)
    response = _apply(plan_id, account_id)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "CREATED"
    return account_id, experiment_id, source_draft_id, data["revised_draft_id"], plan_id


def _create_review_report(
    draft_id: int,
    account_id: int,
    experiment_id: int,
    risk_level: str = "LOW",
    passed: bool = True,
) -> int:
    with SessionLocal() as db:
        report = ReviewReport(
            draft_id=draft_id,
            account_id=account_id,
            experiment_id=experiment_id,
            review_type="DRAFT_REVIEW_B9",
            passed=passed,
            score=86 if passed else 38,
            quality_score=84 if passed else 35,
            conversion_score=80 if passed else 30,
            evidence_usage_score=78 if passed else 20,
            risk_level=risk_level,
            issues=[] if passed else [{"field": "body", "category": "OVERPROMISE_RISK", "level": "HIGH", "message": "Risky claim."}],
            suggestions=["Ready for manual packaging."] if passed else ["Fix risky claims before publishing."],
            summary="Low-risk draft review." if passed else "High-risk draft review.",
            status="SUCCESS",
        )
        db.add(report)
        db.commit()
        db.refresh(report)
        return report.id


def _create_package(draft_id: int, account_id: int, confirmed: bool = True, **extra):
    payload = {
        "account_id": account_id,
        "confirmed": confirmed,
        "style": "clean_knowledge_card",
        "card_count": 5,
    }
    payload.update(extra)
    return _client().post(f"/agent/drafts/{draft_id}/publish-packages", json=payload)


def _counts() -> dict[str, int]:
    with SessionLocal() as db:
        return {
            "drafts": db.query(ContentDraft).count(),
            "experiments": db.query(ContentExperiment).count(),
            "opportunities": db.query(ContentOpportunity).count(),
            "review_reports": db.query(ReviewReport).count(),
            "publish_packages": db.query(PublishPackage).count(),
            "published_notes": db.query(PublishedNote).count(),
            "strategy_memory": db.query(StrategyMemory).count(),
            "competitor_comments": db.query(CompetitorComment).count(),
            "note_comment_snapshots": db.query(NoteCommentSnapshot).count(),
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


def _blank_draft(draft_id: int) -> None:
    with SessionLocal() as db:
        draft = db.get(ContentDraft, draft_id)
        assert draft is not None
        draft.title = ""
        draft.body = ""
        draft.recommended_title = ""
        draft.body_text = ""
        draft.tag_list = []
        draft.cta_text = None
        db.commit()


def test_confirmed_false_does_not_create_package_or_call_llm(monkeypatch):
    account_id, _, _, draft_id, _ = _create_final_draft(monkeypatch)
    before = _counts()

    def fail_llm(*args, **kwargs):
        raise AssertionError("B12 must not call LLM before confirmation")

    monkeypatch.setattr("app.llm.client.LLMClient.__init__", fail_llm, raising=False)

    response = _create_package(draft_id, account_id, confirmed=False)

    data = response.json()
    assert response.status_code == 200
    assert data["status"] == "WAITING_CONFIRMATION"
    assert data["package_id"] is None
    assert data["confirmation"]["requires_confirmation"] is True
    assert _counts() == before


def test_draft_not_found_returns_404_without_side_effects(monkeypatch):
    account_id = _create_account()
    before = _counts()

    def fail_llm(*args, **kwargs):
        raise AssertionError("B12 must not call LLM for a missing draft")

    monkeypatch.setattr("app.llm.client.LLMClient.__init__", fail_llm, raising=False)

    response = _create_package(999999999, account_id)

    assert response.status_code == 404
    assert response.json()["detail"] == "draft not found"
    assert _counts() == before


def test_account_mismatch_returns_400_without_package(monkeypatch):
    _, _, _, draft_id, _ = _create_final_draft(monkeypatch)
    other_account_id = _create_account()
    before = _counts()

    response = _create_package(draft_id, other_account_id)

    assert response.status_code == 400
    assert response.json()["detail"] == "draft account_id does not match"
    assert _counts() == before


def test_empty_draft_returns_data_insufficient_without_package(monkeypatch):
    account_id, _, _, draft_id, _ = _create_final_draft(monkeypatch)
    _blank_draft(draft_id)
    before = _counts()

    response = _create_package(draft_id, account_id)

    data = response.json()
    assert response.status_code == 200
    assert data["status"] == "DATA_INSUFFICIENT"
    assert data["error_code"] == "DRAFT_CONTENT_EMPTY"
    assert _counts() == before


def test_create_publish_package_from_final_draft(monkeypatch):
    account_id, experiment_id, _, draft_id, plan_id = _create_final_draft(monkeypatch)
    report_id = _create_review_report(draft_id, account_id, experiment_id)
    before_counts = _counts()
    before_draft = _draft_snapshot(draft_id)

    response = _create_package(draft_id, account_id, review_report_id=report_id, card_count=4)

    data = response.json()
    assert response.status_code == 200
    assert data["status"] == "READY"
    assert data["package_id"]
    assert data["draft_id"] == draft_id
    assert data["review_report_id"] == report_id
    assert data["revision_plan_id"] == plan_id
    assert data["source_type"] == "REVISED_DRAFT"
    assert data["title"] == before_draft["recommended_title"]
    assert data["body"] == before_draft["body_text"]
    assert data["tags"] == before_draft["tag_list"]
    assert data["cta"] == before_draft["cta_text"]
    assert data["cover_card"]["card_type"] == "cover"
    assert data["cover_card"]["style"] == "clean_knowledge_card"
    assert 2 <= len(data["image_cards"]) <= 4
    assert data["image_cards"][0]["card_type"] == "cover"
    assert any(item["level"] == "REQUIRED" for item in data["publish_checklist"])
    assert any("Open XHS yourself" in item for item in data["manual_publish_steps"])
    assert data["warnings"] == []
    assert data["stats"]["llm_called"] is False
    assert data["stats"]["auto_publish"] is False
    assert data["stats"]["template_generation"] == "frontend_canvas"
    assert _draft_snapshot(draft_id) == before_draft
    after_counts = _counts()
    assert after_counts["publish_packages"] == before_counts["publish_packages"] + 1
    assert after_counts["drafts"] == before_counts["drafts"]
    assert after_counts["published_notes"] == before_counts["published_notes"]
    assert after_counts["strategy_memory"] == before_counts["strategy_memory"]


def test_package_without_review_report_requires_manual_review(monkeypatch):
    account_id, _, _, draft_id, _ = _create_final_draft(monkeypatch)

    response = _create_package(draft_id, account_id)

    data = response.json()
    assert response.status_code == 200
    assert data["status"] == "NEEDS_REVIEW"
    assert data["review_report_id"] is None
    assert any("No ReviewReport" in item for item in data["warnings"])


def test_high_risk_review_keeps_package_but_marks_needs_review(monkeypatch):
    account_id, experiment_id, _, draft_id, _ = _create_final_draft(monkeypatch)
    report_id = _create_review_report(draft_id, account_id, experiment_id, risk_level="HIGH", passed=False)

    response = _create_package(draft_id, account_id, review_report_id=report_id)

    data = response.json()
    assert response.status_code == 200
    assert data["status"] == "NEEDS_REVIEW"
    assert data["review_report_id"] == report_id
    assert any("high risk" in item.lower() for item in data["warnings"])
    assert any(item["item"] == "ReviewReport is not marked high risk" and item["passed"] is False for item in data["publish_checklist"])


def test_review_report_mismatch_returns_400(monkeypatch):
    account_id, experiment_id, _, draft_id, _ = _create_final_draft(monkeypatch)
    other_account_id, other_experiment_id, _, other_draft_id, _ = _create_final_draft(monkeypatch)
    report_id = _create_review_report(other_draft_id, other_account_id, other_experiment_id)
    assert other_draft_id != draft_id
    assert other_account_id != account_id

    response = _create_package(draft_id, account_id, review_report_id=report_id)

    assert response.status_code == 400
    assert response.json()["detail"] == "review_report draft_id does not match"
    assert experiment_id


def test_get_and_list_publish_packages(monkeypatch):
    account_id, experiment_id, _, draft_id, _ = _create_final_draft(monkeypatch)
    report_id = _create_review_report(draft_id, account_id, experiment_id)
    created = _create_package(draft_id, account_id, review_report_id=report_id).json()

    listed = _client().get(f"/agent/drafts/{draft_id}/publish-packages")
    fetched = _client().get(f"/agent/publish-packages/{created['package_id']}")

    assert listed.status_code == 200
    assert listed.json()[0]["package_id"] == created["package_id"]
    assert fetched.status_code == 200
    assert fetched.json()["package_id"] == created["package_id"]


def test_b12_does_not_call_forbidden_workflows_or_publish(monkeypatch):
    account_id, experiment_id, source_draft_id, draft_id, _ = _create_final_draft(monkeypatch)
    report_id = _create_review_report(draft_id, account_id, experiment_id)
    before_counts = _counts()
    before_source = _draft_snapshot(source_draft_id)
    before_final = _draft_snapshot(draft_id)

    def forbidden_call(*args, **kwargs):
        raise AssertionError("B12 must not call upstream, publishing, comment, or memory workflows")

    monkeypatch.setattr("app.llm.client.LLMClient.__init__", forbidden_call, raising=False)
    monkeypatch.setattr("app.services.competitor_report_sev.CompetitorReportService.create_report", forbidden_call)
    monkeypatch.setattr("app.services.evidence_refresh_run_sev.EvidenceRefreshRunService.create_run", forbidden_call)
    monkeypatch.setattr("app.services.operation_run_sev.OperationRunService.create_run", forbidden_call)
    monkeypatch.setattr("app.services.operation_experiment_sev.OperationExperimentService.create_from_recommendation", forbidden_call)
    monkeypatch.setattr("app.services.content_draft_v2_sev.ContentDraftV2Service.generate_draft", forbidden_call)
    monkeypatch.setattr("app.services.content_draft_v2_sev.ContentDraftV2Service.regenerate_draft", forbidden_call)
    monkeypatch.setattr("app.services.post_publish_sev.PostPublishService.publish", forbidden_call, raising=False)

    response = _create_package(draft_id, account_id, review_report_id=report_id)

    data = response.json()
    assert response.status_code == 200
    assert data["status"] == "READY"
    assert _draft_snapshot(source_draft_id) == before_source
    assert _draft_snapshot(draft_id) == before_final
    after_counts = _counts()
    assert after_counts["publish_packages"] == before_counts["publish_packages"] + 1
    assert after_counts["drafts"] == before_counts["drafts"]
    assert after_counts["experiments"] == before_counts["experiments"]
    assert after_counts["opportunities"] == before_counts["opportunities"]
    assert after_counts["published_notes"] == before_counts["published_notes"]
    assert after_counts["strategy_memory"] == before_counts["strategy_memory"]
    assert after_counts["competitor_comments"] == before_counts["competitor_comments"]
    assert after_counts["note_comment_snapshots"] == before_counts["note_comment_snapshots"]
