from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_create_competitor_analysis():
    """测试创建竞品分析报告。"""
    snapshot_ids = []

    for index in range(2):
        payload = {
            "account_id": None,
            "source_type": "COMPETITOR",
            "keyword": "AI Agent",
            "note_url": f"https://www.xiaohongshu.com/explore/65f123456789abcdef12345{index}",
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
        }

        response = client.post("/xhs/notes/snapshots", json=payload)
        assert response.status_code == 200
        snapshot_ids.append(response.json()["data"]["id"])

    response = client.post(
        "/competitor-analysis",
        json={
            "account_id": None,
            "name": "测试竞品分析",
            "keyword": "AI Agent",
            "source_type": "COMPETITOR",
            "target_metric": "engagement",
            "note_snapshot_ids": snapshot_ids,
            "limit": 10,
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["code"] == 0
    assert data["data"]["note_count"] == 2
    assert len(data["data"]["top_tags"]) > 0
    assert len(data["data"]["title_patterns"]) > 0
    assert len(data["data"]["high_performance_notes"]) > 0


def test_list_competitor_analysis():
    """测试查询竞品分析报告列表。"""
    response = client.get("/competitor-analysis")
    assert response.status_code == 200

    data = response.json()
    assert data["code"] == 0
    assert isinstance(data["data"], list)