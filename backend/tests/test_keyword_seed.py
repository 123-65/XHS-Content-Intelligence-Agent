from fastapi.testclient import TestClient

from app.enums.keyword import KeywordCategory
from app.main import app

client = TestClient(app)


def create_v2_account() -> int:
    """创建 V2 账号画像并返回账号 ID。"""
    response = client.post(
        "/api/accounts",
        json={
            "account_name": "关键词测试账号",
            "platform": "xhs",
            "homepage_url": "https://www.xiaohongshu.com/user/profile/keyword-test",
            "content_domain": "AI Agent",
            "positioning": "帮助普通大学生做能写进简历的 AI Agent 项目",
            "target_audience": "大学生、转码初学者、27届应届生",
            "persona": "实话型项目学姐",
            "monetization_goal": "资料包和咨询转化",
            "business_model": "资料包 / 咨询",
            "main_product": "AI Agent 项目资料包",
            "lead_value": 15,
            "avg_order_value": 99,
            "gross_profit": 80,
            "primary_goal": "lead",
            "tone_preference": "通俗直接",
            "forbidden_topics": "不夸大收益",
            "risk_preference": "CONSERVATIVE",
            "account_stage": "STARTUP",
        },
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["content_domain"] == "AI Agent"
    assert data["persona"] == "实话型项目学姐"
    return data["id"]


def test_generate_keyword_seeds():
    """测试规则模板生成关键词池。"""
    account_id = create_v2_account()

    response = client.post(
        "/api/crawler/keywords/generate",
        json={"account_id": account_id, "limit_per_category": 3},
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["account_id"] == account_id
    assert data["count"] == 12
    assert {item["category"] for item in data["keywords"]} == {category.value for category in KeywordCategory}
    assert all(item["account_id"] == account_id for item in data["keywords"])
    assert all(item["source_type"] == "RULE_TEMPLATE" for item in data["keywords"])
    assert all("raw_snapshot" in item for item in data["keywords"])


def test_list_keyword_seeds_by_account_and_category():
    """测试查询账号关键词池和分类筛选。"""
    account_id = create_v2_account()
    generate_response = client.post(
        "/api/crawler/keywords/generate",
        json={"account_id": account_id, "limit_per_category": 2},
    )
    assert generate_response.status_code == 200

    list_response = client.get(f"/api/crawler/keywords?account_id={account_id}")
    assert list_response.status_code == 200
    assert len(list_response.json()["data"]) == 8

    category_response = client.get(
        f"/api/crawler/keywords?account_id={account_id}&category={KeywordCategory.USER_DEMAND.value}"
    )
    assert category_response.status_code == 200
    data = category_response.json()["data"]
    assert len(data) == 2
    assert all(item["category"] == KeywordCategory.USER_DEMAND.value for item in data)
