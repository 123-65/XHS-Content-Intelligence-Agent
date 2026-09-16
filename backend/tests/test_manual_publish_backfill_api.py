from fastapi.testclient import TestClient

from app.core.database import SessionLocal
from app.main import app
from app.models.competitor_comment import CompetitorComment
from app.models.content_draft import ContentDraft
from app.models.content_experiment import ContentExperiment
from app.models.content_opportunity import ContentOpportunity
from app.models.note_comment_snapshot import NoteCommentSnapshot
from app.models.private_conversion_snapshot import PrivateConversionSnapshot
from app.models.public_metric_snapshot import PublicMetricSnapshot
from app.models.publish_package import PublishPackage
from app.models.published_note import PublishedNote
from app.models.review_report import ReviewReport
from app.models.strategy_memory import StrategyMemory
from tests.test_draft_context_preview_api import _create_account
from tests.test_publish_package_api import (
    _create_final_draft,
    _create_package,
    _create_review_report,
    _draft_snapshot,
)


def _client() -> TestClient:
    return TestClient(app)


def _create_ready_package(monkeypatch) -> tuple[int, int, int, int]:
    account_id, experiment_id, _, draft_id, _ = _create_final_draft(monkeypatch)
    report_id = _create_review_report(draft_id, account_id, experiment_id)
    response = _create_package(draft_id, account_id, review_report_id=report_id)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "READY"
    return account_id, experiment_id, draft_id, data["package_id"]


def _backfill(package_id: int, account_id: int, confirmed: bool = True, **extra):
    payload = {
        "account_id": account_id,
        "confirmed": confirmed,
        "platform": "xhs",
        "note_url": f"https://www.xiaohongshu.com/explore/manual-b13-{package_id}",
        "published_at": "2026-09-16T20:00:00",
        "title": "Manual published title",
        "like_count": 11,
        "collect_count": 7,
        "comment_count": 3,
        "share_count": 2,
        "follower_gain": 1,
        "lead_count": 4,
        "remark": "manual metrics from user",
    }
    payload.update(extra)
    return _client().post(f"/agent/publish-packages/{package_id}/manual-publish", json=payload)


def _counts() -> dict[str, int]:
    with SessionLocal() as db:
        return {
            "drafts": db.query(ContentDraft).count(),
            "experiments": db.query(ContentExperiment).count(),
            "opportunities": db.query(ContentOpportunity).count(),
            "review_reports": db.query(ReviewReport).count(),
            "publish_packages": db.query(PublishPackage).count(),
            "published_notes": db.query(PublishedNote).count(),
            "public_metrics": db.query(PublicMetricSnapshot).count(),
            "private_conversions": db.query(PrivateConversionSnapshot).count(),
            "strategy_memory": db.query(StrategyMemory).count(),
            "competitor_comments": db.query(CompetitorComment).count(),
            "note_comment_snapshots": db.query(NoteCommentSnapshot).count(),
        }


def _package_snapshot(package_id: int) -> dict:
    with SessionLocal() as db:
        package = db.get(PublishPackage, package_id)
        assert package is not None
        return {"status": package.status, "stats": package.stats}


def _experiment_snapshot(experiment_id: int) -> dict:
    with SessionLocal() as db:
        experiment = db.get(ContentExperiment, experiment_id)
        assert experiment is not None
        return {"status": experiment.status, "publish_url": experiment.publish_url, "published_at": experiment.published_at}


def _latest_public_metric(snapshot_id: int) -> dict:
    with SessionLocal() as db:
        snapshot = db.get(PublicMetricSnapshot, snapshot_id)
        assert snapshot is not None
        return {
            "published_note_id": snapshot.published_note_id,
            "like_count": snapshot.like_count,
            "collect_count": snapshot.collect_count,
            "comment_count": snapshot.comment_count,
            "share_count": snapshot.share_count,
            "follow_count": snapshot.follow_count,
            "source_type": snapshot.source_type,
            "raw_snapshot": snapshot.raw_snapshot,
        }


def _private_conversion(snapshot_id: int) -> dict:
    with SessionLocal() as db:
        snapshot = db.get(PrivateConversionSnapshot, snapshot_id)
        assert snapshot is not None
        return {
            "lead_count": snapshot.lead_count,
            "source_type": snapshot.source_type,
            "raw_snapshot": snapshot.raw_snapshot,
        }


