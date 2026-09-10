from app.crawler.providers.manual import ManualProvider
from app.models.crawl_task import CrawlTask
from app.schemas.crawler_collection import CrawlerProviderResult


class ManualSnapshotProvider(ManualProvider):
    """用户手动录入真实公开笔记快照 Provider。"""

    name = "manual_snapshot"
    source_type = "MANUAL"
    is_mock = False

    def collect(self, task: CrawlTask) -> CrawlerProviderResult:
        """读取用户手动整理的真实快照。"""
        result = super().collect(task)
        return result.model_copy(update={"provider_name": self.name, "source_type": "MANUAL", "is_mock": False, "confidence": 0.9})
