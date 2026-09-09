from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


TargetMetric = Literal["like", "collect", "comment", "engagement"]


class CompetitorAnalysisCreate(BaseModel):
    """创建竞品分析请求。"""

    account_id: int | None = None
    name: str = Field(min_length=1, max_length=128)
    keyword: str | None = Field(default=None, max_length=128)
    source_type: str = Field(default="COMPETITOR", max_length=32)
    target_metric: TargetMetric = "engagement"
    note_snapshot_ids: list[int] = Field(default_factory=list)
    limit: int = Field(default=30, ge=1, le=100)


class CompetitorAnalysisResponse(BaseModel):
    """竞品分析报告响应。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    account_id: int | None
    name: str
    keyword: str | None
    source_type: str
    target_metric: str
    note_snapshot_ids: list[int]
    note_count: int
    top_tags: list[dict]
    title_patterns: list[dict]
    high_performance_notes: list[dict]
    content_insights: list[str]
    suggestions: list[str]
    summary: str | None
    status: str
    error_message: str | None
    created_at: datetime
    updated_at: datetime