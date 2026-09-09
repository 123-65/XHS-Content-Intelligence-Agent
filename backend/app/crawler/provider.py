from abc import ABC, abstractmethod

from app.schemas.xhs_note import XhsNoteCrawlResult


class XhsCrawlerProvider(ABC):
    """小红书采集器抽象接口。"""

    @abstractmethod
    def crawl_note(
        self,
        note_url: str,
        source_type: str = "MANUAL_LINK",
        keyword: str | None = None,
    ) -> XhsNoteCrawlResult:
        """采集单篇小红书公开笔记。"""
        raise NotImplementedError