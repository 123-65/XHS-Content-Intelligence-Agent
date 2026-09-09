from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_create_xhs_note_snapshot():
    """测试创建小红书笔记快照。"""
    payload = {
        "account_id": None,
        "source_type": "COMPETITOR",
        "keyword": "AI Agent",
        "note_url": "https://www.xiaohongshu.com/explore/65f123456789abcdef123456",
        "author_name": "测试博主",
        "author_homepage": "https://www.xiaohongshu.com/user/profile/test",
        "title": "普通大学生怎么入门 AI Agent",
        "content": "这是一篇测试笔记。",
        "tags": ["AI学习", "AI Agent"],
        "like_count": 100,
        "collect_count": 50,
        "comment_count": 10,
        "status": "SUCCESS"
    }

    response = client.post("/xhs/notes/snapshots", json=payload)
    assert response.status_code == 200

    data = response.json()
    assert data["code"] == 0
    assert data["data"]["source_type"] == "COMPETITOR"
    assert data["data"]["note_id"] == "65f123456789abcdef123456"


def test_list_xhs_note_snapshots():
    """测试查询小红书笔记快照列表。"""
    response = client.get("/xhs/notes/snapshots")
    assert response.status_code == 200

    data = response.json()
    assert data["code"] == 0
    assert isinstance(data["data"], list)


def test_parse_xhs_note_url_api():
    """测试笔记链接解析接口。"""
    response = client.get(
        "/xhs/notes/parse-url",
        params={"note_url": "https://www.xiaohongshu.com/explore/65f123456789abcdef123456"},
    )
    assert response.status_code == 200

    data = response.json()
    assert data["code"] == 0
    assert data["data"]["valid"] is True