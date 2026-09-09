from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def create_test_account() -> int:
    """创建测试账号并返回账号 ID。"""
    response = client.post(
        "/accounts",
        json={
            "account_name": "草稿测试账号",
            "platform": "xhs",
            "homepage_url": "https://www.xiaohongshu.com/user/profile/draft-test",
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


def create_test_experiment() -> int:
    """创建测试内容实验并返回实验 ID。"""
    account_id = create_test_account()
    response = client.post(
        "/experiments",
        json={
            "account_id": account_id,
            "experiment_name": "AI Agent 学习路线内容实验",
            "hypothesis": "路线型内容更容易带来收藏和评论。",
            "target_metric": "collect",
            "expected_result": "收藏数 >= 100",
            "topic_angle": "路线步骤型",
            "selected_topic": "普通大学生 AI Agent 学习路线",
            "target_values": {"collect_count": 100},
            "source_type": "MANUAL_TOPIC",
        },
    )
    assert response.status_code == 200
    return response.json()["data"]["id"]


def test_generate_content_draft_with_mock():
    """测试使用 mock 生成内容草稿。"""
    experiment_id = create_test_experiment()

    response = client.post(
        "/drafts/generate",
        json={
            "experiment_id": experiment_id,
            "user_requirement": "语气像学姐给普通大学生的实话建议，不要太营销",
            "use_mock": True,
        },
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["experiment_id"] == experiment_id
    assert data["image_scripts"]
    assert data["version"] == 1
    assert data["status"] == "GENERATED"


def test_list_and_get_content_draft():
    """测试查询实验草稿列表和草稿详情。"""
    experiment_id = create_test_experiment()
    create_response = client.post("/drafts/generate", json={"experiment_id": experiment_id, "use_mock": True})
    draft_id = create_response.json()["data"]["id"]

    list_response = client.get(f"/drafts/experiment/{experiment_id}")
    assert list_response.status_code == 200
    assert any(item["id"] == draft_id for item in list_response.json()["data"])

    detail_response = client.get(f"/drafts/{draft_id}")
    assert detail_response.status_code == 200
    assert detail_response.json()["data"]["id"] == draft_id
