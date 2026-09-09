from app.core.config import settings
from app.crawler.mock_provider import MockXhsCrawlerProvider
from app.crawler.provider import XhsCrawlerProvider


def get_xhs_crawler_provider() -> XhsCrawlerProvider:
    """根据配置获取小红书采集器。"""
    if settings.xhs_crawler_provider == "mock":
        return MockXhsCrawlerProvider()

    from app.crawler.xhs_public_crawler import XhsPublicCrawler

    return XhsPublicCrawler()