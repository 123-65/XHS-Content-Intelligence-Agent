from typing import Any

from pydantic import BaseModel, Field


class LLMUsage(BaseModel):
    """模型 Token 用量。"""

    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


class LLMResult(BaseModel):
    """普通文本模型调用结果。"""

    text: str
    model: str
    provider: str
    usage: LLMUsage = Field(default_factory=LLMUsage)
    estimated_cost: float = 0
    raw_response_id: str | None = None
    is_mock: bool = False
    fallback_used: bool = False
    fallback_from: str | None = None
    latency_ms: int = 0
    prompt_key: str | None = None
    prompt_version: str | None = None
    error_message: str | None = None


class LLMStructuredResult(BaseModel):
    """结构化模型调用结果。"""

    data: Any
    text: str
    model: str
    provider: str
    usage: LLMUsage = Field(default_factory=LLMUsage)
    estimated_cost: float = 0
    raw_response_id: str | None = None
    is_mock: bool = False
    fallback_used: bool = False
    fallback_from: str | None = None
    latency_ms: int = 0
    prompt_key: str | None = None
    prompt_version: str | None = None
    error_message: str | None = None
    attempt_evidence: list[dict[str, Any]] = Field(default_factory=list, exclude=True)
