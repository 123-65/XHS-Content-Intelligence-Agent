from datetime import datetime

from fastapi.testclient import TestClient

from app.agent.product_entry.chat_service import build_agent_chat_workflow_execute_service
from app.agent.product_entry.llm_router import LLMUserInputRouter
from app.agent.product_entry.schemas import Action, AgentChatRequest, Intent
from app.agent.product_entry.task_planner import LLMTaskPlanner
from app.collectors.ocr.base import OcrResult
from app.collectors.xhs.base import XhsCollectedAccount, XhsCollectedComment, XhsCollectedNote
from app.core.database import SessionLocal
from app.main import app
from app.models.competitor_account import CompetitorAccount
from app.models.competitor_comment import CompetitorComment
from app.models.competitor_note import CompetitorNote
from app.models.strategy_memory import StrategyMemory
from app.models.xhs_note import XhsNoteSnapshot
from app.services.xhs_collect_import_sev import XhsCollectImportService
from app.services.xhs_collector_sev import XhsCollectorService
from tests.test_draft_context_preview_api import _create_account
from tests.competitor_analysis_fakes import FakeStructuredCompetitorAnalyzer


class FailingLLM:
    def generate_text(self, *args, **kwargs):
        raise AssertionError("deterministic workflow should not call LLM")


class FakeOcrProvider:
    provider_name = "fake_ocr"

    def extract_image_text(self, image_url: str) -> OcrResult:
        if "ocr-fail" in image_url:
            return OcrResult(status="OCR_FAILED", image_url=image_url, error_code="OCR_FAILED")
        return OcrResult(status="SUCCESS", image_url=image_url, text=f"OCR {image_url}", lines=[f"OCR {image_url}"])


class FakeXhsProvider:
    provider_name = "fake_xhs_mcp"
    source_type = "XHS_MCP"

    def collect_note(self, note_url: str, collect_comments: bool = True, max_comments: int = 20):
        from app.collectors.xhs.base import XhsCollectionResult

        if "login" in note_url:
            return XhsCollectionResult(status="LOGIN_REQUIRED", provider_name=self.provider_name, source_url=note_url, error_code="LOGIN_REQUIRED")
        slug = note_url.rstrip("/").split("/")[-1]
        comments = [
            XhsCollectedComment(comment_id=f"c-{slug}-{index}", note_id=slug, content=f"路线资料怎么拿 {index}", author_name=f"u{index}", like_count=index)
            for index in range(3)
        ]
        return XhsCollectionResult(
            status="SUCCESS",
            provider_name=self.provider_name,
            source_url=note_url,
            parsed_note=XhsCollectedNote(
                note_url=note_url,
                note_id=slug,
                title=f"AI Agent 竞品笔记 {slug}",
                content="项目实战路线和资料清单",
                author_id="author-1",
                author_name="同行作者",
                author_profile_url="https://www.xiaohongshu.com/user/profile/author-1",
                publish_time=datetime(2026, 9, 16, 12, 0, 0),
                like_count=100,
                collect_count=60,
                comment_count=3,
                share_count=5,
                image_urls=[f"https://img.example.com/{slug}.jpg"],
                tags=["AI Agent", "项目"],
                comments=comments[:max_comments] if collect_comments else [],
                raw_payload={"slug": slug},
            ),
        )

    def collect_account(self, account_id_or_url: str, recent_note_limit: int = 10):
        from app.collectors.xhs.base import XhsCollectionResult

        if "login" in account_id_or_url:
            return XhsCollectionResult(status="LOGIN_REQUIRED", provider_name=self.provider_name, source_url=account_id_or_url, error_code="LOGIN_REQUIRED")
        note = XhsCollectedNote(
            note_url=f"https://www.xiaohongshu.com/explore/recent-{account_id_or_url}",
            note_id=f"recent-{account_id_or_url}",
            title="同行近期项目笔记",
            content="项目复盘和求职路线",
            author_id=account_id_or_url,
            author_name=f"同行 {account_id_or_url}",
            author_profile_url=f"https://www.xiaohongshu.com/user/profile/{account_id_or_url}",
            like_count=88,
            collect_count=40,
            comment_count=0,
            tags=["项目"],
            raw_payload={"recent": True},
        )
        return XhsCollectionResult(
            status="SUCCESS",
            provider_name=self.provider_name,
            source_url=account_id_or_url,
            parsed_account=XhsCollectedAccount(
                external_user_id=account_id_or_url,
                profile_url=f"https://www.xiaohongshu.com/user/profile/{account_id_or_url}",
                nickname=f"同行 {account_id_or_url}",
                bio="专注 AI Agent 项目实战",
                follower_count=1000,
                following_count=10,
                liked_count=5000,
                recent_notes=[note],
                raw_payload={"account": account_id_or_url},
            ),
        )


