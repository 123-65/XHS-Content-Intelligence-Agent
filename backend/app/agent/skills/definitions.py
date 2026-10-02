from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class SkillId(StrEnum):
    """冻结的五个业务 Skill 标识。"""

    RESEARCH = "research"
    CONTENT_STRATEGY = "content_strategy"
    CONTENT_CREATION = "content_creation"
    CONTENT_REFINEMENT = "content_refinement"
    POST_PUBLISH_REVIEW = "post_publish_review"


class SkillDefinition(BaseModel):
    """不包含执行函数的静态 Skill 定义。"""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: SkillId
    description: str = Field(min_length=1)
    input_requirements: tuple[str, ...]
    output_type: str = Field(min_length=1)
    workflow_id: str = Field(min_length=1)
