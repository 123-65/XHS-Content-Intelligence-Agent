from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.agent.schemas.interaction import PendingInteraction
from app.agent.schemas.semantic import Intent


class RuntimeAction(StrEnum):
    """冻结的七种用户层 Runtime Action。"""

    RESPOND = "RESPOND"
    CLARIFY = "CLARIFY"
    CONFIRM = "CONFIRM"
    QUERY = "QUERY"
    EXECUTE_PLAN = "EXECUTE_PLAN"
    EXECUTE_CONFIRMED_COMMAND = "EXECUTE_CONFIRMED_COMMAND"
    CANCEL = "CANCEL"


class WorkflowStatus(StrEnum):
    """冻结的 Workflow 运行状态。"""

    PENDING = "PENDING"
    RUNNING = "RUNNING"
    WAITING_USER = "WAITING_USER"
    SUCCESS = "SUCCESS"
    PARTIAL_SUCCESS = "PARTIAL_SUCCESS"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class ArtifactType(StrEnum):
    """冻结的七种系统产物类型。"""

    RESEARCH = "RESEARCH"
    CONTENT_STRATEGY = "CONTENT_STRATEGY"
    CONTENT_OPPORTUNITY = "CONTENT_OPPORTUNITY"
    DRAFT = "DRAFT"
    DRAFT_REVIEW = "DRAFT_REVIEW"
    POST_PUBLISH_REVIEW = "POST_PUBLISH_REVIEW"
    STRATEGY_CANDIDATE = "STRATEGY_CANDIDATE"


class ArtifactRef(BaseModel):
    """系统产物引用，与事实证据引用保持语义隔离。"""

    model_config = ConfigDict(extra="forbid")

    type: ArtifactType
    id: int = Field(gt=0)


class AgentTurnResult(BaseModel):
    """Runtime 面向前端和调用方的统一结果信封。"""

    model_config = ConfigDict(extra="forbid")

    action: RuntimeAction
    intent: Intent
    run_ref: str | None = None
    checkpoint_version: int | None = None
    message: str
    artifacts: list[ArtifactRef] = Field(default_factory=list)
    pending_interaction: PendingInteraction | None = None
    result: Any | None = None
    warnings: list[str] = Field(default_factory=list)
    error: Any | None = None
    status: WorkflowStatus
