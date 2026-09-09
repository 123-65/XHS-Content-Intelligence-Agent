from abc import ABC, abstractmethod

from app.models.crawl_task import CrawlTask
from app.schemas.crawler_collection import CrawlerProviderResult


class BaseCrawlerProvider(ABC):
    """采集 Provider 基础抽象。"""

    name: str

    @abstractmethod
    def collect(self, task: CrawlTask) -> CrawlerProviderResult:
        """执行采集任务并返回标准化结果。"""
        raise NotImplementedError
