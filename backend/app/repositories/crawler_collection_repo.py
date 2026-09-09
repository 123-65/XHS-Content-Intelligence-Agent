from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.account import AccountProfile
from app.models.competitor_account import CompetitorAccount
from app.models.competitor_comment import CompetitorComment
from app.models.competitor_note import CompetitorNote
from app.models.crawl_task import CrawlTask
from app.schemas.crawler_collection import (
    CompetitorAccountCreate,
    CompetitorCommentCreate,
    CompetitorNoteCreate,
    CrawlTaskCreate,
)


class CrawlerCollectionRepository:
    """采集任务与竞品数据数据库访问层。"""

    def __init__(self, db: Session):
        """初始化数据库会话。"""
        self.db = db

    def get_account(self, account_id: int) -> AccountProfile | None:
        """查询账号配置。"""
        return self.db.get(AccountProfile, account_id)

    def create_task(self, data: CrawlTaskCreate) -> CrawlTask:
        """创建采集任务。"""
        task = CrawlTask(**data.model_dump())
        self.db.add(task)
        self.db.commit()
        self.db.refresh(task)
        return task

    def get_task(self, task_id: int) -> CrawlTask | None:
        """根据 ID 查询采集任务。"""
        return self.db.get(CrawlTask, task_id)

    def save_accounts(self, items: list[CompetitorAccountCreate]) -> list[CompetitorAccount]:
        """保存同行账号快照。"""
        accounts = [CompetitorAccount(**item.model_dump()) for item in items]
        self.db.add_all(accounts)
        self.db.flush()
        return accounts

    def save_notes(self, items: list[CompetitorNoteCreate]) -> list[CompetitorNote]:
        """保存竞品笔记快照。"""
        notes = [CompetitorNote(**item.model_dump()) for item in items]
        self.db.add_all(notes)
        self.db.flush()
        return notes

    def save_comments(self, items: list[CompetitorCommentCreate]) -> list[CompetitorComment]:
        """保存竞品评论样本。"""
        comments = [CompetitorComment(**item.model_dump()) for item in items]
        self.db.add_all(comments)
        self.db.flush()
        return comments

    def commit_and_refresh_task(self, task: CrawlTask) -> CrawlTask:
        """提交事务并刷新任务。"""
        self.db.commit()
        self.db.refresh(task)
        return task

    def rollback(self) -> None:
        """回滚当前事务。"""
        self.db.rollback()

    def list_competitor_accounts(self, account_id: int) -> list[CompetitorAccount]:
        """查询同行账号快照。"""
        stmt = select(CompetitorAccount).where(CompetitorAccount.account_id == account_id).order_by(CompetitorAccount.id.desc())
        return list(self.db.execute(stmt).scalars().all())

    def list_competitor_notes(self, account_id: int) -> list[CompetitorNote]:
        """查询竞品笔记快照。"""
        stmt = select(CompetitorNote).where(CompetitorNote.account_id == account_id).order_by(CompetitorNote.id.desc())
        return list(self.db.execute(stmt).scalars().all())
