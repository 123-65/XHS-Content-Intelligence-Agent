from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class EvidenceType(StrEnum):
    """研究阶段允许读取的事实证据类型。"""

    NOTE = "NOTE"
    COMMENT = "COMMENT"
    ACCOUNT = "ACCOUNT"


class EvidenceRef(BaseModel):
    """事实证据引用，与系统 Artifact 引用严格分离。"""

    model_config = ConfigDict(extra="forbid", frozen=True)

    type: EvidenceType
    id: int = Field(gt=0)
