from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.api.publication import _private_metrics_service
from app.main import app
from app.schemas.publication import PrivateMetricsInput, PrivateMetricsWriteRequest
from app.services.private_metrics_sev import PrivateMetricsService

START = datetime(2026, 9, 25, tzinfo=UTC)
END = START + timedelta(days=1)


class FakeRepository:
    """记录最小私域指标副作用并模拟 PublishedNote ownership。"""

    def __init__(self):
        """初始化冻结 PublishedNote 与空 Snapshot 列表。"""
        self.note = SimpleNamespace(id=592, account_id=8456)
        self.records = []

    def get_note(self, ref):
        """只返回冻结验收 PublishedNote。"""
        return self.note if ref == self.note.id else None

    def create_private_metrics(self, data):
        """保存服务收到的类型化输入。"""
        record = SimpleNamespace(id=len(self.records) + 1, collected_at=START, data=data)
        self.records.append(record)
        return record


def payload(**updates):
    """构造合法扁平 HTTP 请求。"""
    value = {
        "account_id": 8456, "label": "E2E009_ACCEPT",
        "window_start": START.isoformat(), "window_end": END.isoformat(),
        "dm_count": 3, "wechat_add_count": 1,
    }
    value.update(updates)
    return value


def test_private_metrics_http_partial_input_and_provenance():
    """验证正式路由只保存显式字段且 provenance 由服务端固定。"""
    repo = FakeRepository()
    app.dependency_overrides[_private_metrics_service] = lambda: PrivateMetricsService(None, repository=repo)
    try:
        response = TestClient(app).post("/api/published-notes/592/private-metrics", json=payload())
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 201
    assert response.json()["provenance"] == "USER_ATTRIBUTED"
    assert response.json()["metrics"] == {"dm_count": 3, "wechat_add_count": 1, "consultation_count": None, "deal_count": None, "revenue": None}
    assert repo.records[0].data.published_note_ref == 592


def test_explicit_zero_is_preserved_and_missing_all_is_rejected():
    """验证显式零有效，而完全缺失指标 fail closed。"""
    request = PrivateMetricsWriteRequest.model_validate(payload(dm_count=0, wechat_add_count=None))
    assert request.to_service_input(592).dm_count == 0
    with pytest.raises(ValidationError):
        PrivateMetricsWriteRequest.model_validate(payload(dm_count=None, wechat_add_count=None)).to_service_input(592)


def test_label_window_and_client_provenance_validation():
    """验证 label、非递增窗口和伪造 provenance 的边界。"""
    assert len(PrivateMetricsWriteRequest.model_validate(payload()).label) <= 16
    with pytest.raises(ValidationError):
        PrivateMetricsWriteRequest.model_validate(payload(window_end=START.isoformat())).to_service_input(592)
    with pytest.raises(ValidationError):
        PrivateMetricsWriteRequest.model_validate(payload(provenance="MEASURED"))


def test_cross_account_note_is_rejected_without_snapshot():
    """验证跨账号写入失败且不产生 Snapshot。"""
    repo = FakeRepository()
    data = PrivateMetricsInput.model_validate({"account_id": 9999, "published_note_ref": 592, "window": {"label": "D1", "window_start": START, "window_end": END}, "dm_count": 0})
    with pytest.raises(ValueError):
        PrivateMetricsService(None, repository=repo).record(data)
    assert repo.records == []
