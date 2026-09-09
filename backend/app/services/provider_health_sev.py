from app.core.config import settings
from app.crawler.providers.factory import PROVIDERS, PROVIDER_ORDER
from app.llm.router import llm_health


class ProviderHealthService:
    """Provider 健康检查服务。"""

    def health(self) -> dict:
        """返回 LLM、Crawler 和 Embedding Provider 健康状态。"""
        return {"llm": self._llm(), "crawler": self._crawler(), "embedding": self._embedding()}

    def llm_health(self) -> dict:
        """Return only LLM provider health for developer checks."""
        return self._llm()

    def _llm(self) -> dict:
        """返回 LLM Provider 健康状态。"""
        return llm_health()

    def _crawler(self) -> dict:
        """返回 Crawler Provider 健康状态。"""
        active = settings.xhs_crawler_provider if settings.xhs_crawler_provider in PROVIDERS else PROVIDER_ORDER[0]
        provider = PROVIDERS[active]
        is_mock = active in {"seed_sample", "mcp_xhs"}
        return {
            "active_provider": provider.name,
            "available": True,
            "fallback_provider": "seed_sample",
            "provider_order": list(PROVIDER_ORDER),
            "is_mock": is_mock,
            "guardrails": [
                "no_auto_like",
                "no_auto_comment",
                "no_auto_follow",
                "no_auto_dm",
                "no_captcha_bypass",
                "no_risk_control_bypass",
                "no_account_pool",
                "no_proxy_pool",
                "no_high_frequency_batch_collection",
            ],
        }

    def _embedding(self) -> dict:
        """返回 Embedding Provider 健康状态。"""
        is_mock = not settings.embedding_api_key or settings.embedding_provider == "mock"
        return {
            "active_provider": settings.embedding_provider if not is_mock else "mock",
            "model": settings.embedding_model,
            "available": True,
            "is_mock": is_mock,
        }
