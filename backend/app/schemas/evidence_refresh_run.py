from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class EvidenceRefreshRunStatus(StrEnum):
    """证据刷新运行状态。"""

    RUNNING = "RUNNING"
    SUCCESS = "SUCCESS"
    PARTIAL = "PARTIAL"
    DATA_INSUFFICIENT = "DATA_INSUFFICIENT"
    FAILED = "FAILED"


class EvidenceRefreshRunCreate(BaseModel):
    """创建账号证据刷新运行请求。"""

    account_id: int = Field(gt=0)
    data_refresh_run_id: int | None = Field(default=None, gt=0)
    keyword: str | None = Field(default=None, max_length=128)
    target_metric: str = Field(default="composite", max_length=32)
    limit: int = Field(default=20, ge=1, le=100)
    name: str | None = Field(default=None, max_length=128)


class EvidenceRefreshRunResponse(BaseModel):
    """账号证据刷新运行响应。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    account_id: int
    data_refresh_run_id: int | None
    report_id: int | None
    trigger_type: str
    status: str
    keyword: str | None
    target_metric: str
    limit: int
    stats: dict[str, Any]
    error_code: str | None
    error_message: str | None
    started_at: datetime | None
    finished_at: datetime | None
    created_at: datetime
    updated_at: datetime
    report_summary: str | None = None
    note_count: int = 0
    comment_count: int = 0
    opportunity_count: int = 0
    breakdown_count: int = 0
    data_quality: str | None = None
    hint: str | None = None
