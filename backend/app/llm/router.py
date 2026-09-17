from app.core.config import settings
from app.llm.providers.base import BaseLLMProvider
from app.llm.providers.deepseek_provider import DeepSeekProvider
from app.llm.providers.qwen_provider import QwenProvider
from app.llm.providers.zhipu_provider import ZhipuProvider
from app.llm.errors import LLMError
from app.schemas.provider_status import ProviderErrorCode


PROVIDER_CLASSES: dict[str, type[BaseLLMProvider]] = {
    "qwen": QwenProvider,
    "zhipu": ZhipuProvider,
    "deepseek": DeepSeekProvider,
}


def configured_provider_name(provider_name: str | None = None) -> str:
    """Return the configured provider name without using OPENAI_* env names."""
    if provider_name is not None:
        return provider_name.lower()
    configured = (settings.llm_provider or "").lower()
    return configured if configured and configured != "mock" else "deepseek"


def build_llm_provider(provider_name: str | None = None) -> BaseLLMProvider:
    """Build the requested provider without hiding fallback decisions."""
    selected = configured_provider_name(provider_name)
    provider_class = PROVIDER_CLASSES.get(selected)
    if not provider_class:
        raise LLMError(f"{ProviderErrorCode.LLM_PROVIDER_UNAVAILABLE.value}: unsupported provider {selected}")
    return provider_class(settings.llm_api_key, settings.llm_base_url, settings.llm_model)


def get_llm_provider(provider_name: str | None = None) -> BaseLLMProvider:
    """选择真实 LLM Provider；缺少配置或密钥时直接失败。"""
    provider = build_llm_provider(provider_name)
    return provider


def llm_health() -> dict:
    """Return current LLM provider health and fallback status."""
    requested = configured_provider_name()
    configured = bool(settings.llm_api_key and settings.llm_base_url and settings.llm_model)
    production_provider_candidates = list(PROVIDER_CLASSES)
    base_payload = {
        "requested_provider": requested,
        "configured": configured,
        "base_url_configured": bool(settings.llm_base_url),
        "api_key_configured": bool(settings.llm_api_key),
        "model_configured": bool(settings.llm_model),
        "fallback_provider": None,
        "fallback_active": False,
        "provider_candidates": production_provider_candidates,
        "production_provider_candidates": production_provider_candidates,
        "config_keys": ["LLM_PROVIDER", "LLM_API_KEY", "LLM_BASE_URL", "LLM_MODEL", "LLM_TIMEOUT_SECONDS", "LLM_MAX_RETRIES"],
    }
    try:
        provider = build_llm_provider(requested)
    except LLMError:
        return {
            **base_payload,
            "active_provider": None,
            "model": settings.llm_model,
            "available": False,
            "is_mock": False,
            "error_code": ProviderErrorCode.LLM_PROVIDER_UNAVAILABLE.value,
        }
    if not provider.available():
        return {
            **base_payload,
            "active_provider": None,
            "model": provider.model,
            "available": False,
            "is_mock": False,
            "error_code": ProviderErrorCode.LLM_CONFIG_MISSING.value,
        }
    return {
        **provider.health(),
        **base_payload,
        "error_code": None,
    }

