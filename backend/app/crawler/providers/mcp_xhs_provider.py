from app.crawler.providers.base import BaseCrawlerProvider
from app.crawler.providers.readonly_xhs_provider import ReadOnlyXhsProvider
from app.models.crawl_task import CrawlTask
from app.schemas.crawler_collection import CrawlerProviderResult
from types import SimpleNamespace


class MCPXhsProvider(BaseCrawlerProvider):
    """MCP 小红书只读工具 Provider 抽象。"""

    name = "mcp_xhs"

    def collect(self, task: CrawlTask) -> CrawlerProviderResult:
        """第一版复用公开快照做 Mock MCP 适配。"""
        payload = task.input_payload or {}
        if not payload.get("mcp_snapshot"):
            raise ValueError("MCP_XHS_NOT_CONFIGURED")
        proxy_task = SimpleNamespace(id=task.id, account_id=task.account_id, keyword=task.keyword, input_payload={"public_snapshot": payload["mcp_snapshot"]})
        result = ReadOnlyXhsProvider().collect(proxy_task)
        return result.model_copy(update={"provider_name": self.name, "source_type": "MCP_XHS_READONLY", "is_mock": True, "confidence": min(result.confidence, 0.75)})
