from datetime import datetime

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
from tests.test_manual_publish_backfill_api import _backfill, _create_ready_package
from tests.test_draft_context_preview_api import _create_account


def _client() -> TestClient:
    return TestClient(app)


def _review(published_note_id: int, account_id: int, confirmed: bool = True, **extra):
    payload = {
        "account_id": account_id,
        "confirmed": confirmed,
        "review_window": "MANUAL_SNAPSHOT",
        "notes": "Manual observation only.",
    }
    payload.update(extra)
    return _client().post(f"/agent/published-notes/{published_note_id}/post-publish-reviews", json=payload)


def _create_backfilled_note(monkeypatch, **backfill_extra) -> tuple[int, int, int, int, int]:
    account_id, experiment_id, draft_id, package_id = _create_ready_package(monkeypatch)
    response = _backfill(package_id, account_id, **backfill_extra)
    assert response.status_code == 200
    data = response.json()
    return account_id, experiment_id, draft_id, package_id, data["published_note_id"]


def _set_target(experiment_id: int, target_metric: str = "collect", target_values: dict | None = None) -> None:
    with SessionLocal() as db:
        experiment = db.get(ContentExperiment, experiment_id)
        assert experiment is not None
        experiment.target_metric = target_metric
        experiment.primary_metric = target_metric
        experiment.target_values = target_values if target_values is not None else {"collect_count": 5}
        db.commit()


def _create_note_without_metrics(monkeypatch) -> tuple[int, int]:
    account_id, experiment_id, draft_id, package_id = _create_ready_package(monkeypatch)
    with SessionLocal() as db:
        note = PublishedNote(
            account_id=account_id,
            experiment_id=experiment_id,
            draft_id=draft_id,
            publish_url=f"https://www.xiaohongshu.com/explore/no-metrics-{package_id}",
            platform="xhs",
            status="PUBLISHED",
            source_type="MANUAL_BACKFILL",
            published_at=datetime(2026, 9, 16, 20, 0, 0),
            raw_snapshot={"publish_package_id": package_id, "source": "test_no_metrics"},
        )
        db.add(note)
        db.commit()
        db.refresh(note)
        return account_id, note.id


def _counts() -> dict[str, int]:
    with SessionLocal() as db:
        return {
            "drafts": db.query(ContentDraft).count(),
            "experiments": db.query(ContentExperiment).count(),
            "opportunities": db.query(ContentOpportunity).count(),
            "publish_packages": db.query(PublishPackage).count(),
            "published_notes": db.query(PublishedNote).count(),
            "public_metrics": db.query(PublicMetricSnapshot).count(),
            "private_conversions": db.query(PrivateConversionSnapshot).count(),
            "review_reports": db.query(ReviewReport).count(),
            "strategy_memory": db.query(StrategyMemory).count(),
            "competitor_comments": db.query(CompetitorComment).count(),
            "note_comment_snapshots": db.query(NoteCommentSnapshot).count(),
        }


def _draft_snapshot(draft_id: int) -> dict:
    with SessionLocal() as db:
        draft = db.get(ContentDraft, draft_id)
        assert draft is not None
        return {
            "status": draft.status,
            "version": draft.version,
            "title": draft.title,
            "body": draft.body,
            "updated_at": draft.updated_at,
        }


def _experiment_snapshot(experiment_id: int) -> dict:
    with SessionLocal() as db:
        experiment = db.get(ContentExperiment, experiment_id)
        assert experiment is not None
        return {
            "status": experiment.status,
            "target_metric": experiment.target_metric,
            "target_values": experiment.target_values,
            "publish_url": experiment.publish_url,
            "published_at": experiment.published_at,
        }


def test_confirmed_false_does_not_create_review(monkeypatch):
    account_id, _, _, _, note_id = _create_backfilled_note(monkeypatch)
    before = _counts()

    response = _review(note_id, account_id, confirmed=False)

    data = response.json()
    assert response.status_code == 200
    assert data["status"] == "WAITING_CONFIRMATION"
    assert data["review_id"] is None
    assert _counts() == before


def test_published_note_not_found_returns_404_without_side_effects():
    account_id = _create_account()
    before = _counts()

    response = _review(999999999, account_id)

    assert response.status_code == 404
    assert response.json()["detail"] == "published note not found"
    assert _counts() == before


