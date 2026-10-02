from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict

from app.agent.schemas.execution import WorkflowStatus
from app.agent.schemas.interaction import PendingInteraction
from app.agent.workflows.definitions import WorkflowId


class WorkflowRunErrorSnapshot(BaseModel):
    """可安全持久化的 Workflow 失败摘要，不包含 traceback。"""

    model_config = ConfigDict(extra="forbid")
    code: str
    category: str
    safe_message: str
    retryable: bool
    user_action: str | None = None
    source: str


class WorkflowResumeSnapshot(BaseModel):
    """Phase 2.4B 可用于 Resume 的 typed 读取结果。"""

    model_config = ConfigDict(arbitrary_types_allowed=True)
    run_ref: str
    workflow_name: WorkflowId
    account_id: int
    input: Any
    state: Any
    checkpoint_version: int
    pending_interaction: PendingInteraction | None = None


class WorkflowRunSnapshot(BaseModel):
    """Run 当前持久化状态的 typed service 视图。"""

    model_config = ConfigDict(arbitrary_types_allowed=True)
    run_ref: str
    workflow_name: WorkflowId
    account_id: int
    status: WorkflowStatus
    input: Any
    state: Any
    result: Any | None = None
    pending_interaction: PendingInteraction | None = None
    error: WorkflowRunErrorSnapshot | None = None
    warnings: list[str]
    checkpoint_version: int
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None = None
    execution_token: str | None = None
    lease_expires_at: datetime | None = None
    execution_mode: str | None = None