def _client() -> TestClient:
    return TestClient(app)


def _valid_url(slug: str) -> str:
    return f"https://www.xiaohongshu.com/explore/{slug}"


def test_router_and_planner_select_collection_plus_analysis_tools():
    account_id = _create_account()
    request = AgentChatRequest(
        account_id=account_id,
        text="分析这些小红书笔记和同行账号，看看人设和评论区需求",
        attachments={"note_urls": [_valid_url("wf-1")], "competitor_account_ids": ["author-1"]},
    )
    router = LLMUserInputRouter(FailingLLM())
    planner = LLMTaskPlanner(FailingLLM())

    result = router.route(request)
    plan = planner.plan(request, result)

    assert result.intent == Intent.ANALYZE_COMPETITOR
    assert result.can_execute is True
    assert [step.action for step in plan.steps] == [
        Action.COLLECT_XHS_NOTES,
        Action.COLLECT_XHS_ACCOUNTS,
        Action.ANALYZE_COMPETITOR_DATA,
    ]


def test_import_service_upserts_note_account_comments_and_ocr_payload():
    account_id = _create_account()
    service = XhsCollectorService(SessionLocal(), provider=FakeXhsProvider(), ocr_provider=FakeOcrProvider())
    try:
        first = service.collect_notes(account_id, [_valid_url("upsert-1")], max_comments=2)
        second = service.collect_notes(account_id, [_valid_url("upsert-1")], max_comments=3)
    finally:
        service.db.close()

    assert first["status"] == "SUCCESS"
    assert second["status"] == "SUCCESS"
    with SessionLocal() as db:
        assert db.query(CompetitorNote).filter(CompetitorNote.account_id == account_id, CompetitorNote.note_url == _valid_url("upsert-1")).count() == 1
        assert db.query(XhsNoteSnapshot).filter(XhsNoteSnapshot.account_id == account_id, XhsNoteSnapshot.note_url == _valid_url("upsert-1")).count() == 1
        snapshot = db.query(XhsNoteSnapshot).filter(XhsNoteSnapshot.account_id == account_id, XhsNoteSnapshot.note_url == _valid_url("upsert-1")).first()
        assert snapshot.image_urls
        assert snapshot.image_ocr_items[0]["ocr_status"] == "SUCCESS"
        assert db.query(CompetitorComment).filter(CompetitorComment.account_id == account_id).count() == 3
        assert db.query(StrategyMemory).filter(StrategyMemory.account_id == account_id).count() == 0


def test_provider_failure_and_login_required_do_not_write_fake_records():
    account_id = _create_account()
    with SessionLocal() as db:
        service = XhsCollectorService(db, provider=FakeXhsProvider(), ocr_provider=FakeOcrProvider())
        before_notes = db.query(CompetitorNote).filter(CompetitorNote.account_id == account_id).count()
        result = service.collect_notes(account_id, [_valid_url("login")])
        after_notes = db.query(CompetitorNote).filter(CompetitorNote.account_id == account_id).count()

    assert result["status"] == "FAILED"
    assert result["errors"][0]["error_code"] == "LOGIN_REQUIRED"
    assert after_notes == before_notes