def test_account_mismatch_returns_400_without_review(monkeypatch):
    _, _, _, _, note_id = _create_backfilled_note(monkeypatch)
    other_account_id = _create_account()
    before = _counts()

    response = _review(note_id, other_account_id)

    assert response.status_code == 400
    assert response.json()["detail"] == "published_note account_id does not match"
    assert _counts() == before


def test_no_metric_snapshot_returns_data_insufficient_without_review(monkeypatch):
    account_id, note_id = _create_note_without_metrics(monkeypatch)
    before = _counts()

    response = _review(note_id, account_id)

    data = response.json()
    assert response.status_code == 200
    assert data["status"] == "DATA_INSUFFICIENT"
    assert data["error_code"] == "NO_METRIC_SNAPSHOT"
    assert any(item["type"] == "NO_PUBLIC_METRIC_SNAPSHOT" for item in data["data_gaps"])
    assert _counts() == before


def test_mock_metric_snapshot_returns_data_insufficient_without_review(monkeypatch):
    account_id, note_id = _create_note_without_metrics(monkeypatch)
    with SessionLocal() as db:
        db.add(
            PublicMetricSnapshot(
                published_note_id=note_id,
                snapshot_window="manual",
                view_count=100,
                like_count=10,
                collect_count=5,
                comment_count=1,
                share_count=1,
                follow_count=0,
                profile_visit_count=0,
                source_type="MOCK",
                collected_at=datetime(2026, 9, 16, 21, 0, 0),
                raw_snapshot={"source": "mock_test"},
            )
        )
        db.commit()
    before = _counts()

    response = _review(note_id, account_id)

    data = response.json()
    assert response.status_code == 200
    assert data["status"] == "DATA_INSUFFICIENT"
    assert data["error_code"] == "MOCK_METRIC_SOURCE"
    assert any(item["type"] == "MOCK_METRIC_SOURCE" for item in data["data_gaps"])
    assert _counts() == before


def test_review_hit_target_calculates_metrics_and_candidates(monkeypatch):
    account_id, experiment_id, draft_id, package_id, note_id = _create_backfilled_note(
        monkeypatch,
        like_count=10,
        collect_count=5,
        comment_count=2,
        share_count=3,
        follower_gain=4,
        lead_count=2,
    )
    _set_target(experiment_id, "collect", {"collect_count": 5})
    before = _counts()
    before_draft = _draft_snapshot(draft_id)
    before_experiment = _experiment_snapshot(experiment_id)

    response = _review(note_id, account_id)

    data = response.json()
    assert response.status_code == 200
    assert data["status"] == "REVIEWED"
    assert data["review_id"]
    assert data["package_id"] == package_id
    assert data["metric_summary"]["engagement_count"] == 20
    assert data["metric_summary"]["collect_like_ratio"] == 0.5
    assert data["metric_summary"]["comment_like_ratio"] == 0.2
    assert data["target_comparison"]["target_metric"] == "collect"
    assert data["target_comparison"]["target_value"] == 5
    assert data["target_comparison"]["actual_value"] == 5
    assert data["target_comparison"]["result"] == "HIT_TARGET"
    assert data["conversion_summary"]["lead_count"] == 2
    assert data["conversion_summary"]["follower_gain"] == 4
    assert data["conversion_summary"]["lead_rate"] == 0.1
    assert data["insights"]
    assert any(item["action"] == "CREATE_STRATEGY_MEMORY_CANDIDATE" for item in data["next_actions"])
    assert data["strategy_memory_candidates"]
    after = _counts()
    assert after["review_reports"] == before["review_reports"] + 1
    assert after["strategy_memory"] == before["strategy_memory"]
    assert _draft_snapshot(draft_id) == before_draft
    assert _experiment_snapshot(experiment_id) == before_experiment


def test_missing_target_values_returns_unknown_target(monkeypatch):
    account_id, experiment_id, _, _, note_id = _create_backfilled_note(monkeypatch)
    _set_target(experiment_id, "collect", {})

    response = _review(note_id, account_id)

    data = response.json()
    assert response.status_code == 200
    assert data["status"] == "REVIEWED"
    assert data["target_comparison"]["result"] == "UNKNOWN_TARGET"
    assert any(item["type"] == "UNKNOWN_TARGET" for item in data["data_gaps"])


