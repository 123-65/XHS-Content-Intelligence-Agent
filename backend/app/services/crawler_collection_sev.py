"""Deprecated compatibility service for the old crawler-provider chain.

New Agents, Workflows, and Tools must use ``XhsCollectorService`` instead.
The registered legacy APIs remain temporarily available for external-consumer
compatibility and must not become fallback paths for the canonical MCP owner.
"""

from datetime import datetime

from sqlalchemy.orm import Session

from app.crawler.providers.factory import get_provider_chain
from app.models.competitor_account import CompetitorAccount
from app.models.competitor_note import CompetitorNote
from app.models.crawl_task import CrawlTask
from app.repositories.crawler_collection_repo import CrawlerCollectionRepository
from app.schemas.crawler_collection import CrawlTaskCreate


class CrawlerCollectionService:
    """DEPRECATED/LEGACY_COMPAT: old crawler task and provider owner."""

    def __init__(self, db: Session):
        """初始化采集任务服务。"""
        self.repo = CrawlerCollectionRepository(db)

    def create_task(self, data: CrawlTaskCreate) -> CrawlTask:
        """创建采集任务。"""
        self._ensure_account_exists(data.account_id)
        return self.repo.create_task(data)

    def run_task(self, task_id: int) -> CrawlTask:
        """执行采集任务并保存标准化竞品数据。"""
        task = self.get_task(task_id)
        task.status = "RUNNING"
        task.started_at = datetime.now()
        self.repo.commit_and_refresh_task(task)

        try:
            result = self._collect_with_fallback(task)
            saved_accounts = self.repo.save_accounts(result.accounts)
            note_items = self._bind_first_account(result.notes, saved_accounts)
            saved_notes = self.repo.save_notes(note_items)
            comment_items = self._bind_comments_to_notes(result.comments, saved_notes)
            saved_comments = self.repo.save_comments(comment_items)
            task.result_count = len(saved_accounts) + len(saved_notes) + len(saved_comments)
            task.success_count = task.result_count
            task.failed_count = 0
            task.confidence = result.confidence
            task.error_message = result.error_message
            task.provider_name = result.provider_name
            task.status = "SUCCESS"
        except Exception as exc:
            self.repo.rollback()
            task = self.get_task(task_id)
            task.status = "FAILED"
            task.failed_count = 1
            task.error_message = str(exc)
        finally:
            task.finished_at = datetime.now()

        return self.repo.commit_and_refresh_task(task)

    def _collect_with_fallback(self, task: CrawlTask):
        """按灰度 Provider 链采集，失败后自动降级。"""
        errors = []
        for provider in get_provider_chain(task.provider_name):
            try:
                result = provider.collect(task)
                return self._stamp_provider_metadata(result)
            except Exception as exc:
                errors.append({"provider_name": provider.name, "error": str(exc)})
        raise ValueError(f"所有采集 Provider 均不可用：{errors}")

    def _stamp_provider_metadata(self, result):
        """确保所有采集结果都带 Provider 元数据。"""
        for collection in (result.accounts, result.notes, result.comments):
            for item in collection:
                item.provider_name = result.provider_name
                item.source_type = result.source_type
                item.is_mock = result.is_mock
                item.raw_snapshot = {"provider_name": item.provider_name, "is_mock": item.is_mock, **(item.raw_snapshot or {})}
        return result

    def get_task(self, task_id: int) -> CrawlTask:
        """查询采集任务详情。"""
        task = self.repo.get_task(task_id)
        if task:
            return task
        raise ValueError("采集任务不存在")

    def list_competitor_accounts(self, account_id: int) -> list[CompetitorAccount]:
        """查询同行账号快照列表。"""
        self._ensure_account_exists(account_id)
        return self.repo.list_competitor_accounts(account_id)

    def list_competitor_notes(self, account_id: int) -> list[CompetitorNote]:
        """查询竞品笔记快照列表。"""
        self._ensure_account_exists(account_id)
        return self.repo.list_competitor_notes(account_id)

    def _ensure_account_exists(self, account_id: int) -> None:
        """校验账号是否存在。"""
        if self.repo.get_account(account_id):
            return
        raise ValueError("账号配置不存在")

    def _bind_first_account(self, notes, accounts):
        """将未指定账号的笔记绑定到本次保存的第一个同行账号。"""
        first_account_id = accounts[0].id if accounts else None
        for note in notes:
            note.competitor_account_id = note.competitor_account_id or first_account_id
        return notes

    def _bind_comments_to_notes(self, comments, notes):
        """将未指定笔记的评论绑定到本次保存的第一篇笔记。"""
        first_note_id = notes[0].id if notes else None
        for comment in comments:
            comment.competitor_note_id = comment.competitor_note_id or first_note_id
        return comments
