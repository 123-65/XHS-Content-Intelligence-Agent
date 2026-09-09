from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def create_test_account() -> int:
    """创建测试账号并返回账号 ID。"""
    response = client.post(
        "/api/accounts",
        json={
            "account_name": "V2实验测试账号",
            "platform": "xhs",
            "homepage_url": "https://www.xiaohongshu.com/user/profile/experiment-v2-test",
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
            "account_stage": "STARTUP",
        },
    )
    assert response.status_code == 200
    return response.json()["data"]["id"]


def create_content_opportunities(account_id: int) -> int:
    """通过采集和竞品分析创建内容机会并返回报告 ID。"""
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
    assert client.post(f"/api/crawler/tasks/{task_id}/run").status_code == 200

    report_response = client.post(
        "/api/competitor/reports",
        json={"account_id": account_id, "name": "实验前置内容机会", "keyword": "AI Agent"},
    )
    assert report_response.status_code == 200
    return report_response.json()["data"]["id"]


def test_generate_experiment_cards_from_opportunities():
    """测试从内容机会生成候选实验卡。"""
    account_id = create_test_account()
    report_id = create_content_opportunities(account_id)

    response = client.post(
        "/api/experiments/generate",
        json={"account_id": account_id, "report_id": report_id, "limit": 3},
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["account_id"] == account_id
    assert data["count"] == 3

    first = data["experiments"][0]
    assert first["status"] == "CANDIDATE"
    assert first["experiment_name"]
    assert first["hypothesis"]
    assert first["content_pillar"]
    assert first["content_format"]
    assert first["main_variable"]
    assert first["control_variables"]
    assert first["primary_metric"]
    assert first["secondary_metrics"]
    assert first["success_criteria"]
    assert first["failure_criteria"]
    assert first["fallback_strategy"]
    assert first["risk_level"] in {"LOW", "MEDIUM", "HIGH"}
    assert first["variables"]
    assert first["metric_targets"]
    assert any(item["variable_name"] == "cta_strength" and item["variable_value"]["value"] == "SOFT" for item in first["variables"])


def test_get_list_and_approve_experiment_card():
    """测试查询和审批候选实验卡。"""
    account_id = create_test_account()
    report_id = create_content_opportunities(account_id)
    generate_response = client.post(
        "/api/experiments/generate",
        json={"account_id": account_id, "report_id": report_id, "limit": 3},
    )
    experiment_id = generate_response.json()["data"]["experiments"][0]["id"]

    list_response = client.get(f"/api/experiments?account_id={account_id}")
    assert list_response.status_code == 200
    assert any(item["id"] == experiment_id for item in list_response.json()["data"])

    detail_response = client.get(f"/api/experiments/{experiment_id}")
    assert detail_response.status_code == 200
    assert detail_response.json()["data"]["id"] == experiment_id

    approve_response = client.post(f"/api/experiments/{experiment_id}/approve")
    assert approve_response.status_code == 200
    assert approve_response.json()["data"]["status"] == "APPROVED"
