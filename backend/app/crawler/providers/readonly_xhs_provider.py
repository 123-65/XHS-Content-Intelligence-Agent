from app.crawler.providers.base import BaseCrawlerProvider
from app.models.crawl_task import CrawlTask
from app.schemas.crawler_collection import CompetitorAccountCreate, CompetitorCommentCreate, CompetitorNoteCreate, CrawlerProviderResult


class ReadOnlyXhsProvider(BaseCrawlerProvider):
    """只读小红书公开数据 Provider 灰度实现。"""

    name = "readonly_xhs"

    def collect(self, task: CrawlTask) -> CrawlerProviderResult:
        """从用户提供的公开快照中读取数据，不登录、不互动、不绕过风控。"""
        payload = task.input_payload or {}
        if not payload.get("public_snapshot") and not payload.get("notes"):
            raise ValueError("READONLY_XHS_NO_PUBLIC_SNAPSHOT")
        snapshot = payload.get("public_snapshot", payload)
        notes = [self._note(task, item) for item in snapshot.get("notes", payload.get("notes", []))]
        comments = [self._comment(task, item) for item in snapshot.get("comments", payload.get("comments", []))]
        accounts = [self._account(task, item) for item in snapshot.get("accounts", payload.get("accounts", []))]
        return CrawlerProviderResult(accounts=accounts, notes=notes, comments=comments, provider_name=self.name, source_type="XHS_PUBLIC_READONLY", is_mock=False, confidence=0.92)

    def _account(self, task: CrawlTask, item: dict) -> CompetitorAccountCreate:
        """构造只读账号快照。"""
        return CompetitorAccountCreate.model_validate({"account_id": task.account_id, "source_type": "XHS_PUBLIC_READONLY", "provider_name": self.name, "is_mock": False, "confidence": item.get("confidence", 0.92), "raw_snapshot": item, **item})

    def _note(self, task: CrawlTask, item: dict) -> CompetitorNoteCreate:
        """构造只读笔记快照。"""
        return CompetitorNoteCreate.model_validate({"account_id": task.account_id, "source_type": "XHS_PUBLIC_READONLY", "provider_name": self.name, "is_mock": False, "confidence": item.get("confidence", 0.92), "raw_snapshot": item, **item})

    def _comment(self, task: CrawlTask, item: dict) -> CompetitorCommentCreate:
        """构造只读评论快照。"""
        return CompetitorCommentCreate.model_validate({"account_id": task.account_id, "source_type": "XHS_PUBLIC_READONLY", "provider_name": self.name, "is_mock": False, "confidence": item.get("confidence", 0.9), "raw_snapshot": item, **item})
