from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class PendingInteractionType(StrEnum):
    """冻结的等待用户交互类型。"""

    CLARIFICATION = "CLARIFICATION"
    CONFIRMATION = "CONFIRMATION"


class PendingInteraction(BaseModel):
    """澄清与确认共用的等待用户合同。"""

    model_config = ConfigDict(extra="forbid")

    type: PendingInteractionType
    reason: str = Field(min_length=1)
    required_fields: list[str] = Field(default_factory=list)
    options: list[str] = Field(default_factory=list)
    related_run_ref: str | None = None
    resume_token: str = Field(min_length=1)
