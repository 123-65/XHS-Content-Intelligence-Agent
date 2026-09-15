from fastapi.testclient import TestClient

from app.core.database import SessionLocal
from app.main import app
from app.models.account_data_source_config import AccountDataSourceConfig
from app.models.account_evidence_refresh_run import AccountEvidenceRefreshRun
from app.models.account_operation_run import AccountOperationRun
from app.models.competitor_account import CompetitorAccount
from app.models.competitor_note import CompetitorNote
from app.models.competitors_analysis import CompetitorAnalysisReport
from app.models.content_opportunity import ContentOpportunity
from app.models.viral_note_breakdown import ViralNoteBreakdown
from app.schemas.account import AccountProfileCreate
from app.services.account_sev import AccountProfileService


def _client() -> TestClient:
    return TestClient(app)


def _create_account() -> int:
    db = SessionLocal()
    try:
        account = AccountProfileService(db).create_account(
            AccountProfileCreate(
                account_name="B5 operation run account",
                platform="xhs",
                content_domain="operation run",
                positioning="B5 operation test account",
                target_audience="operators",
                primary_goal="lead",
            )
        )
        return account.id
    finally:
        db.close()


def _create_data_source_config(account_id: int) -> int:
    db = SessionLocal()
    try:
        config = AccountDataSourceConfig(
            account_id=account_id,
            platform="xhs",
            status="ACTIVE",
            keywords=[{"keyword": "AI Agent", "enabled": True}],
            competitor_accounts=[{"name": "peer one", "enabled": True}],
            note_urls=[],
            refresh_policy={"manual_only": True},
            metadata_payload={"source": "b5_test"},
        )
        db.add(config)
        db.commit()
        db.refresh(config)
        return config.id
    finally:
        db.close()


def _create_report(account_id: int, data_quality: str = "READY", note_count: int = 5, comment_count: int = 5) -> int:
    db = SessionLocal()
    try:
        report = CompetitorAnalysisReport(
            account_id=account_id,
            name="B5 existing evidence report",
            keyword="AI Agent",
            target_metric="engagement",
            note_count=note_count,
            comment_count=comment_count,
            replicability_summary={"data_quality": data_quality, "reason": "test fixture"},
            summary="Existing evidence summary",
            status="SUCCESS",
        )
        db.add(report)
        db.commit()
        db.refresh(report)
        return report.id
    finally:
        db.close()


def _create_evidence_run(account_id: int, report_id: int | None, status: str = "SUCCESS", error_code: str | None = None) -> int:
    db = SessionLocal()
    try:
        run = AccountEvidenceRefreshRun(
            account_id=account_id,
            report_id=report_id,
            trigger_type="MANUAL",
            status=status,
            keyword="AI Agent",
            target_metric="engagement",
            limit=20,
            stats={"data_quality": "READY" if status == "SUCCESS" else "PARTIAL"},
            error_code=error_code,
            error_message="Evidence unavailable" if error_code else None,
        )
        db.add(run)
        db.commit()
        db.refresh(run)
        return run.id
    finally:
        db.close()


def _create_opportunity(report_id: int, title: str, score: int, risk: str = "LOW") -> int:
    db = SessionLocal()
    try:
        opportunity = ContentOpportunity(
            report_id=report_id,
            opportunity_title=title,
            suggested_angle=f"{title} angle",
            target_audience="operators",
            content_pillar="case",
            comment_demand_type="ROUTE",
            evidence_summary=f"{title} evidence",
            replicability_score=score,
            risk_level=risk,
            risk_points=[],
            opportunity_score=score,
        )
        db.add(opportunity)
        db.commit()
        db.refresh(opportunity)
        return opportunity.id
    finally:
        db.close()