def test_zero_metrics_are_not_judged_as_failure(monkeypatch):
    account_id, experiment_id, _, _, note_id = _create_backfilled_note(
        monkeypatch,
        like_count=0,
        collect_count=0,
        comment_count=0,
        share_count=0,
        follower_gain=0,
        lead_count=0,
    )
    _set_target(experiment_id, "collect", {"collect_count": 5})

    response = _review(note_id, account_id)

    data = response.json()
    assert response.status_code == 200
    assert data["status"] == "REVIEWED"
    assert data["metric_summary"]["engagement_count"] == 0
    assert data["target_comparison"]["result"] == "UNKNOWN_TARGET"
    assert any(item["type"] == "ZERO_METRICS" for item in data["data_gaps"])
    assert "MISS_TARGET" not in [item.get("type") for item in data["data_gaps"]]


def test_get_and_list_post_publish_reviews(monkeypatch):
    account_id, experiment_id, _, _, note_id = _create_backfilled_note(monkeypatch, collect_count=8, like_count=10)
    _set_target(experiment_id, "collect", {"collect_count": 5})
    created = _review(note_id, account_id).json()

    listed = _client().get(f"/agent/published-notes/{note_id}/post-publish-reviews")
    fetched = _client().get(f"/agent/post-publish-reviews/{created['review_id']}")

    assert listed.status_code == 200
    assert listed.json()[0]["review_id"] == created["review_id"]
    assert fetched.status_code == 200
    assert fetched.json()["review_id"] == created["review_id"]
    assert fetched.json()["strategy_memory_candidates"]


def test_b14_does_not_call_forbidden_workflows(monkeypatch):
    account_id, experiment_id, draft_id, _, note_id = _create_backfilled_note(monkeypatch, collect_count=8, like_count=10)
    _set_target(experiment_id, "collect", {"collect_count": 5})
    before = _counts()
    before_draft = _draft_snapshot(draft_id)
    before_experiment = _experiment_snapshot(experiment_id)

    def forbidden_call(*args, **kwargs):
        raise AssertionError("B14 must not call external, LLM, publish, comment, or memory workflows")

    monkeypatch.setattr("app.llm.client.LLMClient.__init__", forbidden_call, raising=False)
    monkeypatch.setattr("app.services.competitor_report_sev.CompetitorReportService.create_report", forbidden_call)
    monkeypatch.setattr("app.services.evidence_refresh_run_sev.EvidenceRefreshRunService.create_run", forbidden_call)
    monkeypatch.setattr("app.services.operation_run_sev.OperationRunService.create_run", forbidden_call)
    monkeypatch.setattr("app.services.operation_experiment_sev.OperationExperimentService.create_from_recommendation", forbidden_call)
    monkeypatch.setattr("app.services.content_draft_v2_sev.ContentDraftV2Service.generate_draft", forbidden_call)
    monkeypatch.setattr("app.services.content_draft_v2_sev.ContentDraftV2Service.regenerate_draft", forbidden_call)
    monkeypatch.setattr("app.services.post_publish_sev.PostPublishService.extract_memories", forbidden_call, raising=False)
    monkeypatch.setattr("app.repositories.post_publish_repo.PostPublishRepository.create_strategy_memory", forbidden_call, raising=False)
    monkeypatch.setattr("app.repositories.post_publish_repo.PostPublishRepository.create_experiment", forbidden_call, raising=False)

    response = _review(note_id, account_id)

    data = response.json()
    assert response.status_code == 200
    assert data["status"] == "REVIEWED"
    after = _counts()
    assert after["review_reports"] == before["review_reports"] + 1
    assert after["strategy_memory"] == before["strategy_memory"]
    assert after["drafts"] == before["drafts"]
    assert after["experiments"] == before["experiments"]
    assert after["opportunities"] == before["opportunities"]
    assert after["publish_packages"] == before["publish_packages"]
    assert after["published_notes"] == before["published_notes"]
    assert after["public_metrics"] == before["public_metrics"]
    assert after["private_conversions"] == before["private_conversions"]
    assert after["competitor_comments"] == before["competitor_comments"]
    assert after["note_comment_snapshots"] == before["note_comment_snapshots"]
    assert _draft_snapshot(draft_id) == before_draft
    assert _experiment_snapshot(experiment_id) == before_experiment
