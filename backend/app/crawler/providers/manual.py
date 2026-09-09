from app.crawler.providers.base import BaseCrawlerProvider
from app.models.crawl_task import CrawlTask
from app.schemas.crawler_collection import (
    CompetitorAccountCreate,
    CompetitorCommentCreate,
    CompetitorNoteCreate,
    CrawlerProviderResult,
)


class ManualProvider(BaseCrawlerProvider):
    """人工录入 Provider，用于导入用户手动整理的数据。"""

    name = "manual"
    source_type = "MANUAL"
    is_mock = False

    def collect(self, task: CrawlTask) -> CrawlerProviderResult:
        """从任务输入中读取人工整理的竞品数据。"""
        payload = task.input_payload or {}
        accounts = [self._with_defaults(CompetitorAccountCreate, task.account_id, item) for item in payload.get("accounts", [])]
        notes = [self._with_defaults(CompetitorNoteCreate, task.account_id, item) for item in payload.get("notes", [])]
        comments = [self._with_defaults(CompetitorCommentCreate, task.account_id, item) for item in payload.get("comments", [])]
        return CrawlerProviderResult(accounts=accounts, notes=notes, comments=comments, provider_name=self.name, source_type=self.source_type, is_mock=self.is_mock, confidence=0.9)

    def _with_defaults(self, schema_model, account_id: int, item: dict):
        """为人工数据补齐标准来源字段。"""
        data = {
            "account_id": account_id,
            "source_type": self.source_type,
            "provider_name": self.name,
            "is_mock": self.is_mock,
            "confidence": item.get("confidence", 0.9),
            "raw_snapshot": item,
            **item,
        }
        return schema_model.model_validate(data)
