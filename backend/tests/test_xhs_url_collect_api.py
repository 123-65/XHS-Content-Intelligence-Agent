from datetime import datetime

from fastapi.testclient import TestClient

from app.collectors.xhs.base import XhsCollectedNote, XhsCollectProviderResult, XhsTopComment
from app.core.database import SessionLocal
from app.main import app
from app.models.competitor_account import CompetitorAccount
from app.models.competitor_comment import CompetitorComment
from app.models.competitor_note import CompetitorNote
from app.models.strategy_memory import StrategyMemory
from app.models.xhs_note import XhsNoteSnapshot
from tests.test_draft_context_preview_api import _create_account


def _client() -> TestClient:
    return TestClient(app)


class FakeXhsProvider:
    provider_name = "fake_xhs_provider"

    def collect(self, url: str, collect_comments: bool = True, max_comments: int = 20) -> XhsCollectProviderResult:
        if "login" in url:
            return XhsCollectProviderResult(
                status="LOGIN_REQUIRED",
                provider_name=self.provider_name,
                source_url=url,
                error_code="LOGIN_REQUIRED",
                error_message="login required",
            )
        if "captcha" in url:
            return XhsCollectProviderResult(
                status="CAPTCHA_REQUIRED",
                provider_name=self.provider_name,
                source_url=url,
                error_code="CAPTCHA_REQUIRED",
                error_message="captcha required",
            )
        if "parse" in url:
            return XhsCollectProviderResult(
                status="PARSE_FAILED",
                provider_name=self.provider_name,
                source_url=url,
                error_code="PARSE_FAILED",
                error_message="parse failed",
            )
        status = "PARTIAL_SUCCESS" if "partial" in url else "SUCCESS"
        note_id = url.rstrip("/").split("/")[-1]
        index = int("".join(ch for ch in note_id if ch.isdigit()) or "1")
        comments = [
            XhsTopComment(
                comment_id=f"c-{note_id}-{comment_index}",
                author_name=f"commenter-{comment_index}",
                content=f"AI Agent route question {comment_index}",
                like_count=comment_index,
                raw_snapshot={"from": "fake", "index": comment_index},
            )
            for comment_index in range(5)
        ]
        return XhsCollectProviderResult(
            status=status,
            provider_name=self.provider_name,
            source_url=url,
            parsed_result=XhsCollectedNote(
                source_url=url,
                note_id=note_id,
                author_name=f"Author {index}",
                author_profile_url=f"https://www.xiaohongshu.com/user/profile/author-{index}",
                title=f"AI Agent real collected note {index}",
                content=f"AI Agent project route and evidence note {index}",
                content_summary=f"AI Agent project route {index}",
                publish_time=datetime(2026, 9, 16, 12, 0, 0),
                like_count=100 + index,
                collect_count=50 + index,
                comment_count=5,
                share_count=3,
                cover_url=f"https://img.example.com/{note_id}-cover.jpg",
                image_urls=[
                    f"https://img.example.com/{note_id}-1.jpg",
                    f"https://img.example.com/{note_id}-2.jpg",
                ],
                tags=["AI Agent", "project"],
                top_comments=comments,
                raw_snapshot={"provider_payload": {"note_id": note_id}},
            ),
            warnings=["MISSING_CONTENT"] if status == "PARTIAL_SUCCESS" else [],
            raw_text="real html fixture",
        )


def _patch_provider(monkeypatch):
    monkeypatch.setattr("app.services.xhs_url_collect_sev.SimpleHttpXhsProvider", FakeXhsProvider)


def _collect(account_id: int, urls: list[str], confirmed: bool = True, **extra):
    payload = {
        "account_id": account_id,
        "confirmed": confirmed,
        "urls": urls,
        "collect_comments": True,
        "max_comments": 20,
    }
    payload.update(extra)
    return _client().post("/agent/xhs/url-collect", json=payload)


def _valid_url(slug: str = "note-1") -> str:
    return f"https://www.xiaohongshu.com/explore/{slug}"