def test_ocr_failure_does_not_block_note_import():
    account_id = _create_account()
    note = XhsCollectedNote(
        note_url=_valid_url("ocr-fail"),
        note_id="ocr-fail",
        title="OCR failure note",
        content="main data is real",
        author_name="ocr author",
        image_urls=["https://img.example.com/ocr-fail.jpg"],
    )
    provider = FakeXhsProvider()

    class OneNoteProvider(FakeXhsProvider):
        def collect_note(self, note_url: str, collect_comments: bool = True, max_comments: int = 20):
            from app.collectors.xhs.base import XhsCollectionResult

            return XhsCollectionResult(status="SUCCESS", provider_name=provider.provider_name, source_url=note_url, parsed_note=note)

    with SessionLocal() as db:
        result = XhsCollectorService(db, provider=OneNoteProvider(), ocr_provider=FakeOcrProvider()).collect_notes(account_id, [_valid_url("ocr-fail")])
        snapshot = db.query(XhsNoteSnapshot).filter(XhsNoteSnapshot.account_id == account_id, XhsNoteSnapshot.note_url == _valid_url("ocr-fail")).first()

    assert result["status"] == "SUCCESS"
    assert "OCR_OCR_FAILED" in result["items"][0]["warnings"]
    assert snapshot is not None
    assert snapshot.image_ocr_items[0]["ocr_status"] == "OCR_FAILED"


def test_agent_workflow_executes_collection_and_analysis_without_manual_steps(monkeypatch):
    account_id = _create_account()

    def fake_service(context):
        return XhsCollectorService(context["db"], provider=FakeXhsProvider(), ocr_provider=FakeOcrProvider())

    monkeypatch.setattr("app.agent.product_entry.business_handlers._xhs_collector_service", fake_service)
    monkeypatch.setattr(
        "app.services.competitor_report_sev.LLMStructuredCompetitorAnalyzer",
        FakeStructuredCompetitorAnalyzer,
    )
    request = {
        "account_id": account_id,
        "text": "分析这些小红书笔记和同行账号，看看他们的人设、内容方向、用户在评论区关心什么",
        "attachments": {
            "note_urls": [_valid_url("wf-101"), _valid_url("wf-102"), _valid_url("wf-103")],
            "competitor_account_ids": ["author-1"],
        },
    }

    response = _client().post("/agent/chat/execute-workflow", json=request)
    data = response.json()

    assert response.status_code == 200
    assert data["status"] == "SUCCESS"
    actions = [item["action"] for item in data["metadata"]["workflow_timeline"]]
    assert actions == ["COLLECT_XHS_NOTES", "COLLECT_XHS_ACCOUNTS", "ANALYZE_COMPETITOR_DATA"]
    assert data["metadata"]["business_result"]["competitor_analysis"]["report_id"]
    assert data["metadata"]["workflow_timeline"][0]["data_count"]["notes_saved"] == 3
    analysis_timeline = data["metadata"]["workflow_timeline"][2]
    assert analysis_timeline["analysis_engine"] == "LLM_STRUCTURED_V1"
    assert analysis_timeline["evidence_note_count"] == 4
    assert analysis_timeline["evidence_comment_count"] == 9
    assert isinstance(analysis_timeline["data_gaps"], list)
    assert analysis_timeline["grounding_status"] == "PASSED"


def test_agent_workflow_marks_failed_step_visible(monkeypatch):
    account_id = _create_account()

    class LoginProvider(FakeXhsProvider):
        def collect_note(self, note_url: str, collect_comments: bool = True, max_comments: int = 20):
            from app.collectors.xhs.base import XhsCollectionResult

            return XhsCollectionResult(status="LOGIN_REQUIRED", provider_name=self.provider_name, source_url=note_url, error_code="LOGIN_REQUIRED")

    def fake_service(context):
        return XhsCollectorService(context["db"], provider=LoginProvider(), ocr_provider=FakeOcrProvider())

    monkeypatch.setattr("app.agent.product_entry.business_handlers._xhs_collector_service", fake_service)
    response = _client().post(
        "/agent/chat/execute-workflow",
        json={
            "account_id": account_id,
            "text": "分析这些小红书笔记和同行账号",
            "attachments": {"note_urls": [_valid_url("login")], "competitor_account_ids": ["author-1"]},
        },
    )
    data = response.json()

    assert response.status_code == 200
    assert data["status"] == "FAILED"
    assert data["metadata"]["workflow_timeline"][0]["status"] == "FAILED"
    assert data["metadata"]["workflow_timeline"][0]["error_code"] == "LOGIN_REQUIRED"
