from app.models.startup_strategy import StartupStrategy
from app.repositories.startup_strategy_repo import StartupStrategyRepository
from app.schemas.startup_strategy import StartupStrategyCreate
from sqlalchemy.orm import Session


class StartupStrategyService:
    """起号策略业务服务。"""

    def __init__(self, db: Session):
        """初始化起号策略服务。"""
        self.repo = StartupStrategyRepository(db)

    def create_strategy(self, data: StartupStrategyCreate) -> StartupStrategy:
        """创建起号策略。"""
        return self.repo.create(data)

    def list_strategies(self, account_id: int) -> list[StartupStrategy]:
        """查询账号起号策略列表。"""
        return self.repo.list_by_account(account_id)
