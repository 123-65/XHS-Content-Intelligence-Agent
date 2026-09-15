from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class DataSourceConfigStatus(StrEnum):
    """Data source config status."""

    ACTIVE = "ACTIVE"
    DISABLED = "DISABLED"


class DataSourceKeyword(BaseModel):
    """Tracked keyword item."""

    keyword: str = Field(min_length=1, max_length=128)
    enabled: bool = True
    note: str | None = Field(default=None, max_length=512)

    @field_validator("keyword")
    @classmethod
    def strip_keyword(cls, value: str) -> str:
        return value.strip()


class DataSourceCompetitorAccount(BaseModel):
    """Tracked competitor account item."""

    name: str | None = Field(default=None, max_length=128)
    profile_url: str | None = Field(default=None, max_length=1024)
    platform_account_id: str | None = Field(default=None, max_length=128)
    enabled: bool = True
    note: str | None = Field(default=None, max_length=512)

    @field_validator("name", "profile_url", "platform_account_id", mode="before")
    @classmethod
    def strip_optional_text(cls, value: Any) -> Any:
        return value.strip() if isinstance(value, str) else value


class DataSourceConfigUpsert(BaseModel):
    """Create or replace one account/platform data source config."""

    account_id: int = Field(gt=0)
    platform: str = Field(default="xhs", min_length=1, max_length=32)
    status: DataSourceConfigStatus = DataSourceConfigStatus.ACTIVE
    keywords: list[DataSourceKeyword] = Field(default_factory=list)
    competitor_accounts: list[DataSourceCompetitorAccount] = Field(default_factory=list)
    note_urls: list[str] = Field(default_factory=list)
    refresh_policy: dict[str, Any] = Field(default_factory=dict)
    metadata_payload: dict[str, Any] = Field(default_factory=dict)

    @field_validator("platform")
    @classmethod
    def normalize_platform(cls, value: str) -> str:
        return value.strip().lower()

    @field_validator("note_urls")
    @classmethod
    def strip_note_urls(cls, value: list[str]) -> list[str]:
        return [item.strip() for item in value if item and item.strip()]


class DataSourceConfigUpdate(BaseModel):
    """Patch an existing data source config."""

    status: DataSourceConfigStatus | None = None
    keywords: list[DataSourceKeyword] | None = None
    competitor_accounts: list[DataSourceCompetitorAccount] | None = None
    note_urls: list[str] | None = None
    refresh_policy: dict[str, Any] | None = None
    metadata_payload: dict[str, Any] | None = None

    @field_validator("note_urls")
    @classmethod
    def strip_optional_note_urls(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return None
        return [item.strip() for item in value if item and item.strip()]


class DataSourceConfigResponse(BaseModel):
    """Data source config API response."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    account_id: int
    platform: str
    status: str
    keywords: list[dict[str, Any]]
    competitor_accounts: list[dict[str, Any]]
    note_urls: list[str]
    refresh_policy: dict[str, Any]
    metadata_payload: dict[str, Any]
    created_at: datetime
    updated_at: datetime
