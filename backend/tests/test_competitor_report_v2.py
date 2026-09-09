from fastapi.testclient import TestClient

from app.enums.competitor_analysis import CommentDemandType, RiskLevel
from app.main import app

client = TestClient(app)


def create_test_account() -> int:
    """创建测试账号并返回账号 ID。"""
    response = client.post(
        "/api/accounts",
        json={
            "account_name": "V2竞品分析测试账号",
            "platform": "xhs",
            "homepage_url": "https://www.xiaohongshu.com/user/profile/report-v2-test",
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
        },
    )
    assert response.status_code == 200
    return response.json()["data"]["id"]


def seed_competitor_data(account_id: int) -> None:
    """运行 SeedSampleProvider 生成竞品数据。"""
    task_response = client.post(
        "/api/crawler/tasks",
        json={
            "account_id": account_id,
            "task_type": "COMPETITOR_SEED",
            "provider_name": "seed_sample",
            "keyword": "AI Agent",
        },
    )
    assert task_response.status_code == 200
    task_id = task_response.json()["data"]["id"]
    run_response = client.post(f"/api/crawler/tasks/{task_id}/run")
    assert run_response.status_code == 200
    assert run_response.json()["data"]["status"] == "SUCCESS"


def test_create_competitor_report_v2():
    """测试创建 V2 竞品与爆款分析报告。"""
    account_id = create_test_account()
    seed_competitor_data(account_id)

    response = client.post(
        "/api/competitor/reports",
        json={
            "account_id": account_id,
            "name": "AI Agent 竞品与爆款分析",
            "keyword": "AI Agent",
            "target_metric": "engagement",
            "limit": 20,
        },
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["account_id"] == account_id
    assert data["source_type"] == "COMPETITOR_COLLECTION"
    assert data["note_count"] == 3
    assert data["comment_count"] == 3
    assert data["persona_patterns"]
    assert data["content_pillars"]
    assert data["title_patterns"]
    assert data["cover_patterns"]
    assert data["content_structures"]
    assert data["comment_demands"]
    assert data["conversion_signals"]
    assert "avg_score" in data["replicability_summary"]
    assert data["risk_points"]


def test_get_viral_notes_and_opportunities():
    """测试查询爆款笔记拆解和内容机会。"""
    account_id = create_test_account()
    seed_competitor_data(account_id)
    report_response = client.post(
        "/api/competitor/reports",
        json={"account_id": account_id, "name": "内容机会分析", "keyword": "AI Agent"},
    )
    report_id = report_response.json()["data"]["id"]

    detail_response = client.get(f"/api/competitor/reports/{report_id}")
    assert detail_response.status_code == 200
    assert detail_response.json()["data"]["id"] == report_id

    viral_response = client.get(f"/api/competitor/reports/{report_id}/viral-notes")
    assert viral_response.status_code == 200
    viral_notes = viral_response.json()["data"]
    assert len(viral_notes) >= 1
    assert viral_notes[0]["evidence_summary"]
    assert viral_notes[0]["replicability_score"] >= 0
    assert isinstance(viral_notes[0]["comment_demands"], list)

    opportunities_response = client.get(f"/api/competitor/reports/{report_id}/opportunities")
    assert opportunities_response.status_code == 200
    opportunities = opportunities_response.json()["data"]
    assert len(opportunities) >= 1
    first = opportunities[0]
    assert first["evidence_summary"]
    assert first["comment_demand_type"] in {item.value for item in CommentDemandType}
    assert first["risk_level"] in {item.value for item in RiskLevel}
    assert 0 <= first["replicability_score"] <= 100
    assert 0 <= first["opportunity_score"] <= 100
