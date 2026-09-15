from fastapi.testclient import TestClient

from app.core.database import SessionLocal
from app.main import app
from app.models.crawl_task import CrawlTask
from app.schemas.account import AccountProfileCreate
from app.services.account_sev import AccountProfileService


def _client() -> TestClient:
    return TestClient(app)


def _create_account() -> int:
    db = SessionLocal()
    try:
        account = AccountProfileService(db).create_account(
            AccountProfileCreate(
                account_name="B2 data source config account",
                platform="xhs",
                content_domain="AI career",
                positioning="Explain agent projects for beginners",
                target_audience="AI application engineers",
                primary_goal="lead",
            )
        )
        return account.id
    finally:
        db.close()


def _crawl_task_count() -> int:
    db = SessionLocal()
    try:
        return db.query(CrawlTask).count()
    finally:
        db.close()


def _payload(account_id: int, **overrides) -> dict:
    payload = {
        "account_id": account_id,
        "platform": "xhs",
        "status": "ACTIVE",
        "keywords": [
            {"keyword": "AI Agent project", "enabled": True},
            {"keyword": "AI Agent project", "enabled": True},
            {"keyword": "job search content", "enabled": True},
        ],
        "competitor_accounts": [
            {"name": "peer account", "profile_url": "https://www.xiaohongshu.com/user/profile/peer", "enabled": True},
            {"name": "peer account", "profile_url": "https://www.xiaohongshu.com/user/profile/peer", "enabled": True},
            {"platform_account_id": "xhs-1001", "enabled": False, "note": "watch only"},
        ],
        "note_urls": [
            "https://www.xiaohongshu.com/explore/note-1",
            "https://www.xiaohongshu.com/explore/note-1",
        ],
        "refresh_policy": {"manual_only": True},
        "metadata_payload": {"source": "user_config"},
    }
    payload.update(overrides)
    return payload


def test_upsert_data_source_config_creates_account_platform_config_only():
    account_id = _create_account()
    before_count = _crawl_task_count()
    response = _client().post("/agent/data-source-configs", json=_payload(account_id))

    assert response.status_code == 200
    data = response.json()
    assert data["account_id"] == account_id
    assert data["platform"] == "xhs"
    assert data["status"] == "ACTIVE"
    assert [item["keyword"] for item in data["keywords"]] == ["AI Agent project", "job search content"]
    assert len(data["competitor_accounts"]) == 2
    assert data["competitor_accounts"][1]["enabled"] is False
    assert data["note_urls"] == ["https://www.xiaohongshu.com/explore/note-1"]
    assert _crawl_task_count() == before_count


def test_upsert_data_source_config_replaces_same_account_platform_config():
    account_id = _create_account()
    first = _client().post("/agent/data-source-configs", json=_payload(account_id)).json()
    second = _client().post(
        "/agent/data-source-configs",
        json=_payload(
            account_id,
            keywords=[{"keyword": "new topic"}],
            competitor_accounts=[],
            note_urls=[],
        ),
    ).json()

    assert second["id"] == first["id"]
    assert second["keywords"] == [{"keyword": "new topic", "enabled": True, "note": None}]
    assert second["competitor_accounts"] == []


def test_get_and_list_data_source_configs_by_account():
    account_id = _create_account()
    created = _client().post("/agent/data-source-configs", json=_payload(account_id)).json()

    by_account = _client().get(f"/agent/data-source-configs/by-account/{account_id}?platform=xhs").json()
    listed = _client().get(f"/agent/data-source-configs?account_id={account_id}").json()
    by_id = _client().get(f"/agent/data-source-configs/{created['id']}").json()

    assert by_account["id"] == created["id"]
    assert by_id["id"] == created["id"]
    assert [item["id"] for item in listed] == [created["id"]]


def test_update_data_source_config_status_and_sources():
    account_id = _create_account()
    created = _client().post("/agent/data-source-configs", json=_payload(account_id)).json()

    response = _client().put(
        f"/agent/data-source-configs/{created['id']}",
        json={
            "status": "DISABLED",
            "keywords": [{"keyword": "disabled keyword"}],
            "competitor_accounts": [{"name": "another peer"}],
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "DISABLED"
    assert data["keywords"][0]["keyword"] == "disabled keyword"
    assert data["competitor_accounts"][0]["name"] == "another peer"


def test_missing_account_returns_404():
    response = _client().post("/agent/data-source-configs", json=_payload(999999999))

    assert response.status_code == 404
    assert response.json()["detail"] == "account not found"


def test_missing_config_returns_404():
    account_id = _create_account()
    response = _client().get(f"/agent/data-source-configs/by-account/{account_id}?platform=xhs")

    assert response.status_code == 404
    assert response.json()["detail"] == "data source config not found"
