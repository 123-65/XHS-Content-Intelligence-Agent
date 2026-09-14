from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.agent.product_entry.schemas import Action, ConfirmationRequirement, RiskFlag


class ExecutionSchema(BaseModel):
    """执行层 Schema 基类，禁止未声明字段进入结果。"""

    model_config = ConfigDict(extra="forbid")


class ExecutionMode(StrEnum):
    """执行模式。"""

    DRY_RUN = "DRY_RUN"
    REAL = "REAL"


class ExecutionStatus(StrEnum):
    """执行状态。"""

    NOT_STARTED = "NOT_STARTED"
    SKIPPED = "SKIPPED"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    BLOCKED = "BLOCKED"
    WAITING_CONFIRMATION = "WAITING_CONFIRMATION"
    NEED_CLARIFICATION = "NEED_CLARIFICATION"


class StepExecutionResult(ExecutionSchema):
    """单个计划步骤的执行结果。"""

    step_order: int
    action: Action
    status: ExecutionStatus
    can_execute: bool = False
    dry_run: bool = True
    output: dict[str, Any] = Field(default_factory=dict)
    error_code: str | None = None
    message: str | None = None
    risk_flags: list[RiskFlag] = Field(default_factory=list)
    started_at: datetime | None = None
    finished_at: datetime | None = None


class PlanExecutionResult(ExecutionSchema):
    """完整计划的执行结果。"""

    plan_id: str | None = None
    session_id: str | None = None
    trace_id: str | None = None
    status: ExecutionStatus
    mode: ExecutionMode = ExecutionMode.DRY_RUN
    can_execute: bool = False
    step_results: list[StepExecutionResult] = Field(default_factory=list)
    output: dict[str, Any] = Field(default_factory=dict)
    error_code: str | None = None
    message: str | None = None
    risk_flags: list[RiskFlag] = Field(default_factory=list)
    confirmation_requirement: ConfirmationRequirement | None = None


def utc_now() -> datetime:
    """返回统一 UTC 时间，便于执行结果记录。"""
    return datetime.now(UTC)
