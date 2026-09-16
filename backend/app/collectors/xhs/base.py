from abc import ABC, abstractmethod
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


XhsCollectStatus = Literal[
    "SUCCESS",
    "PARTIAL_SUCCESS",
    "COLLECT_FAILED",
    "LOGIN_REQUIRED",
    "CAPTCHA_REQUIRED",
    "RATE_LIMITED",
    "UNSUPPORTED_URL",
    "PARSE_FAILED",
]


class XhsTopComment(BaseModel):
    content: str
    like_count: int | None = None
    author_name: str | None = None
    comment_id: str | None = None
    raw_snapshot: dict = Field(default_factory=dict)


class XhsCollectedNote(BaseModel):
    source_url: str
    source_type: str = "URL_COLLECT"
    note_id: str | None = None
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
    tags: list[str] = Field(default_factory=list)
    top_comments: list[XhsTopComment] = Field(default_factory=list)
    raw_snapshot: dict = Field(default_factory=dict)


class XhsCollectProviderResult(BaseModel):
    status: XhsCollectStatus
    provider_name: str
    source_url: str
    error_code: str | None = None
    error_message: str | None = None
    raw_html: str | None = None
    raw_text: str | None = None
    parsed_result: XhsCollectedNote | None = None
    warnings: list[str] = Field(default_factory=list)


class XhsUrlCollectProvider(ABC):
    provider_name = "base_xhs_provider"

    @abstractmethod
    def collect(self, url: str, collect_comments: bool = True, max_comments: int = 20) -> XhsCollectProviderResult:
        """Collect one public XHS note URL without login, cookies, or captcha bypass."""
