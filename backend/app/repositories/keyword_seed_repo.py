from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.account import AccountProfile
from app.models.keyword_seed import KeywordSeed
from app.schemas.keyword_seed import KeywordSeedCreate


class KeywordSeedRepository:
    """关键词种子数据库访问层。"""

    def __init__(self, db: Session):
        """初始化数据库会话。"""
        self.db = db

    def get_account(self, account_id: int) -> AccountProfile | None:
        """查询账号配置。"""
        return self.db.get(AccountProfile, account_id)

    def create_many(self, items: list[KeywordSeedCreate]) -> list[KeywordSeed]:
        """批量创建关键词种子。"""
        seeds = [KeywordSeed(**item.model_dump()) for item in items]
        self.db.add_all(seeds)
        self.db.commit()
        for seed in seeds:
            self.db.refresh(seed)
        return seeds

    def list_by_account(self, account_id: int, category: str | None = None) -> list[KeywordSeed]:
        """查询账号关键词。"""
        filters = [KeywordSeed.account_id == account_id]
        filters.extend([KeywordSeed.category == category] if category else [])
        stmt = select(KeywordSeed).where(*filters).order_by(KeywordSeed.id.desc())
        return list(self.db.execute(stmt).scalars().all())
