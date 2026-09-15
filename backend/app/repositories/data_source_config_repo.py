from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.account_data_source_config import AccountDataSourceConfig
from app.schemas.data_source_config import DataSourceConfigUpdate, DataSourceConfigUpsert


class DataSourceConfigRepository:
    """Database access for account data source configs."""

    def __init__(self, db: Session):
        self.db = db

    def create(self, data: DataSourceConfigUpsert) -> AccountDataSourceConfig:
        config = AccountDataSourceConfig(**data.model_dump(mode="json"))
        self.db.add(config)
        self.db.commit()
        self.db.refresh(config)
        return config

    def get(self, config_id: int) -> AccountDataSourceConfig | None:
        return self.db.get(AccountDataSourceConfig, config_id)

    def get_by_account_platform(self, account_id: int, platform: str = "xhs") -> AccountDataSourceConfig | None:
        stmt = select(AccountDataSourceConfig).where(
            AccountDataSourceConfig.account_id == account_id,
            AccountDataSourceConfig.platform == platform,
        )
        return self.db.execute(stmt).scalar_one_or_none()

    def list(self, account_id: int | None = None) -> list[AccountDataSourceConfig]:
        stmt = select(AccountDataSourceConfig).order_by(AccountDataSourceConfig.updated_at.desc(), AccountDataSourceConfig.id.desc())
        if account_id is not None:
            stmt = stmt.where(AccountDataSourceConfig.account_id == account_id)
        return list(self.db.execute(stmt).scalars().all())

    def update(self, config: AccountDataSourceConfig, data: DataSourceConfigUpdate) -> AccountDataSourceConfig:
        payload = data.model_dump(exclude_unset=True, mode="json")
        for field, value in payload.items():
            setattr(config, field, value)
        self.db.commit()
        self.db.refresh(config)
        return config

    def replace(self, config: AccountDataSourceConfig, data: DataSourceConfigUpsert) -> AccountDataSourceConfig:
        payload = data.model_dump(mode="json")
        for field, value in payload.items():
            setattr(config, field, value)
        self.db.commit()
        self.db.refresh(config)
        return config