def _counts(account_id: int) -> dict[str, int]:
    with SessionLocal() as db:
        return {
            "accounts": db.query(CompetitorAccount).filter(CompetitorAccount.account_id == account_id).count(),
            "notes": db.query(CompetitorNote).filter(CompetitorNote.account_id == account_id).count(),
            "snapshots": db.query(XhsNoteSnapshot).filter(XhsNoteSnapshot.account_id == account_id).count(),
            "comments": db.query(CompetitorComment).filter(CompetitorComment.account_id == account_id).count(),
            "strategy_memory": db.query(StrategyMemory).filter(StrategyMemory.account_id == account_id).count(),
        }


def test_confirmed_false_does_not_collect_or_write(monkeypatch):
    _patch_provider(monkeypatch)
    account_id = _create_account()
    before = _counts(account_id)

    response = _collect(account_id, [_valid_url()], confirmed=False)

    data = response.json()
    assert response.status_code == 200
    assert data["status"] == "WAITING_CONFIRMATION"
    assert data["run_id"] is None
    assert _counts(account_id) == before


def test_empty_urls_returns_failed_without_write(monkeypatch):
    _patch_provider(monkeypatch)
    account_id = _create_account()
    before = _counts(account_id)

    response = _collect(account_id, [])

    data = response.json()
    assert response.status_code == 200
    assert data["status"] == "FAILED"
    assert data["error_code"] == "EMPTY_URLS"
    assert _counts(account_id) == before


def test_non_xhs_url_returns_unsupported_without_note(monkeypatch):
    _patch_provider(monkeypatch)
    account_id = _create_account()
    before = _counts(account_id)

    response = _collect(account_id, ["https://example.com/not-xhs"])

    data = response.json()
    assert response.status_code == 200
    assert data["status"] == "FAILED"
    assert data["results"][0]["status"] == "UNSUPPORTED_URL"
    after = _counts(account_id)
    assert after["notes"] == before["notes"]
    assert after["snapshots"] == before["snapshots"]
    assert after["comments"] == before["comments"]


def test_success_writes_account_snapshot_note_comment_metrics_images_and_raw(monkeypatch):
    _patch_provider(monkeypatch)
    account_id = _create_account()

    response = _collect(account_id, [_valid_url("note-101")], max_comments=2)

    data = response.json()
    assert response.status_code == 200
    assert data["status"] == "COMPLETED"
    assert data["success_count"] == 1
    assert data["results"][0]["comment_count_saved"] == 2
    with SessionLocal() as db:
        account = db.query(CompetitorAccount).filter(CompetitorAccount.account_id == account_id).order_by(CompetitorAccount.id.desc()).first()
        note = db.query(CompetitorNote).filter(CompetitorNote.account_id == account_id).order_by(CompetitorNote.id.desc()).first()
        snapshot = db.query(XhsNoteSnapshot).filter(XhsNoteSnapshot.account_id == account_id).order_by(XhsNoteSnapshot.id.desc()).first()
        comments = db.query(CompetitorComment).filter(CompetitorComment.account_id == account_id, CompetitorComment.competitor_note_id == note.id).all()
        assert account.source_type == "URL_COLLECT"
        assert account.is_mock is False
        assert account.raw_snapshot["source_type"] == "URL_COLLECT"
        assert note.source_type == "URL_COLLECT"
        assert note.is_mock is False
        assert note.like_count == 201
        assert note.collect_count == 151
        assert note.comment_count == 5
        assert note.raw_snapshot["image_urls"]
        assert note.raw_snapshot["raw_snapshot"]["provider_payload"]["note_id"] == "note-101"
        assert snapshot.source_type == "URL_COLLECT"
        assert snapshot.like_count == 201
        assert snapshot.collect_count == 151
        assert snapshot.comment_count == 5
        assert snapshot.image_urls == ["https://img.example.com/note-101-1.jpg", "https://img.example.com/note-101-2.jpg"]
        assert len(comments) == 2
        assert all(comment.source_type == "URL_COLLECT" for comment in comments)
        assert all(comment.is_mock is False for comment in comments)


def test_duplicate_url_updates_existing_note_and_snapshot(monkeypatch):
    _patch_provider(monkeypatch)
    account_id = _create_account()
    url = _valid_url("note-102")
    first = _collect(account_id, [url], max_comments=1).json()
    before = _counts(account_id)

    second = _collect(account_id, [url], max_comments=3).json()

    after = _counts(account_id)
    assert second["status"] == "COMPLETED"
    assert after["accounts"] == before["accounts"]
    assert after["notes"] == before["notes"]
    assert after["snapshots"] == before["snapshots"]
    assert after["comments"] == before["comments"] + 2
    assert first["results"][0]["note_id"] == second["results"][0]["note_id"]


