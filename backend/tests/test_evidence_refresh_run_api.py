from fastapi.testclient import TestClient

from app.core.database import SessionLocal
from app.main import app
from app.models.account_evidence_refresh_run import AccountEvidenceRefreshRun
from app.models.competitor_account import CompetitorAccount
from app.models.competitor_comment import CompetitorComment
from app.models.competitor_note import CompetitorNote
from app.models.competitors_analysis import CompetitorAnalysisReport
from app.models.content_opportunity import ContentOpportunity
from app.models.viral_note_breakdown import ViralNoteBreakdown
from app.schemas.account import AccountProfileCreate
from app.services.account_sev import AccountProfileService


def _client() -> TestClient:
    """创建测试客户端。"""
    return TestClient(app)


def _create_account() -> int:
    """创建测试账号。"""
    db = SessionLocal()
    try:
        account = AccountProfileService(db).create_account(
            AccountProfileCreate(
                account_name="B4 evidence refresh account",
                platform="xhs",
                content_domain="AI Agent",
                positioning="Evidence refresh test account",
                target_audience="operators",
                primary_goal="lead",
            )
        )
        return account.id
    finally:
        db.close()


def _counts(account_id: int) -> dict[str, int]:
    """统计账号下证据产物数量。"""
    db = SessionLocal()
    try:
        return {
            "report": db.query(CompetitorAnalysisReport).filter(CompetitorAnalysisReport.account_id == account_id).count(),
            "breakdown": db.query(ViralNoteBreakdown).join(CompetitorAnalysisReport).filter(CompetitorAnalysisReport.account_id == account_id).count(),
            "opportunity": db.query(ContentOpportunity).join(CompetitorAnalysisReport).filter(CompetitorAnalysisReport.account_id == account_id).count(),
        }
    finally:
        db.close()


def _create_competitor_data(account_id: int, note_count: int = 3, comment_count: int = 3, is_mock: bool = False) -> None:
    """写入测试竞品数据，不访问外部链接。"""
    db = SessionLocal()
    try:
        account = CompetitorAccount(
            account_id=account_id,
            platform_account_id=f"b4-account-{account_id}",
            nickname="B4 peer account",
            homepage_url="https://www.xiaohongshu.com/user/profile/b4-peer",
            bio="AI Agent project sharing",
            source_type="SEED_SAMPLE" if is_mock else "MANUAL",
            provider_name="seed_sample" if is_mock else "manual_snapshot",
            is_mock=is_mock,
            confidence=0.9,
            raw_snapshot={"source": "b4_test_fixture"},
        )
        db.add(account)
        db.flush()
        notes = []
        for index in range(note_count):
            note = CompetitorNote(
                account_id=account_id,
                competitor_account_id=account.id,
                note_id=f"b4-note-{account_id}-{index}",
                note_url=f"https://www.xiaohongshu.com/explore/b4-note-{index}",
                author_name="B4 peer",
                title=f"AI Agent project route {index}",
                content="AI Agent project, resume, route and source code explanation",
                tags=["AI Agent", "project", "route"],
                like_count=100 + index,
                collect_count=80 + index,
                comment_count=comment_count,
                source_type="SEED_SAMPLE" if is_mock else "MANUAL",
                provider_name="seed_sample" if is_mock else "manual_snapshot",
                is_mock=is_mock,
                confidence=0.9,
                raw_snapshot={"source": "b4_test_fixture"},
            )
            db.add(note)
            notes.append(note)
        db.flush()
        for index in range(comment_count):
            db.add(
                CompetitorComment(
                    account_id=account_id,
                    competitor_note_id=notes[index % len(notes)].id if notes else None,
                    comment_id=f"b4-comment-{account_id}-{index}",
                    user_name=f"user-{index}",
                    content="Want route, project source code and resume expression",
                    like_count=10 + index,
                    source_type="SEED_SAMPLE" if is_mock else "MANUAL",
                    provider_name="seed_sample" if is_mock else "manual_snapshot",
                    is_mock=is_mock,
                    confidence=0.9,
                    raw_snapshot={"source": "b4_test_fixture"},
                )
            )
        db.commit()
    finally:
        db.close()


def _create_data_refresh_run(account_id: int) -> dict:
    """创建 B3 数据刷新运行记录。"""
    return _client().post("/agent/data-refresh/runs", json={"account_id": account_id}).json()


def test_no_competitor_notes_returns_data_insufficient_without_empty_report():
    """没有竞品笔记时返回 DATA_INSUFFICIENT，不生成空报告。"""
    account_id = _create_account()
    before = _counts(account_id)
    response = _client().post("/agent/evidence-refresh/runs", json={"account_id": account_id})

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "DATA_INSUFFICIENT"
    assert data["error_code"] == "NO_COMPETITOR_NOTES"
    assert data["report_id"] is None
    assert data["stats"]["data_quality"] == "EMPTY"
    assert _counts(account_id) == before


