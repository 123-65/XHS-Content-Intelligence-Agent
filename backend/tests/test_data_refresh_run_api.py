from fastapi.testclient import TestClient

from app.core.database import SessionLocal
from app.main import app
from app.models.competitor_comment import CompetitorComment
from app.models.competitor_note import CompetitorNote
from app.models.competitors_analysis import CompetitorAnalysisReport
from app.models.content_opportunity import ContentOpportunity
from app.models.crawl_task import CrawlTask
from app.schemas.account import AccountProfileCreate
from app.services.account_sev import AccountProfileService


def _client() -> TestClient:
    """创建测试客户端。"""
    return TestClient(app)


def _create_account() -> int:
    """创建测试账号画像。"""
    db = SessionLocal()
    try:
        account = AccountProfileService(db).create_account(
            AccountProfileCreate(
                account_name="B3 manual refresh account",
                platform="xhs",
                content_domain="manual refresh",
                positioning="B3 refresh test account",
                target_audience="operators",
                primary_goal="lead",
            )
        )
        return account.id
    finally:
        db.close()


def _create_data_source_config(account_id: int, status: str = "ACTIVE") -> dict:
    """创建 B2 数据源配置。"""
    response = _client().post(
        "/agent/data-source-configs",
        json={
            "account_id": account_id,
            "platform": "xhs",
            "status": status,
            "keywords": [
                {"keyword": "AI Agent", "enabled": True},
                {"keyword": "小红书运营", "enabled": True},
                {"keyword": "disabled keyword", "enabled": False},
            ],
            "competitor_accounts": [
                {"name": "peer one", "enabled": True},
                {"profile_url": "https://www.xiaohongshu.com/user/profile/peer-two", "enabled": True},
                {"name": "disabled peer", "enabled": False},
            ],
            "note_urls": [
                "https://www.xiaohongshu.com/explore/seed-1",
                "https://www.xiaohongshu.com/explore/seed-2",
                "https://www.xiaohongshu.com/explore/seed-3",
            ],
            "refresh_policy": {"manual_only": True, "refresh_scope_days": 7},
            "metadata_payload": {"source": "b3_test_config"},
        },
    )
    assert response.status_code == 200
    return response.json()


def _counts() -> dict[str, int]:
    """统计刷新不应伪造的数据。"""
    db = SessionLocal()
    try:
        return {
            "crawl_task": db.query(CrawlTask).count(),
            "note": db.query(CompetitorNote).count(),
            "comment": db.query(CompetitorComment).count(),
            "report": db.query(CompetitorAnalysisReport).count(),
            "opportunity": db.query(ContentOpportunity).count(),
        }
    finally:
        db.close()


def test_missing_account_returns_404():
    """account_id 不存在时返回 404。"""
    response = _client().post("/agent/data-refresh/runs", json={"account_id": 999999999})

    assert response.status_code == 404
    assert response.json()["detail"] == "account not found"


def test_no_enabled_data_source_returns_failed_run():
    """账号存在但没有启用数据源时创建失败运行记录。"""
    account_id = _create_account()
    response = _client().post("/agent/data-refresh/runs", json={"account_id": account_id})

    assert response.status_code == 200
    data = response.json()
    assert data["account_id"] == account_id
    assert data["status"] == "FAILED"
    assert data["error_code"] == "NO_ENABLED_DATA_SOURCE"
    assert data["stats"]["config_count"] == 0


def test_disabled_data_source_returns_no_enabled_data_source():
    """显式传入停用的数据源配置时不执行刷新。"""
    account_id = _create_account()
    config = _create_data_source_config(account_id, status="DISABLED")
    response = _client().post(
        "/agent/data-refresh/runs",
        json={"account_id": account_id, "data_source_config_id": config["id"]},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "FAILED"
    assert data["error_code"] == "NO_ENABLED_DATA_SOURCE"


def test_enabled_data_source_creates_provider_not_configured_run_without_fake_data():
    """有启用配置时记录刷新请求，但 Provider 未配置时不伪造采集结果。"""
    account_id = _create_account()
    config = _create_data_source_config(account_id)
    before = _counts()

    response = _client().post("/agent/data-refresh/runs", json={"account_id": account_id})

    assert response.status_code == 200
    data = response.json()
    assert data["account_id"] == account_id
    assert data["data_source_config_id"] == config["id"]
    assert data["status"] == "PROVIDER_NOT_CONFIGURED"
    assert data["error_code"] == "PROVIDER_NOT_CONFIGURED"
    assert data["refresh_scope_days"] == 7
    assert data["stats"]["config_count"] == 1
    assert data["stats"]["keyword_count"] == 2
    assert data["stats"]["competitor_account_count"] == 2
    assert data["stats"]["seed_url_count"] == 3
    assert data["stats"]["crawl_task_count"] == 0
    assert data["stats"]["note_count"] == 0
    assert data["stats"]["comment_count"] == 0
    assert _counts() == before


def test_provider_not_configured_does_not_visit_external_links(monkeypatch):
    """只有 seed_urls 时不访问外部链接，也不创建 CrawlTask。"""
    account_id = _create_account()
    _create_data_source_config(account_id)

    def fail_if_called(*args, **kwargs):
        raise AssertionError("CrawlTask should not be created for plain seed_urls")

    monkeypatch.setattr("app.services.data_refresh_run_sev.CrawlerCollectionService.create_task", fail_if_called)
    response = _client().post("/agent/data-refresh/runs", json={"account_id": account_id})

    assert response.status_code == 200
    assert response.json()["status"] == "PROVIDER_NOT_CONFIGURED"


def test_list_and_get_refresh_runs():
    """可以查询刷新运行列表和详情。"""
    account_id = _create_account()
    _create_data_source_config(account_id)
    created = _client().post("/agent/data-refresh/runs", json={"account_id": account_id}).json()

    listed = _client().get(f"/agent/data-refresh/runs?account_id={account_id}").json()
    detail = _client().get(f"/agent/data-refresh/runs/{created['id']}").json()

    assert listed[0]["id"] == created["id"]
    assert detail["id"] == created["id"]
    assert detail["status"] == "PROVIDER_NOT_CONFIGURED"


def test_b2_data_source_config_still_works_after_b3():
    """B3 不破坏 B2 DataSourceConfig 查询能力。"""
    account_id = _create_account()
    config = _create_data_source_config(account_id)

    response = _client().get(f"/agent/data-source-configs/by-account/{account_id}?platform=xhs")

    assert response.status_code == 200
    assert response.json()["id"] == config["id"]
