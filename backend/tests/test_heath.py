from fastapi.testclient import TestClient

from app.main import app

test_client = TestClient(app)

def test_health_check():
    """测试健康检查接口。"""
    response = test_client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["code"] == 0
    assert data["message"] == "success"
    assert data["data"]["status"] == "ok"

def test_heath_check_db():
    """测试数据库健康检查接口。"""
    response = test_client.get("/health/db")
    assert response.status_code == 200
    data = response.json()
    assert data["code"] == 0
    assert data["data"]["database"] == "ok"