def _create_breakdown(account_id: int, report_id: int) -> int:
    db = SessionLocal()
    try:
        account = CompetitorAccount(
            account_id=account_id,
            platform_account_id=f"b5-peer-{account_id}",
            nickname="B5 peer",
            source_type="MANUAL",
            provider_name="manual_snapshot",
            is_mock=False,
            confidence=0.9,
            raw_snapshot={"source": "b5_test"},
        )
        db.add(account)
        db.flush()
        note = CompetitorNote(
            account_id=account_id,
            competitor_account_id=account.id,
            note_id=f"b5-note-{account_id}-{report_id}",
            note_url=f"https://www.xiaohongshu.com/explore/b5-note-{report_id}",
            author_name="B5 peer",
            title="B5 note",
            content="Existing competitor evidence",
            tags=["AI Agent"],
            like_count=100,
            collect_count=50,
            comment_count=10,
            source_type="MANUAL",
            provider_name="manual_snapshot",
            is_mock=False,
            confidence=0.9,
            raw_snapshot={"source": "b5_test"},
        )
        db.add(note)
        db.flush()
        breakdown = ViralNoteBreakdown(
            report_id=report_id,
            competitor_note_id=note.id,
            note_title=note.title,
            note_url=note.note_url,
            engagement_score=160,
            title_pattern="existing",
            cover_pattern="existing",
            content_structure="existing",
            comment_demands=[],
            conversion_signals=[],
            replicability_score=80,
            risk_points=[],
            evidence_summary="Existing viral breakdown",
        )
        db.add(breakdown)
        db.commit()
        db.refresh(breakdown)
        return breakdown.id
    finally:
        db.close()


def _counts() -> dict[str, int]:
    db = SessionLocal()
    try:
        return {
            "report": db.query(CompetitorAnalysisReport).count(),
            "opportunity": db.query(ContentOpportunity).count(),
            "operation": db.query(AccountOperationRun).count(),
        }
    finally:
        db.close()


def test_no_evidence_refresh_run_returns_data_insufficient():
    account_id = _create_account()
    response = _client().post("/agent/operation-runs", json={"account_id": account_id})

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "DATA_INSUFFICIENT"
    assert data["error_code"] == "NO_EVIDENCE_REFRESH_RUN"
    assert data["recommendations"] == []
    assert data["data_gaps"][0]["suggested_action"] == "RUN_EVIDENCE_REFRESH"


def test_data_insufficient_evidence_run_propagates_to_operation_run():
    account_id = _create_account()
    evidence_id = _create_evidence_run(account_id, report_id=None, status="DATA_INSUFFICIENT", error_code="NO_COMPETITOR_NOTES")

    response = _client().post("/agent/operation-runs", json={"account_id": account_id, "evidence_refresh_run_id": evidence_id})

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "DATA_INSUFFICIENT"
    assert data["error_code"] == "NO_COMPETITOR_NOTES"
    assert data["recommendations"] == []


def test_report_without_opportunities_returns_data_insufficient():
    account_id = _create_account()
    report_id = _create_report(account_id)
    evidence_id = _create_evidence_run(account_id, report_id=report_id)

    response = _client().post("/agent/operation-runs", json={"account_id": account_id, "evidence_refresh_run_id": evidence_id})

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "DATA_INSUFFICIENT"
    assert data["error_code"] == "NO_CONTENT_OPPORTUNITY"
    assert data["data_gaps"][0]["type"] == "NO_CONTENT_OPPORTUNITY"


def test_opportunities_generate_top_three_recommendations_sorted_by_score():
    account_id = _create_account()
    _create_data_source_config(account_id)
    report_id = _create_report(account_id)
    evidence_id = _create_evidence_run(account_id, report_id=report_id)
    _create_breakdown(account_id, report_id)
    _create_opportunity(report_id, "score 70", 70)
    _create_opportunity(report_id, "score 95", 95)
    _create_opportunity(report_id, "score 80", 80)
    _create_opportunity(report_id, "score 60", 60)

    response = _client().post("/agent/operation-runs", json={"account_id": account_id, "evidence_refresh_run_id": evidence_id})

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "SUCCESS"
    assert [item["title"] for item in data["recommendations"]] == ["score 95", "score 80", "score 70"]
    assert len(data["recommendations"]) == 3
    assert data["stats"]["has_data_source_config"] is True
    assert data["stats"]["opportunity_count"] == 4


