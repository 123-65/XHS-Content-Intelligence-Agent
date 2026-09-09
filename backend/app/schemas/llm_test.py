from pydantic import BaseModel, Field


class LLMTestAnalysisResult(BaseModel):
    """LLM 测试分析结果。"""

    summary: str = Field(description="一句话摘要")
    suggestions: list[str] = Field(description="建议列表")
    score: int = Field(ge=0, le=100, description="质量评分")
