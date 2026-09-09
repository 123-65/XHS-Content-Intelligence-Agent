from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def create_test_account(name: str = "采集测试账号") -> int:
    """创建测试账号并返回账号 ID。"""
    response = client.post(
        "/api/accounts",
        json={
            "account_name": name,
            "platform": "xhs",
            "homepage_url": "https://www.xiaohongshu.com/user/profile/crawler-test",
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


def test_seed_sample_crawl_task_flow():
    """测试 SeedSampleProvider 采集任务完整流程。"""
    account_id = create_test_account()
    create_response = client.post(
        "/api/crawler/tasks",
        json={
            "account_id": account_id,
            "task_type": "COMPETITOR_SEED",
            "provider_name": "seed_sample",
            "keyword": "AI Agent",
        },
    )
    assert create_response.status_code == 200
    task_id = create_response.json()["data"]["id"]

    run_response = client.post(f"/api/crawler/tasks/{task_id}/run")
    assert run_response.status_code == 200
    task = run_response.json()["data"]
    assert task["status"] == "SUCCESS"
    assert task["result_count"] == 7
    assert task["success_count"] == 7
    assert task["failed_count"] == 0
    assert task["confidence"] > 0

    detail_response = client.get(f"/api/crawler/tasks/{task_id}")
    assert detail_response.status_code == 200
    assert detail_response.json()["data"]["id"] == task_id

    accounts_response = client.get(f"/api/competitor/accounts?account_id={account_id}")
    assert accounts_response.status_code == 200
    accounts = accounts_response.json()["data"]
    assert len(accounts) == 1
    assert accounts[0]["source_type"] == "SEED_SAMPLE"
    assert accounts[0]["raw_snapshot"]["provider"] == "seed_sample"

    notes_response = client.get(f"/api/competitor/notes?account_id={account_id}")
    assert notes_response.status_code == 200
    notes = notes_response.json()["data"]
    assert len(notes) == 3
    assert all(note["account_id"] == account_id for note in notes)
    assert all(note["source_type"] == "SEED_SAMPLE" for note in notes)
    assert any("AI Agent" in (note["title"] or "") for note in notes)


def test_manual_provider_crawl_task_flow():
    """测试 ManualProvider 人工数据采集流程。"""
    account_id = create_test_account("人工采集测试账号")
    create_response = client.post(
        "/api/crawler/tasks",
        json={
            "account_id": account_id,
            "task_type": "COMPETITOR_MANUAL",
            "provider_name": "manual",
            "input_payload": {
                "accounts": [
                    {
                        "nickname": "手动录入同行",
                        "homepage_url": "https://www.xiaohongshu.com/user/profile/manual",
                        "bio": "手动整理的同行账号。",
                        "follower_count": 5200,
                    }
                ],
                "notes": [
                    {
                        "note_id": "manual-note-1",
                        "note_url": "https://www.xiaohongshu.com/explore/manual-note-1",
                        "author_name": "手动录入同行",
                        "title": "AI Agent 项目怎么写进简历",
                        "content": "人工整理的竞品笔记。",
                        "tags": ["AI Agent", "简历项目"],
                        "like_count": 300,
                        "collect_count": 180,
                        "comment_count": 26,
                    }
                ],
                "comments": [{"content": "想看项目结构图", "user_name": "手动评论用户"}],
            },
        },
    )
    assert create_response.status_code == 200
    task_id = create_response.json()["data"]["id"]

    run_response = client.post(f"/api/crawler/tasks/{task_id}/run")

    assert run_response.status_code == 200
    task = run_response.json()["data"]
    assert task["status"] == "SUCCESS"
    assert task["result_count"] == 3

    accounts = client.get(f"/api/competitor/accounts?account_id={account_id}").json()["data"]
    notes = client.get(f"/api/competitor/notes?account_id={account_id}").json()["data"]
    assert accounts[0]["source_type"] == "MANUAL"
    assert notes[0]["source_type"] == "MANUAL"
    assert notes[0]["raw_snapshot"]["note_id"] == "manual-note-1"
