from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


SourceType = Literal["OWN_PUBLIC", "COMPETITOR", "KEYWORD_RESULT", "MANUAL_LINK"]


class XhsNoteUrlParseResult(BaseModel):
    """小红书笔记 URL 解析结果。"""

    note_url: str
    note_id: str | None
    valid: bool
    reason: str | None = None


class XhsNoteSnapshotCreate(BaseModel):
    """创建小红书笔记快照请求。"""

    account_id: int | None = None
    source_type: SourceType = "MANUAL_LINK"
    keyword: str | None = Field(default=None, max_length=128)
    note_url: str = Field(min_length=1, max_length=1024)
    note_id: str | None = Field(default=None, max_length=128)
    author_name: str | None = Field(default=None, max_length=128)
    author_homepage: str | None = Field(default=None, max_length=1024)
    title: str | None = Field(default=None, max_length=512)
    content: str | None = None
    tags: list[str] = Field(default_factory=list)
    like_count: int | None = Field(default=None, ge=0)
    collect_count: int | None = Field(default=None, ge=0)
    comment_count: int | None = Field(default=None, ge=0)
    publish_time: datetime | None = None
    status: str = Field(default="SUCCESS", max_length=32)
    error_message: str | None = None


class XhsNoteSnapshotResponse(BaseModel):
    """小红书笔记快照响应。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    account_id: int | None
    source_type: str
    keyword: str | None
    note_url: str
    note_id: str | None
    author_name: str | None
    author_homepage: str | None
    title: str | None
    content: str | None
    tags: list[str]
    like_count: int | None
    collect_count: int | None
    comment_count: int | None
    publish_time: datetime | None
    crawl_time: datetime
    raw_hash: str | None
    status: str
    error_message: str | None
    created_at: datetime