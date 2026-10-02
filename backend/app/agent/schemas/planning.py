from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.agent.schemas.execution import RuntimeAction, WorkflowStatus
from app.agent.schemas.semantic import Intent


class PlanStatus(StrEnum):
    """冻结的计划阶段状态。"""

    READY = "READY"
    NEED_USER_INPUT = "NEED_USER_INPUT"
    UNSUPPORTED = "UNSUPPORTED"


class PlanStep(BaseModel):
    """Planner 选择到 Skill 与 Workflow 为止的计划步骤。"""

    model_config = ConfigDict(extra="forbid")

    step_id: str = Field(min_length=1)
    skill_id: str = Field(min_length=1)
    workflow_id: str = Field(min_length=1)
    depends_on: list[str] = Field(default_factory=list)
    reason: str = Field(min_length=1)
    workflow_input: dict[str, Any] | None = None
    executable: bool = True


class ExecutionPlan(BaseModel):
    """Planner 的统一输出合同，不包含 Tool 级执行顺序。"""

    model_config = ConfigDict(extra="forbid")

    plan_id: str = Field(min_length=1)
    primary_intent: Intent
    action: RuntimeAction
    steps: list[PlanStep] = Field(default_factory=list)
    required_inputs: list[str] = Field(default_factory=list)
    missing_inputs: list[str] = Field(default_factory=list)
    status: PlanStatus


class PlanStepExecution(BaseModel):
    """PlanExecutionService 返回的单 Step Runtime 结果。"""

    model_config = ConfigDict(extra="forbid")

    step_id: str
    run_ref: str
    checkpoint_version: int | None = None
    status: WorkflowStatus
    pending_interaction: Any | None = None
    result: Any | None = None
    error: Any | None = None


class PlanExecutionResult(BaseModel):
    """薄执行层的结果；不创建交互，也不隐藏 Runtime 状态。"""

    model_config = ConfigDict(extra="forbid")

    plan_id: str
    step_results: list[PlanStepExecution] = Field(default_factory=list)
    stopped_before_step: str | None = None
    status: WorkflowStatus | None = None