def test_provider_failures_do_not_write_fake_notes(monkeypatch):
    _patch_provider(monkeypatch)
    account_id = _create_account()
    before = _counts(account_id)

    response = _collect(account_id, [_valid_url("login"), _valid_url("captcha"), _valid_url("parse")])

    data = response.json()
    assert response.status_code == 200
    assert data["status"] == "FAILED"
    assert {item["status"] for item in data["results"]} == {"LOGIN_REQUIRED", "CAPTCHA_REQUIRED", "PARSE_FAILED"}
    after = _counts(account_id)
    assert after["notes"] == before["notes"]
    assert after["snapshots"] == before["snapshots"]
    assert after["comments"] == before["comments"]


def test_partial_success_saves_known_fields_and_returns_warnings(monkeypatch):
    _patch_provider(monkeypatch)
    account_id = _create_account()

    response = _collect(account_id, [_valid_url("partial-201")])

    data = response.json()
    assert response.status_code == 200
    assert data["status"] == "COMPLETED"
    assert data["results"][0]["status"] == "PARTIAL_SUCCESS"
    assert data["results"][0]["warnings"] == ["MISSING_CONTENT"]
    assert _counts(account_id)["notes"] == 1


def test_collect_comments_false_does_not_save_comments(monkeypatch):
    _patch_provider(monkeypatch)
    account_id = _create_account()

    response = _collect(account_id, [_valid_url("note-301")], collect_comments=False)

    data = response.json()
    assert response.status_code == 200
    assert data["results"][0]["comment_count_saved"] == 0
    assert _counts(account_id)["comments"] == 0


def test_max_comments_limits_saved_comments(monkeypatch):
    _patch_provider(monkeypatch)
    account_id = _create_account()

    response = _collect(account_id, [_valid_url("note-302")], max_comments=1)

    assert response.status_code == 200
    assert response.json()["results"][0]["comment_count_saved"] == 1
    assert _counts(account_id)["comments"] == 1


def test_does_not_call_llm_or_write_strategy_memory(monkeypatch):
    _patch_provider(monkeypatch)
    account_id = _create_account()
    before = _counts(account_id)

    def forbidden_call(*args, **kwargs):
        raise AssertionError("R1 must not call LLM or StrategyMemory workflows")

    monkeypatch.setattr("app.llm.client.LLMClient.__init__", forbidden_call, raising=False)
    monkeypatch.setattr("app.services.strategy_memory_confirmation_sev.StrategyMemoryConfirmationService.confirm", forbidden_call)

    response = _collect(account_id, [_valid_url("note-401")])

    assert response.status_code == 200
    after = _counts(account_id)
    assert after["strategy_memory"] == before["strategy_memory"]
    assert after["notes"] == before["notes"] + 1


def test_r1_data_can_enter_b4_evidence_refresh(monkeypatch):
    _patch_provider(monkeypatch)
    account_id = _create_account()
    urls = [_valid_url("note-501"), _valid_url("note-502"), _valid_url("note-503")]
    collect = _collect(account_id, urls, max_comments=3)
    assert collect.status_code == 200
    assert collect.json()["success_count"] == 3

    response = _client().post(
        "/agent/evidence-refresh/runs",
        json={"account_id": account_id, "keyword": None, "target_metric": "engagement", "limit": 10},
    )

    data = response.json()
    assert response.status_code == 200
    assert data["status"] in {"SUCCESS", "PARTIAL"}
    assert data["error_code"] is None
    assert data["note_count"] >= 3
    assert data["comment_count"] >= 3
    assert data["data_quality"] in {"READY", "PARTIAL"}


def test_get_and_list_runs(monkeypatch):
    _patch_provider(monkeypatch)
    account_id = _create_account()
    created = _collect(account_id, [_valid_url("note-601")]).json()

    listed = _client().get(f"/agent/xhs/url-collect/runs?account_id={account_id}")
    fetched = _client().get(f"/agent/xhs/url-collect/runs/{created['run_id']}")

    assert listed.status_code == 200
    assert listed.json()[0]["run_id"] == created["run_id"]
    assert fetched.status_code == 200
    assert fetched.json()["run_id"] == created["run_id"]
