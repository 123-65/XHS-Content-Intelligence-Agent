from app.core.config import settings
from app.crawler.providers.factory import PROVIDERS, PROVIDER_ORDER
from app.llm.router import llm_health
from app.schemas.provider_status import ProviderErrorCode


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
        status_codes = []
        if active == "mcp_xhs":
            status_codes.append(ProviderErrorCode.MCP_NOT_CONFIGURED.value)
        return {
            "active_provider": provider.name,
            "available": True,
            "fallback_provider": "manual_snapshot",
            "provider_order": list(PROVIDER_ORDER),
            "is_mock": False,
            "status_codes": status_codes,
            "suggestion": "请配置 MCP 数据源，或手动录入真实公开笔记样本。",
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
        available = bool(settings.embedding_api_key and settings.embedding_provider != "disabled")
        return {
            "active_provider": settings.embedding_provider if available else None,
            "model": settings.embedding_model,
            "available": available,
            "is_mock": False,
        }
