from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.startup_strategy import StartupStrategy
from app.schemas.startup_strategy import StartupStrategyCreate


class StartupStrategyRepository:
    """起号策略数据库访问层。"""

    def __init__(self, db: Session):
        """初始化数据库会话。"""
        self.db = db

    def create(self, data: StartupStrategyCreate) -> StartupStrategy:
        """创建起号策略。"""
        strategy = StartupStrategy(**data.model_dump())
        self.db.add(strategy)
        self.db.commit()
        self.db.refresh(strategy)
        return strategy

    def list_by_account(self, account_id: int) -> list[StartupStrategy]:
        """查询账号起号策略列表。"""
        stmt = select(StartupStrategy).where(StartupStrategy.account_id == account_id).order_by(StartupStrategy.id.desc())
        return list(self.db.execute(stmt).scalars().all())
