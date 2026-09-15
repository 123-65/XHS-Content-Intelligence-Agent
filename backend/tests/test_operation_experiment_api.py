from fastapi.testclient import TestClient

from app.core.database import SessionLocal
from app.main import app
from app.models.account_operation_run import AccountOperationRun
from app.models.competitors_analysis import CompetitorAnalysisReport
from app.models.content_experiment import ContentExperiment
from app.models.content_opportunity import ContentOpportunity
from app.schemas.account import AccountProfileCreate
from app.services.account_sev import AccountProfileService


def _client() -> TestClient:
    return TestClient(app)


def _create_account() -> int:
    db = SessionLocal()
    try:
        account = AccountProfileService(db).create_account(
            AccountProfileCreate(
                account_name="B6 operation experiment account",
                platform="xhs",
                content_domain="operation experiment",
                positioning="B6 bridge test account",
                target_audience="operators",
                primary_goal="lead",
            )
        )
        return account.id
    finally:
        db.close()


def _create_report(account_id: int) -> int:
    db = SessionLocal()
    try:
        report = CompetitorAnalysisReport(
            account_id=account_id,
            name="B6 existing report",
            keyword="AI Agent",
            target_metric="engagement",
            note_count=5,
            comment_count=5,
            replicability_summary={"data_quality": "READY"},
            summary="Existing report",
            status="SUCCESS",
        )
        db.add(report)
        db.commit()
        db.refresh(report)
        return report.id
    finally:
        db.close()


def _create_opportunity(report_id: int) -> int:
    db = SessionLocal()
    try:
        opportunity = ContentOpportunity(
            report_id=report_id,
            opportunity_title="B6 recommendation topic",
            suggested_angle="Use existing evidence angle",
            target_audience="operators",
            content_pillar="case",
            comment_demand_type="ROUTE",
            evidence_summary="Existing opportunity evidence",
            replicability_score=88,
            risk_level="LOW",
            risk_points=[],
            opportunity_score=88,
        )
        db.add(opportunity)
        db.commit()
        db.refresh(opportunity)
        return opportunity.id
    finally:
        db.close()


def _create_operation_run(
    account_id: int,
    report_id: int | None,
    opportunity_id: int | None,
    status: str = "SUCCESS",
    rank: int = 1,
) -> int:
    db = SessionLocal()
    try:
        recommendation = {
            "rank": rank,
            "title": "B6 recommendation topic",
            "reason": "opportunity_score=88 / risk_level=LOW",
            "evidence": "Existing opportunity evidence",
            "report_id": report_id,
            "confidence": "HIGH",
            "risk_level": "LOW",
            "suggested_next_action": "CREATE_EXPERIMENT",
        }
        if opportunity_id is not None:
            recommendation["opportunity_id"] = opportunity_id
        run = AccountOperationRun(
            account_id=account_id,
            report_id=report_id,
            trigger_type="MANUAL",
            status=status,
            summary="Existing operation recommendation",
            recommendations=[recommendation] if status not in {"DATA_INSUFFICIENT", "FAILED"} else [],
            data_gaps=[] if status not in {"DATA_INSUFFICIENT", "FAILED"} else [{"type": "NO_CONTENT_OPPORTUNITY"}],
            next_actions=[{"action": "CREATE_EXPERIMENT", "enabled": True}],
            stats={"data_quality": "READY"},
        )
        db.add(run)
        db.commit()
        db.refresh(run)
        return run.id
    finally:
        db.close()


def _experiment_count() -> int:
    db = SessionLocal()
    try:
        return db.query(ContentExperiment).count()
    finally:
        db.close()


def _counts() -> dict[str, int]:
    db = SessionLocal()
    try:
        return {
            "report": db.query(CompetitorAnalysisReport).count(),
            "opportunity": db.query(ContentOpportunity).count(),
            "experiment": db.query(ContentExperiment).count(),
            "operation": db.query(AccountOperationRun).count(),
        }
    finally:
        db.close()


def _ready_fixture() -> tuple[int, int, int, int]:
    account_id = _create_account()
    report_id = _create_report(account_id)
    opportunity_id = _create_opportunity(report_id)
    run_id = _create_operation_run(account_id, report_id, opportunity_id)
    return account_id, report_id, opportunity_id, run_id


