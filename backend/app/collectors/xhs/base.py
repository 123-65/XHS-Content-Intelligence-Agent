from abc import ABC, abstractmethod
from datetime import datetime

from pydantic import BaseModel, Field, model_validator

from app.collectors.xhs.provider_types import XhsCollectStatus


class XhsCollectedComment(BaseModel):
    content: str
    like_count: int | None = None
    note_id: str | None = None
    author_id: str | None = None
    author_name: str | None = None
    comment_id: str | None = None
    note_url: str | None = None
    created_at: datetime | None = None
    raw_snapshot: dict = Field(default_factory=dict)


XhsTopComment = XhsCollectedComment


class XhsCollectedNote(BaseModel):
    note_url: str | None = None
    source_url: str | None = None
    source_type: str = "MANUAL_RAW_LINK"
    source_provider: str | None = None
    provider_name: str | None = None
    status: str = "SUCCESS"
    note_id: str | None = None
    author_id: str | None = None
    author_name: str | None = None
    author_profile_url: str | None = None
    title: str | None = None
    content: str | None = None
    content_summary: str | None = None
    publish_time: datetime | None = None
    like_count: int | None = None
    collect_count: int | None = None
    comment_count: int | None = None
    share_count: int | None = None
    cover_url: str | None = None
    image_urls: list[str] = Field(default_factory=list)
    image_ocr_texts: list[str] = Field(default_factory=list)
    card_structure: list[dict] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    comments: list[XhsCollectedComment] = Field(default_factory=list)
    top_comments: list[XhsCollectedComment] = Field(default_factory=list)
    raw_payload: dict = Field(default_factory=dict)
    raw_snapshot: dict = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def sync_legacy_fields(self):
        if not self.note_url and self.source_url:
            self.note_url = self.source_url
        if not self.source_url and self.note_url:
            self.source_url = self.note_url
        if not self.comments and self.top_comments:
            self.comments = self.top_comments
        if not self.top_comments and self.comments:
            self.top_comments = self.comments
        if not self.raw_payload and self.raw_snapshot:
            self.raw_payload = self.raw_snapshot
        if not self.raw_snapshot and self.raw_payload:
            self.raw_snapshot = self.raw_payload
        if not self.provider_name and self.source_provider:
            self.provider_name = self.source_provider
        if not self.source_provider and self.provider_name:
            self.source_provider = self.provider_name
        return self


class XhsCollectedAccount(BaseModel):
    account_id: str | None = None
    external_user_id: str | None = None
    profile_url: str | None = None
    nickname: str | None = None
    avatar_url: str | None = None
    bio: str | None = None
    follower_count: int | None = None
    following_count: int | None = None
    liked_count: int | None = None
    recent_notes: list[XhsCollectedNote] = Field(default_factory=list)
    raw_payload: dict = Field(default_factory=dict)
    source_provider: str | None = None
    provider_name: str | None = None
    source_type: str = "MANUAL_RAW_LINK"
    status: str = "SUCCESS"
    warnings: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def sync_account_fields(self):
        if not self.external_user_id and self.account_id:
            self.external_user_id = self.account_id
        if not self.account_id and self.external_user_id:
            self.account_id = self.external_user_id
        if not self.provider_name and self.source_provider:
            self.provider_name = self.source_provider
        if not self.source_provider and self.provider_name:
            self.source_provider = self.provider_name
        return self


class XhsCollectProviderResult(BaseModel):
    status: XhsCollectStatus
    provider_name: str
    source_url: str
    is_mock: bool = False
    error_code: str | None = None
    error_message: str | None = None
    raw_html: str | None = None
    raw_text: str | None = None
    parsed_result: XhsCollectedNote | None = None
    parsed_note: XhsCollectedNote | None = None
    parsed_account: XhsCollectedAccount | None = None
    warnings: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def sync_parsed_note(self):
        if not self.parsed_note and self.parsed_result:
            self.parsed_note = self.parsed_result
        if not self.parsed_result and self.parsed_note:
            self.parsed_result = self.parsed_note
        return self


XhsCollectionResult = XhsCollectProviderResult


class XhsCollectorProvider(ABC):
    provider_name = "base_xhs_collector_provider"

    @abstractmethod
    def collect_note(self, note_url: str, collect_comments: bool = True, max_comments: int = 20) -> XhsCollectionResult:
        """Collect note detail, images, interaction metrics and comments from a user-supplied URL."""

    @abstractmethod
    def collect_account(self, account_id_or_url: str, recent_note_limit: int = 10) -> XhsCollectionResult:
        """Collect account profile and recent public notes from a user-supplied account ID or profile URL."""

    def collect_note_detail(self, url: str, collect_comments: bool, max_comments: int) -> XhsCollectionResult:
        """Backward-compatible alias for older service names."""
        return self.collect_note(url, collect_comments=collect_comments, max_comments=max_comments)

    def collect_account_profile(self, account_id_or_url: str, recent_note_limit: int) -> XhsCollectionResult:
        """Backward-compatible alias for older service names."""
        return self.collect_account(account_id_or_url, recent_note_limit=recent_note_limit)


class XhsUrlCollectProvider(ABC):
    provider_name = "base_xhs_provider"

    @abstractmethod
    def collect(self, url: str, collect_comments: bool = True, max_comments: int = 20) -> XhsCollectProviderResult:
        """Collect one public XHS note URL without login, cookies, or captcha bypass."""