def test_confirmed_false_does_not_create_note_or_metrics(monkeypatch):
    account_id, _, _, package_id = _create_ready_package(monkeypatch)
    before = _counts()

    def fail_llm(*args, **kwargs):
        raise AssertionError("B13 must not call LLM before confirmation")

    monkeypatch.setattr("app.llm.client.LLMClient.__init__", fail_llm, raising=False)

    response = _backfill(package_id, account_id, confirmed=False)

    data = response.json()
    assert response.status_code == 200
    assert data["status"] == "WAITING_CONFIRMATION"
    assert data["published_note_id"] is None
    assert data["metric_snapshot_id"] is None
    assert _counts() == before


def test_package_not_found_returns_404_without_side_effects(monkeypatch):
    account_id = _create_account()
    before = _counts()

    response = _backfill(999999999, account_id)

    assert response.status_code == 404
    assert response.json()["detail"] == "publish package not found"
    assert _counts() == before


def test_account_mismatch_returns_400_without_note(monkeypatch):
    _, _, _, package_id = _create_ready_package(monkeypatch)
    other_account_id = _create_account()
    before = _counts()

    response = _backfill(package_id, other_account_id)

    assert response.status_code == 400
    assert response.json()["detail"] == "publish_package account_id does not match"
    assert _counts() == before


def test_note_url_empty_returns_400(monkeypatch):
    account_id, _, _, package_id = _create_ready_package(monkeypatch)
    before = _counts()

    response = _backfill(package_id, account_id, note_url="  ")

    assert response.status_code == 400
    assert response.json()["detail"] == "note_url is required"
    assert _counts() == before


def test_note_url_must_be_xhs_link(monkeypatch):
    account_id, _, _, package_id = _create_ready_package(monkeypatch)
    before = _counts()

    response = _backfill(package_id, account_id, note_url="https://example.com/not-xhs")

    assert response.status_code == 400
    assert response.json()["detail"] == "note_url must be a XHS link"
    assert _counts() == before


def test_negative_metrics_return_validation_error(monkeypatch):
    account_id, _, _, package_id = _create_ready_package(monkeypatch)
    before = _counts()

    response = _backfill(package_id, account_id, like_count=-1)

    assert response.status_code == 422
    assert _counts() == before


def test_manual_backfill_creates_published_note_and_snapshots(monkeypatch):
    account_id, experiment_id, draft_id, package_id = _create_ready_package(monkeypatch)
    before_counts = _counts()
    before_draft = _draft_snapshot(draft_id)
    before_experiment = _experiment_snapshot(experiment_id)

    response = _backfill(package_id, account_id)

    data = response.json()
    assert response.status_code == 200
    assert data["status"] == "RECORDED"
    assert data["published_note_id"]
    assert data["metric_snapshot_id"]
    assert data["private_conversion_snapshot_id"]
    assert data["metrics"]["source_type"] == "MANUAL"
    assert data["metrics"]["like_count"] == 11
    assert data["metrics"]["lead_count"] == 4
    assert data["next_actions"][0]["action"] == "POST_PUBLISH_REVIEW"
    after_counts = _counts()
    assert after_counts["published_notes"] == before_counts["published_notes"] + 1
    assert after_counts["public_metrics"] == before_counts["public_metrics"] + 1
    assert after_counts["private_conversions"] == before_counts["private_conversions"] + 1
    assert after_counts["drafts"] == before_counts["drafts"]
    assert after_counts["experiments"] == before_counts["experiments"]
    assert _draft_snapshot(draft_id) == before_draft
    assert _experiment_snapshot(experiment_id) == before_experiment

    public_metric = _latest_public_metric(data["metric_snapshot_id"])
    assert public_metric["published_note_id"] == data["published_note_id"]
    assert public_metric["source_type"] == "MANUAL"
    assert public_metric["like_count"] == 11
    assert public_metric["collect_count"] == 7
    assert public_metric["comment_count"] == 3
    assert public_metric["share_count"] == 2
    assert public_metric["follow_count"] == 1
    assert public_metric["raw_snapshot"]["publish_package_id"] == package_id

    private_conversion = _private_conversion(data["private_conversion_snapshot_id"])
    assert private_conversion["source_type"] == "MANUAL"
    assert private_conversion["lead_count"] == 4
    assert private_conversion["raw_snapshot"]["publish_package_id"] == package_id

    package_snapshot = _package_snapshot(package_id)
    assert package_snapshot["status"] == "MANUALLY_PUBLISHED"
    assert package_snapshot["stats"]["manual_publish"]["published_note_id"] == data["published_note_id"]