def test_high_risk_same_score_does_not_rank_before_low_risk():
    account_id = _create_account()
    report_id = _create_report(account_id)
    evidence_id = _create_evidence_run(account_id, report_id=report_id)
    _create_opportunity(report_id, "high risk same score", 90, risk="HIGH")
    _create_opportunity(report_id, "low risk same score", 90, risk="LOW")

    response = _client().post("/agent/operation-runs", json={"account_id": account_id, "evidence_refresh_run_id": evidence_id})

    assert response.status_code == 200
    data = response.json()
    assert data["recommendations"][0]["title"] == "low risk same score"
    assert data["recommendations"][1]["title"] == "high risk same score"


def test_partial_evidence_generates_partial_operation_run():
    account_id = _create_account()
    report_id = _create_report(account_id, data_quality="PARTIAL", note_count=2, comment_count=2)
    evidence_id = _create_evidence_run(account_id, report_id=report_id, status="PARTIAL")
    _create_opportunity(report_id, "partial opportunity", 85)

    response = _client().post("/agent/operation-runs", json={"account_id": account_id, "evidence_refresh_run_id": evidence_id})

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "PARTIAL"
    assert data["recommendations"][0]["confidence"] == "LOW"
    assert any(gap["type"] == "LOW_EVIDENCE_QUALITY" for gap in data["data_gaps"])


def test_success_persists_operation_run():
    account_id = _create_account()
    report_id = _create_report(account_id)
    evidence_id = _create_evidence_run(account_id, report_id=report_id)
    _create_opportunity(report_id, "persisted opportunity", 88)

    response = _client().post("/agent/operation-runs", json={"account_id": account_id, "evidence_refresh_run_id": evidence_id})

    db = SessionLocal()
    try:
        run = db.get(AccountOperationRun, response.json()["id"])
        assert run is not None
        assert run.status == response.json()["status"]
        assert run.report_id == report_id
    finally:
        db.close()


def test_list_and_get_operation_runs():
    account_id = _create_account()
    report_id = _create_report(account_id)
    evidence_id = _create_evidence_run(account_id, report_id=report_id)
    _create_opportunity(report_id, "list detail opportunity", 81)
    created = _client().post("/agent/operation-runs", json={"account_id": account_id, "evidence_refresh_run_id": evidence_id}).json()

    listed = _client().get(f"/agent/operation-runs?account_id={account_id}").json()
    detail = _client().get(f"/agent/operation-runs/{created['id']}").json()

    assert listed[0]["id"] == created["id"]
    assert detail["id"] == created["id"]
    assert detail["report_id"] == report_id


def test_operation_run_does_not_call_llm_crawler_or_create_evidence(monkeypatch):
    account_id = _create_account()
    report_id = _create_report(account_id)
    evidence_id = _create_evidence_run(account_id, report_id=report_id)
    _create_opportunity(report_id, "readonly opportunity", 90)
    before = _counts()

    def fail_llm(*args, **kwargs):
        raise AssertionError("LLM should not be called by B5")

    def fail_crawler(*args, **kwargs):
        raise AssertionError("Crawler should not be called by B5")

    def fail_report_create(*args, **kwargs):
        raise AssertionError("CompetitorReportService.create_report should not be called by B5")

    monkeypatch.setattr("app.llm.client.LLMClient.__init__", fail_llm, raising=False)
    monkeypatch.setattr("app.services.crawler_collection_sev.CrawlerCollectionService.run_task", fail_crawler)
    monkeypatch.setattr("app.services.competitor_report_sev.CompetitorReportService.create_report", fail_report_create)

    response = _client().post("/agent/operation-runs", json={"account_id": account_id, "evidence_refresh_run_id": evidence_id})

    after = _counts()
    assert response.status_code == 200
    assert response.json()["status"] == "SUCCESS"
    assert after["report"] == before["report"]
    assert after["opportunity"] == before["opportunity"]
    assert after["operation"] == before["operation"] + 1


def test_b4_evidence_refresh_endpoint_still_available():
    account_id = _create_account()
    response = _client().post("/agent/evidence-refresh/runs", json={"account_id": account_id})

    assert response.status_code == 200
    assert response.json()["status"] == "DATA_INSUFFICIENT"
