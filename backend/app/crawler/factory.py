from app.core.config import settings
from app.crawler.mock_provider import MockXhsCrawlerProvider
from app.crawler.provider import XhsCrawlerProvider
from app.crawler.xhs_public_crawler import XhsPublicCrawler


def get_xhs_crawler_provider() -> XhsCrawlerProvider:
    """获取小红书单条笔记采集器；默认使用真实只读采集器，Mock 必须显式配置。"""
    provider_name = (settings.xhs_crawler_provider or "readonly_xhs").lower()
    if provider_name == "mock":
        return MockXhsCrawlerProvider()
    if provider_name in {"readonly_xhs", "xhs_public"}:
        return XhsPublicCrawler()
    raise ValueError(f"CRAWLER_PROVIDER_UNAVAILABLE: 不支持的小红书采集器 Provider：{provider_name}")