def test_preview_does_not_write_database():
    account_id, _, opportunity_id, run_id = _ready_fixture()
    before = _experiment_count()

    response = _client().post(
        f"/agent/operation-runs/{run_id}/recommendations/1/experiment-preview",
        json={"account_id": account_id, "target_metric": "collect"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "WAITING_CONFIRMATION"
    assert data["opportunity_id"] == opportunity_id
    assert data["confirmation"]["requires_confirmation"] is True
    assert _experiment_count() == before


def test_confirmed_false_does_not_write_database():
    account_id, _, _, run_id = _ready_fixture()
    before = _experiment_count()

    response = _client().post(
        f"/agent/operation-runs/{run_id}/recommendations/1/experiments",
        json={"account_id": account_id, "confirmed": False},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "WAITING_CONFIRMATION"
    assert response.json()["experiment_id"] is None
    assert _experiment_count() == before


def test_confirmed_true_creates_content_experiment():
    account_id, report_id, opportunity_id, run_id = _ready_fixture()

    response = _client().post(
        f"/agent/operation-runs/{run_id}/recommendations/1/experiments",
        json={
            "account_id": account_id,
            "confirmed": True,
            "experiment_name": "Confirmed B6 experiment",
            "target_metric": "collect",
            "notes": "user confirmed",
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "CREATED"
    assert data["experiment_id"]
    db = SessionLocal()
    try:
        experiment = db.get(ContentExperiment, data["experiment_id"])
        assert experiment is not None
        assert experiment.account_id == account_id
        assert experiment.analysis_report_id == report_id
        assert experiment.content_opportunity_id == opportunity_id
        assert experiment.experiment_name == "Confirmed B6 experiment"
        assert experiment.source_type == "OPERATION_RUN_RECOMMENDATION"
        assert experiment.status == "DRAFT"
    finally:
        db.close()


def test_operation_run_not_found_returns_404():
    account_id = _create_account()
    response = _client().post(
        "/agent/operation-runs/999999999/recommendations/1/experiment-preview",
        json={"account_id": account_id},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "operation run not found"


def test_account_id_mismatch_returns_400():
    account_id, _, _, run_id = _ready_fixture()
    other_account_id = _create_account()

    response = _client().post(
        f"/agent/operation-runs/{run_id}/recommendations/1/experiments",
        json={"account_id": other_account_id, "confirmed": True},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "operation run account_id does not match"
    assert account_id != other_account_id


def test_data_insufficient_operation_run_cannot_create():
    account_id = _create_account()
    run_id = _create_operation_run(account_id, report_id=None, opportunity_id=None, status="DATA_INSUFFICIENT")

    response = _client().post(
        f"/agent/operation-runs/{run_id}/recommendations/1/experiments",
        json={"account_id": account_id, "confirmed": True},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "operation run is not ready for experiment creation"


def test_missing_recommendation_rank_cannot_create():
    account_id, _, _, run_id = _ready_fixture()

    response = _client().post(
        f"/agent/operation-runs/{run_id}/recommendations/9/experiments",
        json={"account_id": account_id, "confirmed": True},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "recommendation rank not found"


def test_recommendation_without_opportunity_id_cannot_create():
    account_id = _create_account()
    report_id = _create_report(account_id)
    run_id = _create_operation_run(account_id, report_id, opportunity_id=None)

    response = _client().post(
        f"/agent/operation-runs/{run_id}/recommendations/1/experiments",
        json={"account_id": account_id, "confirmed": True},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "recommendation has no opportunity_id"


def test_missing_opportunity_id_cannot_create():
    account_id = _create_account()
    report_id = _create_report(account_id)
    run_id = _create_operation_run(account_id, report_id, opportunity_id=999999999)

    response = _client().post(
        f"/agent/operation-runs/{run_id}/recommendations/1/experiments",
        json={"account_id": account_id, "confirmed": True},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "content opportunity not found"


def test_b6_does_not_call_llm_external_links_or_create_report_opportunity(monkeypatch):
    account_id, _, _, run_id = _ready_fixture()
    before = _counts()

    def fail_llm(*args, **kwargs):
        raise AssertionError("LLM should not be called by B6")

    def fail_crawler(*args, **kwargs):
        raise AssertionError("Crawler should not be called by B6")

    def fail_report_create(*args, **kwargs):
        raise AssertionError("CompetitorReportService.create_report should not be called by B6")

    def fail_evidence_create(*args, **kwargs):
        raise AssertionError("EvidenceRefreshRunService.create_run should not be called by B6")

    def fail_operation_create(*args, **kwargs):
        raise AssertionError("OperationRunService.create_run should not be called by B6")

    monkeypatch.setattr("app.llm.client.LLMClient.__init__", fail_llm, raising=False)
    monkeypatch.setattr("app.services.crawler_collection_sev.CrawlerCollectionService.run_task", fail_crawler)
    monkeypatch.setattr("app.services.competitor_report_sev.CompetitorReportService.create_report", fail_report_create)
    monkeypatch.setattr("app.services.evidence_refresh_run_sev.EvidenceRefreshRunService.create_run", fail_evidence_create)
    monkeypatch.setattr("app.services.operation_run_sev.OperationRunService.create_run", fail_operation_create)

    response = _client().post(
        f"/agent/operation-runs/{run_id}/recommendations/1/experiments",
        json={"account_id": account_id, "confirmed": True},
    )

    after = _counts()
    assert response.status_code == 200
    assert response.json()["status"] == "CREATED"
    assert after["report"] == before["report"]
    assert after["opportunity"] == before["opportunity"]
    assert after["operation"] == before["operation"]
    assert after["experiment"] == before["experiment"] + 1