def test_duplicate_backfill_reuses_published_note_but_adds_metric_snapshot(monkeypatch):
    account_id, _, _, package_id = _create_ready_package(monkeypatch)
    first = _backfill(package_id, account_id).json()
    before = _counts()

    second_response = _backfill(package_id, account_id, like_count=22, collect_count=9, lead_count=6)

    second = second_response.json()
    assert second_response.status_code == 200
    assert second["status"] == "RECORDED"
    assert second["published_note_id"] == first["published_note_id"]
    assert second["metric_snapshot_id"] != first["metric_snapshot_id"]
    assert second["private_conversion_snapshot_id"] != first["private_conversion_snapshot_id"]
    after = _counts()
    assert after["published_notes"] == before["published_notes"]
    assert after["public_metrics"] == before["public_metrics"] + 1
    assert after["private_conversions"] == before["private_conversions"] + 1
    public_metric = _latest_public_metric(second["metric_snapshot_id"])
    assert public_metric["like_count"] == 22
    assert public_metric["collect_count"] == 9
    private_conversion = _private_conversion(second["private_conversion_snapshot_id"])
    assert private_conversion["lead_count"] == 6


def test_get_and_list_published_notes(monkeypatch):
    account_id, _, _, package_id = _create_ready_package(monkeypatch)
    created = _backfill(package_id, account_id).json()

    listed = _client().get(f"/agent/published-notes?account_id={account_id}&limit=20")
    fetched = _client().get(f"/agent/published-notes/{created['published_note_id']}")

    assert listed.status_code == 200
    assert any(item["id"] == created["published_note_id"] for item in listed.json())
    assert fetched.status_code == 200
    assert fetched.json()["id"] == created["published_note_id"]
    assert fetched.json()["package_id"] == package_id


def test_b13_does_not_call_forbidden_workflows(monkeypatch):
    account_id, experiment_id, draft_id, package_id = _create_ready_package(monkeypatch)
    before_counts = _counts()
    before_draft = _draft_snapshot(draft_id)
    before_experiment = _experiment_snapshot(experiment_id)

    def forbidden_call(*args, **kwargs):
        raise AssertionError("B13 must not call external, LLM, publish, comment, review, or memory workflows")

    monkeypatch.setattr("app.llm.client.LLMClient.__init__", forbidden_call, raising=False)
    monkeypatch.setattr("app.services.competitor_report_sev.CompetitorReportService.create_report", forbidden_call)
    monkeypatch.setattr("app.services.evidence_refresh_run_sev.EvidenceRefreshRunService.create_run", forbidden_call)
    monkeypatch.setattr("app.services.operation_run_sev.OperationRunService.create_run", forbidden_call)
    monkeypatch.setattr("app.services.operation_experiment_sev.OperationExperimentService.create_from_recommendation", forbidden_call)
    monkeypatch.setattr("app.services.content_draft_v2_sev.ContentDraftV2Service.generate_draft", forbidden_call)
    monkeypatch.setattr("app.services.content_draft_v2_sev.ContentDraftV2Service.regenerate_draft", forbidden_call)
    monkeypatch.setattr("app.services.post_publish_sev.PostPublishService.create_review", forbidden_call, raising=False)
    monkeypatch.setattr("app.services.post_publish_sev.PostPublishService.extract_memories", forbidden_call, raising=False)
    monkeypatch.setattr("app.services.post_publish_sev.PostPublishService.generate_optimization", forbidden_call, raising=False)
    monkeypatch.setattr("app.repositories.post_publish_repo.PostPublishRepository.create_strategy_memory", forbidden_call, raising=False)

    response = _backfill(package_id, account_id)

    data = response.json()
    assert response.status_code == 200
    assert data["status"] == "RECORDED"
    assert _draft_snapshot(draft_id) == before_draft
    assert _experiment_snapshot(experiment_id) == before_experiment
    after_counts = _counts()
    assert after_counts["published_notes"] == before_counts["published_notes"] + 1
    assert after_counts["public_metrics"] == before_counts["public_metrics"] + 1
    assert after_counts["private_conversions"] == before_counts["private_conversions"] + 1
    assert after_counts["drafts"] == before_counts["drafts"]
    assert after_counts["experiments"] == before_counts["experiments"]
    assert after_counts["opportunities"] == before_counts["opportunities"]
    assert after_counts["publish_packages"] == before_counts["publish_packages"]
    assert after_counts["review_reports"] == before_counts["review_reports"]
    assert after_counts["strategy_memory"] == before_counts["strategy_memory"]
    assert after_counts["competitor_comments"] == before_counts["competitor_comments"]
    assert after_counts["note_comment_snapshots"] == before_counts["note_comment_snapshots"]