def test_only_mock_notes_returns_data_insufficient():
    """只有 Mock 竞品笔记时不生成真实证据分析。"""
    account_id = _create_account()
    _create_competitor_data(account_id, is_mock=True)
    response = _client().post("/agent/evidence-refresh/runs", json={"account_id": account_id, "keyword": "AI Agent"})

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "DATA_INSUFFICIENT"
    assert data["error_code"] == "ONLY_MOCK_COMPETITOR_NOTES"
    assert data["report_id"] is None


def test_real_competitor_data_creates_report_breakdowns_and_opportunities():
    """有真实竞品数据时复用 CompetitorReportService 生成证据结构。"""
    account_id = _create_account()
    _create_competitor_data(account_id)
    response = _client().post(
        "/agent/evidence-refresh/runs",
        json={"account_id": account_id, "keyword": "AI Agent", "target_metric": "engagement", "limit": 20},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "SUCCESS"
    assert data["report_id"]
    assert data["note_count"] == 3
    assert data["comment_count"] == 3
    assert data["breakdown_count"] >= 1
    assert data["opportunity_count"] >= 1
    assert data["data_quality"] == "READY"
    counts = _counts(account_id)
    assert counts["report"] >= 1
    assert counts["breakdown"] >= 1
    assert counts["opportunity"] >= 1


def test_insufficient_sample_returns_partial():
    """真实样本不足时生成低置信 PARTIAL 运行记录。"""
    account_id = _create_account()
    _create_competitor_data(account_id, note_count=2, comment_count=2)
    response = _client().post("/agent/evidence-refresh/runs", json={"account_id": account_id, "keyword": "AI Agent"})

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "PARTIAL"
    assert data["stats"]["data_quality"] == "PARTIAL"
    assert data["report_id"]


def test_data_refresh_run_id_must_exist_and_match_account():
    """data_refresh_run_id 不存在或账号不匹配时返回 400。"""
    account_id = _create_account()
    other_account_id = _create_account()
    other_refresh = _create_data_refresh_run(other_account_id)

    missing = _client().post(
        "/agent/evidence-refresh/runs",
        json={"account_id": account_id, "data_refresh_run_id": 999999999},
    )
    mismatch = _client().post(
        "/agent/evidence-refresh/runs",
        json={"account_id": account_id, "data_refresh_run_id": other_refresh["id"]},
    )

    assert missing.status_code == 400
    assert missing.json()["detail"] == "data refresh run not found"
    assert mismatch.status_code == 400
    assert mismatch.json()["detail"] == "data refresh run account_id does not match"


def test_data_refresh_run_status_is_recorded_when_present():
    """传入 B3 运行记录时，stats 标记 data_refresh_run_status。"""
    account_id = _create_account()
    _create_competitor_data(account_id)
    data_refresh = _create_data_refresh_run(account_id)

    response = _client().post(
        "/agent/evidence-refresh/runs",
        json={"account_id": account_id, "data_refresh_run_id": data_refresh["id"], "keyword": "AI Agent"},
    )

    assert response.status_code == 200
    assert response.json()["stats"]["data_refresh_run_status"] == data_refresh["status"]


def test_list_and_get_evidence_refresh_runs():
    """可以按账号查询列表，也可以查询单条详情。"""
    account_id = _create_account()
    _create_competitor_data(account_id)
    created = _client().post("/agent/evidence-refresh/runs", json={"account_id": account_id, "keyword": "AI Agent"}).json()

    listed = _client().get(f"/agent/evidence-refresh/runs?account_id={account_id}").json()
    detail = _client().get(f"/agent/evidence-refresh/runs/{created['id']}").json()

    assert listed[0]["id"] == created["id"]
    assert detail["id"] == created["id"]
    assert detail["report_id"] == created["report_id"]


def test_evidence_refresh_does_not_call_llm_or_external_links(monkeypatch):
    """证据刷新不调用 LLM，也不访问外部链接。"""
    account_id = _create_account()
    _create_competitor_data(account_id)

    def fail_llm(*args, **kwargs):
        raise AssertionError("LLM should not be called by B4")

    def fail_crawler(*args, **kwargs):
        raise AssertionError("Crawler should not be called by B4")

    monkeypatch.setattr("app.llm.client.LLMClient.__init__", fail_llm, raising=False)
    monkeypatch.setattr("app.services.crawler_collection_sev.CrawlerCollectionService.run_task", fail_crawler)

    response = _client().post("/agent/evidence-refresh/runs", json={"account_id": account_id, "keyword": "AI Agent"})

    assert response.status_code == 200
    assert response.json()["status"] == "SUCCESS"


def test_failed_or_insufficient_run_records_are_persisted():
    """DATA_INSUFFICIENT 时也会持久化 EvidenceRefreshRun。"""
    account_id = _create_account()
    response = _client().post("/agent/evidence-refresh/runs", json={"account_id": account_id})

    db = SessionLocal()
    try:
        run = db.get(AccountEvidenceRefreshRun, response.json()["id"])
        assert run is not None
        assert run.status == "DATA_INSUFFICIENT"
    finally:
        db.close()
