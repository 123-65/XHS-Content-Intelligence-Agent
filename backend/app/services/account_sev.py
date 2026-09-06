from sqlalchemy.orm import Session

from app.models.account import AccountProfile
from app.repositories.account_repo import AccountProfileRepository
from app.schemas.account import AccountProfileCreate, AccountProfileUpdate


class AccountProfileService:
    """账号配置业务服务。"""

    def __init__(self, db: Session):
        """初始化账号配置服务。"""
        self.repo = AccountProfileRepository(db)

    def create_account(self, data: AccountProfileCreate) -> AccountProfile:
        """创建账号配置。"""
        return self.repo.create(data)

    def list_accounts(self) -> list[AccountProfile]:
        """查询账号配置列表。"""
        return self.repo.list_all()

    def get_account(self, account_id: int) -> AccountProfile:
        """查询账号配置详情。"""
        account = self.repo.get_by_id(account_id)
        if not account:
            raise ValueError("账号配置不存在")
        return account

    def update_account(self, account_id: int, data: AccountProfileUpdate) -> AccountProfile:
        """更新账号配置。"""
        account = self.get_account(account_id)
        return self.repo.update(account, data)