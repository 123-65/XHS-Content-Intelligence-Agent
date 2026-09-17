from app.crawler.providers.base import BaseCrawlerProvider
from app.models.crawl_task import CrawlTask
from app.schemas.crawler_collection import (
    CompetitorAccountCreate,
    CompetitorCommentCreate,
    CompetitorNoteCreate,
    CrawlerProviderResult,
)


class ManualSnapshotProvider(BaseCrawlerProvider):
    """用户手动录入真实公开笔记快照 Provider。"""

    name = "manual_snapshot"
    source_type = "MANUAL"
    is_mock = False

    def collect(self, task: CrawlTask) -> CrawlerProviderResult:
        """读取用户手动整理的真实快照。"""
        payload = task.input_payload or {}
        accounts = [self._with_defaults(CompetitorAccountCreate, task.account_id, item) for item in payload.get("accounts", [])]
        notes = [self._with_defaults(CompetitorNoteCreate, task.account_id, item) for item in payload.get("notes", [])]
        comments = [self._with_defaults(CompetitorCommentCreate, task.account_id, item) for item in payload.get("comments", [])]
        if not accounts and not notes and not comments:
            raise ValueError("MANUAL_SNAPSHOT_REQUIRED")
        return CrawlerProviderResult(
            accounts=accounts,
            notes=notes,
            comments=comments,
            provider_name=self.name,
            source_type=self.source_type,
            is_mock=False,
            confidence=0.9,
        )

    def _with_defaults(self, schema_model, account_id: int, item: dict):
        """为人工快照补齐真实来源字段。"""
        return schema_model.model_validate(
            {
                "account_id": account_id,
                "source_type": self.source_type,
                "provider_name": self.name,
                "is_mock": False,
                "confidence": item.get("confidence", 0.9),
                "raw_snapshot": item,
                **item,
            }
        )
