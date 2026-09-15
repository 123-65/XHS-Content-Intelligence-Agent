from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class RefreshTriggerType(StrEnum):
    """数据刷新触发方式。"""

    USER_CLICK = "USER_CLICK"
    AGENT_COMMAND = "AGENT_COMMAND"


class RefreshRunStatus(StrEnum):
    """数据刷新运行状态。"""

    PENDING = "PENDING"
    RUNNING = "RUNNING"
    SUCCESS = "SUCCESS"
    PARTIAL = "PARTIAL"
    FAILED = "FAILED"
    PROVIDER_NOT_CONFIGURED = "PROVIDER_NOT_CONFIGURED"


class DataRefreshRunCreate(BaseModel):
    """创建账号数据刷新运行请求。"""

    account_id: int = Field(gt=0)
    data_source_config_id: int | None = Field(default=None, gt=0)
    trigger_type: RefreshTriggerType = RefreshTriggerType.USER_CLICK
    force: bool = False


class DataRefreshRunResponse(BaseModel):
    """账号数据刷新运行响应。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    account_id: int
    data_source_config_id: int | None
    trigger_type: str
    status: str
    refresh_scope_days: int
    started_at: datetime | None
    finished_at: datetime | None
    stats: dict[str, Any]
    error_code: str | None
    error_message: str | None
    created_at: datetime
    updated_at: datetime
