"""Smoke test the configured LLM provider through LLMClient."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.llm.client import LLMClient


def run(prompt: str = "请用一句话说明你当前使用的模型能力。") -> dict:
    """Call the configured provider and return observability fields."""
    result = LLMClient().generate_text(prompt, prompt_key="llm_smoke_test", prompt_version="v1")
    return {
        "text": result.text,
        "provider": result.provider,
        "model": result.model,
        "is_mock": result.is_mock,
        "fallback_used": result.fallback_used,
        "fallback_from": result.fallback_from,
        "latency_ms": result.latency_ms,
        "input_token_count": result.usage.prompt_tokens,
        "output_token_count": result.usage.completion_tokens,
        "total_tokens": result.usage.total_tokens,
        "estimated_cost": result.estimated_cost,
        "error_message": result.error_message,
    }


if __name__ == "__main__":
    print(run())
