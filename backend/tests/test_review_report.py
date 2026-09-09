from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def create_test_account() -> int:
    """创建测试账号并返回账号 ID。"""
    response = client.post(
        "/accounts",
        json={
            "account_name": "审核测试账号",
            "platform": "xhs",
            "homepage_url": "https://www.xiaohongshu.com/user/profile/review-test",
            "positioning": "帮助大学生学习 AI Agent 项目",
            "target_audience": "大学生、转码初学者、27届应届生",
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


def create_test_draft() -> int:
    """创建测试草稿并返回草稿 ID。"""
    account_id = create_test_account()
    experiment_response = client.post(
        "/experiments",
        json={
            "account_id": account_id,
            "experiment_name": "审核链路内容实验",
            "hypothesis": "路线型内容更容易带来收藏和评论。",
            "target_metric": "collect",
            "expected_result": "收藏数 >= 100",
            "topic_angle": "路线步骤型",
            "selected_topic": "普通大学生 AI Agent 学习路线",
            "target_values": {"collect_count": 100},
            "source_type": "MANUAL_TOPIC",
        },
    )
    assert experiment_response.status_code == 200
    experiment_id = experiment_response.json()["data"]["id"]

    draft_response = client.post("/drafts/generate", json={"experiment_id": experiment_id, "use_mock": True})
    assert draft_response.status_code == 200
    return draft_response.json()["data"]["id"]


def test_review_content_draft_with_mock():
    """测试使用 mock 审核内容草稿。"""
    draft_id = create_test_draft()

    response = client.post("/reviews/draft", json={"draft_id": draft_id, "use_mock": True})

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["draft_id"] == draft_id
    assert isinstance(data["issues"], list)
    assert isinstance(data["suggestions"], list)
    assert data["risk_level"] in {"LOW", "MEDIUM", "HIGH"}

    draft_response = client.get(f"/drafts/{draft_id}")
    assert draft_response.json()["data"]["status"] in {"REVIEW_PASSED", "REVIEW_FAILED"}


def test_list_review_reports_by_draft():
    """测试查询草稿审核报告列表。"""
    draft_id = create_test_draft()
    review_response = client.post("/reviews/draft", json={"draft_id": draft_id, "use_mock": True})
    report_id = review_response.json()["data"]["id"]

    response = client.get(f"/reviews/draft/{draft_id}")

    assert response.status_code == 200
    assert any(item["id"] == report_id for item in response.json()["data"])
