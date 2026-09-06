from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.account import AccountProfile
from app.schemas.account import AccountProfileCreate, AccountProfileUpdate


class AccountProfileRepository:
    """账号配置数据库访问层。"""

    def __init__(self, db: Session):
        """初始化数据库会话。"""
        self.db = db

    def create(self, data: AccountProfileCreate) -> AccountProfile:
        """创建账号配置。"""
        account = AccountProfile(**data.model_dump())
        self.db.add(account)
        self.db.commit()
        self.db.refresh(account)
        return account

    def get_by_id(self, account_id: int) -> AccountProfile | None:
        """根据 ID 查询账号配置。"""
        return self.db.get(AccountProfile, account_id)

    def list_all(self) -> list[AccountProfile]:
        """查询全部账号配置。"""
        stmt = select(AccountProfile).order_by(AccountProfile.id.desc())
        return list(self.db.execute(stmt).scalars().all())

    def update(self, account: AccountProfile, data: AccountProfileUpdate) -> AccountProfile:
        """更新账号配置。"""
        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(account, field, value)
        self.db.commit()
        self.db.refresh(account)
        return account