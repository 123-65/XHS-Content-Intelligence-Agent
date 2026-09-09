from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def create_test_account() -> int:
    """创建测试账号并返回账号 ID。"""
    response = client.post(
        "/accounts",
        json={
            "account_name": "测试 AI 项目号",
            "platform": "xhs",
            "homepage_url": "https://www.xiaohongshu.com/user/profile/test",
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


def create_test_analysis_report(account_id: int) -> int:
    """创建测试竞品分析报告并返回报告 ID。"""
    snapshot_ids = []
    for index in range(2):
        response = client.post(
            "/xhs/notes/snapshots",
            json={
                "account_id": account_id,
                "source_type": "COMPETITOR",
                "keyword": "AI Agent",
                "note_url": f"https://www.xiaohongshu.com/explore/75f123456789abcdef12345{index}",
                "author_name": "测试竞品博主",
                "title": f"普通大学生怎么做 AI Agent 项目 {index}",
                "content": "正文主要讲 AI Agent 学习路线和项目实战。",
                "tags": ["AI学习", "AI Agent", "项目实战"],
                "image_urls": ["https://example.com/1.jpg"],
                "image_ocr_text": "图片内容：AI Agent 学习路线，先学 SDK，再做 Workflow。",
                "like_count": 100 + index,
                "collect_count": 60 + index,
                "comment_count": 10 + index,
                "status": "SUCCESS",
            },
        )
        assert response.status_code == 200
        snapshot_ids.append(response.json()["data"]["id"])

    response = client.post(
        "/competitor-analysis",
        json={
            "account_id": account_id,
            "name": "内容实验前置竞品分析",
            "keyword": "AI Agent",
            "source_type": "COMPETITOR",
            "target_metric": "engagement",
            "note_snapshot_ids": snapshot_ids,
            "limit": 10,
        },
    )
    assert response.status_code == 200
    return response.json()["data"]["id"]


def test_create_content_experiment():
    """测试创建内容实验。"""
    account_id = create_test_account()

    response = client.post(
        "/experiments",
        json={
            "account_id": account_id,
            "analysis_report_id": None,
            "experiment_name": "测试内容实验",
            "hypothesis": "路线型内容更容易带来收藏。",
            "target_metric": "collect",
            "expected_result": "收藏数 >= 100",
            "topic_angle": "路线步骤型",
            "selected_topic": "普通大学生 AI Agent 学习路线",
            "target_values": {"collect_count": 100},
            "source_type": "MANUAL_TOPIC",
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["code"] == 0
    assert data["data"]["account_id"] == account_id
    assert data["data"]["status"] == "DRAFT"
    assert data["data"]["target_metric"] == "collect"


def test_list_content_experiments():
    """测试查询内容实验列表。"""
    response = client.get("/experiments")
    assert response.status_code == 200

    data = response.json()
    assert data["code"] == 0
    assert isinstance(data["data"], list)


def test_get_content_experiment_detail():
    """测试查询内容实验详情。"""
    account_id = create_test_account()
    create_response = client.post(
        "/experiments",
        json={
            "account_id": account_id,
            "experiment_name": "详情查询测试",
            "hypothesis": "测试内容实验详情查询。",
            "target_metric": "collect",
            "target_values": {"collect_count": 100},
            "source_type": "MANUAL_TOPIC",
        },
    )
    experiment_id = create_response.json()["data"]["id"]

    response = client.get(f"/experiments/{experiment_id}")
    assert response.status_code == 200
    assert response.json()["data"]["id"] == experiment_id


def test_update_content_experiment_status():
    """测试更新内容实验状态。"""
    account_id = create_test_account()
    create_response = client.post(
        "/experiments",
        json={
            "account_id": account_id,
            "experiment_name": "状态流转测试",
            "hypothesis": "测试实验状态从 DRAFT 到 READY。",
            "target_metric": "collect",
            "expected_result": "收藏数 >= 100",
            "topic_angle": "路线步骤型",
            "selected_topic": "AI Agent 学习路线",
            "target_values": {"collect_count": 100},
            "source_type": "MANUAL_TOPIC",
        },
    )
    experiment_id = create_response.json()["data"]["id"]

    response = client.put(f"/experiments/{experiment_id}", json={"status": "READY"})
    assert response.status_code == 200

    data = response.json()
    assert data["code"] == 0
    assert data["data"]["status"] == "READY"


def test_invalid_status_change():
    """测试非法实验状态流转。"""
    account_id = create_test_account()
    create_response = client.post(
        "/experiments",
        json={
            "account_id": account_id,
            "experiment_name": "非法状态流转测试",
            "hypothesis": "不能从 DRAFT 直接变成 ANALYZED。",
            "target_metric": "collect",
            "expected_result": "收藏数 >= 100",
            "topic_angle": "路线步骤型",
            "selected_topic": "AI Agent 学习路线",
            "target_values": {"collect_count": 100},
            "source_type": "MANUAL_TOPIC",
        },
    )
    experiment_id = create_response.json()["data"]["id"]

    response = client.put(f"/experiments/{experiment_id}", json={"status": "ANALYZED"})
    assert response.status_code == 400
    assert response.json()["code"] == 400


def test_create_content_experiment_from_analysis():
    """测试基于竞品分析报告创建内容实验。"""
    account_id = create_test_account()
    report_id = create_test_analysis_report(account_id)

    response = client.post(
        f"/experiments/from-analysis/{report_id}",
        json={
            "account_id": account_id,
            "target_metric": "collect",
            "target_values": {"collect_count": 100, "comment_count": 20, "lead_count": 5},
        },
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["analysis_report_id"] == report_id
    assert data["source_type"] == "COMPETITOR_ANALYSIS"
    assert data["selected_topic"]
    assert data["hypothesis"]
