from app.core.config import settings
from app.llm.providers.base import BaseLLMProvider
from app.llm.providers.deepseek_provider import DeepSeekProvider
from app.llm.providers.mock_provider import MockLLMProvider
from app.llm.providers.qwen_provider import QwenProvider
from app.llm.providers.zhipu_provider import ZhipuProvider


PROVIDER_CLASSES: dict[str, type[BaseLLMProvider]] = {
    "qwen": QwenProvider,
    "zhipu": ZhipuProvider,
    "deepseek": DeepSeekProvider,
    "mock": MockLLMProvider,
}


def configured_provider_name(provider_name: str | None = None) -> str:
    """Return the configured provider name without using OPENAI_* env names."""
    return (provider_name or settings.llm_provider or "mock").lower()


def build_llm_provider(provider_name: str | None = None) -> BaseLLMProvider:
    """Build the requested provider without hiding fallback decisions."""
    selected = configured_provider_name(provider_name)
    if selected == "mock":
        return MockLLMProvider()
    provider_class = PROVIDER_CLASSES.get(selected)
    if not provider_class:
        return MockLLMProvider()
    return provider_class(settings.llm_api_key, settings.llm_base_url, settings.llm_model)


def get_llm_provider(provider_name: str | None = None) -> BaseLLMProvider:
    """Select an LLM Provider; no API key automatically falls back to Mock."""
    provider = build_llm_provider(provider_name)
    return provider if provider.available() else MockLLMProvider()


def llm_health() -> dict:
    """Return current LLM provider health and fallback status."""
    requested = configured_provider_name()
    provider = build_llm_provider(requested)
    configured = bool(settings.llm_api_key and settings.llm_base_url and settings.llm_model)
    active = provider if provider.available() else MockLLMProvider()
    return {
        **active.health(),
        "requested_provider": requested,
        "configured": configured,
        "base_url_configured": bool(settings.llm_base_url),
        "api_key_configured": bool(settings.llm_api_key),
        "fallback_provider": "mock",
        "fallback_active": active.is_mock and requested != "mock",
        "provider_candidates": list(PROVIDER_CLASSES),
        "config_keys": ["LLM_PROVIDER", "LLM_API_KEY", "LLM_BASE_URL", "LLM_MODEL", "LLM_TIMEOUT_SECONDS", "LLM_MAX_RETRIES"],
    }

