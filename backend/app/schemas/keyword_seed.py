from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.enums.keyword import KeywordCategory


class KeywordGenerateRequest(BaseModel):
    """生成关键词请求。"""

    account_id: int
    limit_per_category: int = Field(default=5, ge=1, le=20)


class KeywordSeedCreate(BaseModel):
    """创建关键词种子数据。"""

    account_id: int
    keyword: str = Field(min_length=1, max_length=128)
    category: KeywordCategory
    reason: str | None = None
    source_type: str = Field(default="RULE_TEMPLATE", max_length=32)
    confidence: float = Field(default=0.8, ge=0, le=1)
    raw_snapshot: dict = Field(default_factory=dict)


class KeywordSeedResponse(BaseModel):
    """关键词种子响应。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    account_id: int
    keyword: str
    category: str
    reason: str | None
    source_type: str
    confidence: float
    raw_snapshot: dict
    collected_at: datetime
    created_at: datetime


class KeywordGenerateResponse(BaseModel):
    """生成关键词响应。"""

    account_id: int
    count: int
    keywords: list[KeywordSeedResponse]
