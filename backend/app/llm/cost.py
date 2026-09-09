from app.core.config import settings
from app.schemas.llm import LLMUsage


def estimate_cost(usage: LLMUsage) -> float:
    """根据 Token 用量估算模型调用成本。"""
    input_cost = usage.prompt_tokens / 1_000_000 * settings.llm_input_price_per_1m
    output_cost = usage.completion_tokens / 1_000_000 * settings.llm_output_price_per_1m
    return round(input_cost + output_cost, 6)
