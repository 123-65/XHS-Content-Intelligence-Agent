from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class CompetitorReportCreate(BaseModel):
    """创建 V2 竞品分析报告请求。"""

    account_id: int
    name: str = Field(min_length=1, max_length=128)
    keyword: str | None = Field(default=None, max_length=128)
    target_metric: str = Field(default="engagement", max_length=32)
    limit: int = Field(default=30, ge=1, le=100)
    analysis_engine: Literal["LLM_STRUCTURED_V1", "RULE_BASELINE"] = "LLM_STRUCTURED_V1"


class CompetitorReportResponse(BaseModel):
    """V2 竞品分析报告响应。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    account_id: int | None
    name: str
    keyword: str | None
    source_type: str
    target_metric: str
    competitor_account_ids: list[int]
    competitor_note_ids: list[int]
    note_count: int
    comment_count: int
    persona_patterns: list[dict]
    content_pillars: list[dict]
    top_tags: list[dict]
    title_patterns: list[dict]
    cover_patterns: list[dict]
    content_structures: list[dict]
    comment_demands: list[dict]
    conversion_signals: list[dict]
    replicability_summary: dict
    risk_points: list[dict]
    high_performance_notes: list[dict]
    content_insights: list[str]
    suggestions: list[str]
    summary: str | None
    status: str
    error_message: str | None
    created_at: datetime
    updated_at: datetime


class ViralNoteBreakdownResponse(BaseModel):
    """爆款笔记拆解响应。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    report_id: int
    competitor_note_id: int
    note_title: str | None
    note_url: str | None
    engagement_score: float
    title_pattern: str
    cover_pattern: str
    content_structure: str
    comment_demands: list[dict]
    conversion_signals: list[str]
    replicability_score: int
    risk_points: list[str]
    evidence_summary: str
    created_at: datetime


class ContentOpportunityResponse(BaseModel):
    """内容机会响应。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    report_id: int
    opportunity_title: str
    suggested_angle: str
    target_audience: str | None
    content_pillar: str
    comment_demand_type: str
    evidence_summary: str
    replicability_score: int
    risk_level: str
    risk_points: list[str]
    opportunity_score: int
    created_at: datetime
