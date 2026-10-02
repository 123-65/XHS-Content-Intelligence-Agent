from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.agent.skills.definitions import SkillId
from app.agent.tools.definitions import ToolName


class WorkflowId(StrEnum):
    """冻结的五条 V1 Workflow 标识。"""

    RESEARCH_V1 = "RESEARCH_V1"
    CONTENT_STRATEGY_V1 = "CONTENT_STRATEGY_V1"
    CONTENT_CREATION_V1 = "CONTENT_CREATION_V1"
    CONTENT_REFINEMENT_V1 = "CONTENT_REFINEMENT_V1"
    POST_PUBLISH_REVIEW_V1 = "POST_PUBLISH_REVIEW_V1"


class WorkflowDefinition(BaseModel):
    """不含 execute、重试或实现绑定的静态 Workflow 定义。"""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: WorkflowId
    skill_id: SkillId
    allowed_tools: tuple[ToolName, ...]
    input_contract: str = Field(min_length=1)
    output_contract: str = Field(min_length=1)
    resumable: bool
    version: str = Field(pattern=r"^v\d+$")

    @field_validator("allowed_tools")
    @classmethod
    def reject_duplicate_tools(cls, value: tuple[ToolName, ...]) -> tuple[ToolName, ...]:
        """拒绝 Workflow Allowlist 中的重复 Tool。"""
        if len(value) != len(set(value)):
            raise ValueError("Workflow allowed_tools 不得重复")
        if not value:
            raise ValueError("Workflow 必须声明 Tool Allowlist")
        return value
