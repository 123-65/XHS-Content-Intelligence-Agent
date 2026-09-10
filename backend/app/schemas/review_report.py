from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


RiskLevel = Literal["LOW", "MEDIUM", "HIGH"]


class ReviewIssue(BaseModel):
    """内容审核问题。"""

    field: str = Field(description="问题字段，例如 title、body、cta、image_scripts")
    level: RiskLevel = Field(description="问题等级")
    message: str = Field(description="问题说明")


class DraftReviewResult(BaseModel):
    """模型返回的草稿审核结果。"""

    passed: bool = Field(description="是否审核通过")
    score: int = Field(ge=0, le=100, description="综合评分")
    quality_score: int = Field(ge=0, le=100, description="内容质量评分")
    conversion_score: int = Field(ge=0, le=100, description="转化引导评分")
    evidence_usage_score: int = Field(ge=0, le=100, description="证据使用评分")
    risk_level: RiskLevel = Field(description="整体风险等级")
    issues: list[ReviewIssue] = Field(default_factory=list, description="问题列表")
    suggestions: list[str] = Field(default_factory=list, description="修改建议")
    summary: str = Field(description="审核总结")


class ReviewDraftRequest(BaseModel):
    """审核草稿请求。"""

    draft_id: int
    use_mock: bool = Field(default=False, description="是否使用模拟结果，仅测试/演示场景显式开启审核")


class ReviewReportCreate(BaseModel):
    """创建审核报告数据。"""

    draft_id: int
    passed: bool
    score: int
    quality_score: int
    conversion_score: int
    evidence_usage_score: int
    risk_level: str
    issues: list[dict] = Field(default_factory=list)
    suggestions: list[str] = Field(default_factory=list)
    summary: str | None = None
    status: str = "SUCCESS"
    error_message: str | None = None
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    estimated_cost: Decimal = Decimal("0")
    raw_response_id: str | None = None


class ReviewReportResponse(BaseModel):
    """审核报告响应。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    draft_id: int
    passed: bool
    score: int
    quality_score: int
    conversion_score: int
    evidence_usage_score: int
    risk_level: str
    issues: list[dict]
    suggestions: list[str]
    summary: str | None
    status: str
    error_message: str | None
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    estimated_cost: Decimal
    raw_response_id: str | None
    created_at: datetime
