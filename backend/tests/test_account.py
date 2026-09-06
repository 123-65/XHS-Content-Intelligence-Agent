from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_create_account():
    """测试创建账号配置。"""
    payload = {
        "account_name": "测试账号",
        "platform": "xhs",
        "homepage_url": "https://www.xiaohongshu.com/user/profile/test",
        "positioning": "测试账号定位",
        "target_audience": "测试目标用户",
        "business_model": "资料包",
        "main_product": "测试产品",
        "lead_value": 10,
        "avg_order_value": 99,
        "gross_profit": 80,
        "primary_goal": "lead",
        "tone_preference": "通俗直接",
        "forbidden_topics": "不夸大"
    }

    response = client.post("/accounts", json=payload)
    assert response.status_code == 200

    data = response.json()
    assert data["code"] == 0
    assert data["data"]["account_name"] == "测试账号"
    assert data["data"]["primary_goal"] == "lead"


def test_list_accounts():
    """测试查询账号配置列表。"""
    response = client.get("/accounts")
    assert response.status_code == 200

    data = response.json()
    assert data["code"] == 0
    assert isinstance(data["data"], list)


def test_account_not_found():
    """测试账号不存在。"""
    response = client.get("/accounts/999999")
    assert response.status_code == 404

    data = response.json()
    assert data["code"] == 404