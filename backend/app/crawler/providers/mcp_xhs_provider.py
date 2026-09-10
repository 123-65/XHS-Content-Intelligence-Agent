from app.crawler.providers.base import BaseCrawlerProvider
from app.models.crawl_task import CrawlTask
from app.schemas.crawler_collection import CrawlerProviderResult
from app.schemas.provider_status import ProviderErrorCode


class MCPXhsProvider(BaseCrawlerProvider):
    """MCP 小红书只读工具 Provider 抽象。"""

    name = "mcp_xhs"

    def collect(self, task: CrawlTask) -> CrawlerProviderResult:
        """MCP 未接入真实数据源前，不生成占位 mock 采集结果。"""
        raise ValueError(ProviderErrorCode.MCP_NOT_CONFIGURED.value)
