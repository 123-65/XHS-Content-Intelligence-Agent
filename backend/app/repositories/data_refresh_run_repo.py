from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.account_data_refresh_run import AccountDataRefreshRun


class DataRefreshRunRepository:
    """账号数据刷新运行记录数据库访问层。"""

    def __init__(self, db: Session):
        """初始化数据库会话。"""
        self.db = db

    def create(self, payload: dict) -> AccountDataRefreshRun:
        """创建刷新运行记录。"""
        run = AccountDataRefreshRun(**payload)
        self.db.add(run)
        self.db.commit()
        self.db.refresh(run)
        return run

    def get(self, run_id: int) -> AccountDataRefreshRun | None:
        """按 ID 查询刷新运行记录。"""
        return self.db.get(AccountDataRefreshRun, run_id)

    def list(self, account_id: int | None = None, limit: int = 20) -> list[AccountDataRefreshRun]:
        """查询最近的刷新运行记录。"""
        stmt = select(AccountDataRefreshRun).order_by(AccountDataRefreshRun.created_at.desc(), AccountDataRefreshRun.id.desc()).limit(limit)
        if account_id is not None:
            stmt = stmt.where(AccountDataRefreshRun.account_id == account_id)
        return list(self.db.execute(stmt).scalars().all())

    def update(self, run: AccountDataRefreshRun, payload: dict) -> AccountDataRefreshRun:
        """更新刷新运行记录。"""
        for field, value in payload.items():
            setattr(run, field, value)
        self.db.commit()
        self.db.refresh(run)
        return run
