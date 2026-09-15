from typing import Any

from sqlalchemy.orm import Session

from app.models.account import AccountProfile
from app.models.account_data_source_config import AccountDataSourceConfig
from app.repositories.data_source_config_repo import DataSourceConfigRepository
from app.schemas.data_source_config import DataSourceConfigUpdate, DataSourceConfigUpsert


class DataSourceConfigService:
    """Business service for account data source configs."""

    def __init__(self, db: Session):
        self.db = db
        self.repo = DataSourceConfigRepository(db)

    def upsert_config(self, data: DataSourceConfigUpsert) -> AccountDataSourceConfig:
        self._ensure_account(data.account_id)
        normalized = self._normalize_upsert(data)
        existing = self.repo.get_by_account_platform(normalized.account_id, normalized.platform)
        if existing:
            return self.repo.replace(existing, normalized)
        return self.repo.create(normalized)

    def list_configs(self, account_id: int | None = None) -> list[AccountDataSourceConfig]:
        if account_id is not None:
            self._ensure_account(account_id)
        return self.repo.list(account_id=account_id)

    def get_config(self, config_id: int) -> AccountDataSourceConfig:
        config = self.repo.get(config_id)
        if not config:
            raise ValueError("data source config not found")
        return config

    def get_by_account(self, account_id: int, platform: str = "xhs") -> AccountDataSourceConfig:
        self._ensure_account(account_id)
        config = self.repo.get_by_account_platform(account_id, platform.strip().lower())
        if not config:
            raise ValueError("data source config not found")
        return config

    def update_config(self, config_id: int, data: DataSourceConfigUpdate) -> AccountDataSourceConfig:
        config = self.get_config(config_id)
        normalized = self._normalize_update(data)
        return self.repo.update(config, normalized)

    def _ensure_account(self, account_id: int) -> None:
        if not self.db.get(AccountProfile, account_id):
            raise ValueError("account not found")

    def _normalize_upsert(self, data: DataSourceConfigUpsert) -> DataSourceConfigUpsert:
        payload = data.model_dump(mode="json")
        payload["keywords"] = self._dedupe_keywords(payload["keywords"])
        payload["competitor_accounts"] = self._dedupe_competitors(payload["competitor_accounts"])
        payload["note_urls"] = self._dedupe_texts(payload["note_urls"])
        return DataSourceConfigUpsert(**payload)

    def _normalize_update(self, data: DataSourceConfigUpdate) -> DataSourceConfigUpdate:
        payload = data.model_dump(exclude_unset=True, mode="json")
        if "keywords" in payload and payload["keywords"] is not None:
            payload["keywords"] = self._dedupe_keywords(payload["keywords"])
        if "competitor_accounts" in payload and payload["competitor_accounts"] is not None:
            payload["competitor_accounts"] = self._dedupe_competitors(payload["competitor_accounts"])
        if "note_urls" in payload and payload["note_urls"] is not None:
            payload["note_urls"] = self._dedupe_texts(payload["note_urls"])
        return DataSourceConfigUpdate(**payload)

    def _dedupe_keywords(self, items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = []
        seen: set[str] = set()
        for item in items:
            keyword = str(item.get("keyword") or "").strip()
            key = keyword.lower()
            if not keyword or key in seen:
                continue
            copied = dict(item)
            copied["keyword"] = keyword
            result.append(copied)
            seen.add(key)
        return result

    def _dedupe_competitors(self, items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = []
        seen: set[str] = set()
        for item in items:
            copied = {key: value for key, value in item.items() if value not in ("", None)}
            key = self._competitor_key(copied)
            if not key or key in seen:
                continue
            result.append(copied)
            seen.add(key)
        return result

    def _competitor_key(self, item: dict[str, Any]) -> str:
        return str(item.get("platform_account_id") or item.get("profile_url") or item.get("name") or "").strip().lower()

    def _dedupe_texts(self, items: list[str]) -> list[str]:
        result: list[str] = []
        seen: set[str] = set()
        for item in items:
            text = item.strip()
            key = text.lower()
            if not text or key in seen:
                continue
            result.append(text)
            seen.add(key)
        return result
