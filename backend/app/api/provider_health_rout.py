from fastapi import APIRouter, Query

from app.core.response import success
from app.llm.client import LLMClient
from app.services.provider_health_sev import ProviderHealthService

router = APIRouter(prefix="/api/providers", tags=["providers"])


@router.get("/health")
def provider_health():
    """Return provider health for LLM, crawler, and embedding."""
    return success(ProviderHealthService().health())


@router.get("/llm/health")
def llm_provider_health():
    """Return real LLM provider health and fallback status."""
    return success(ProviderHealthService().llm_health())


@router.post("/llm/test-text")
def test_llm_provider_text(prompt: str = Query(...)):
    """Call the configured LLM provider through LLMClient and return observability fields."""
    result = LLMClient().generate_text(
        prompt=prompt,
        system_prompt="You are a concise XHS Growth Intelligence Agent test assistant.",
        prompt_key="provider_health_test_text",
        prompt_version="v1",
    )
    return success(
        {
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
    )
