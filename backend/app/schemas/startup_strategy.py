from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class StartupStrategyCreate(BaseModel):
    """创建起号策略数据。"""

    account_id: int
    strategy_name: str = Field(min_length=1, max_length=128)
    persona_hypothesis: str | None = None
    content_mix: list[dict] = Field(default_factory=list)
    success_criteria: dict = Field(default_factory=dict)
    adjustment_rules: list[str] = Field(default_factory=list)
    status: str = Field(default="ACTIVE", max_length=32)


class StartupStrategyResponse(BaseModel):
    """起号策略响应。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    account_id: int
    strategy_name: str
    persona_hypothesis: str | None
    content_mix: list[dict]
    success_criteria: dict
    adjustment_rules: list[str]
    status: str
    created_at: datetime
    updated_at: datetime
