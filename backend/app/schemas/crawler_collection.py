from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


CrawlTaskStatus = Literal["PENDING", "RUNNING", "SUCCESS", "FAILED"]
CrawlerProviderName = Literal["readonly_xhs", "mcp_xhs", "manual_snapshot", "seed_sample", "manual"]


class CrawlTaskCreate(BaseModel):
    """创建采集任务请求。"""

    account_id: int
    task_type: str = Field(default="COMPETITOR_SEED", max_length=64)
    provider_name: CrawlerProviderName = "readonly_xhs"
    keyword: str | None = Field(default=None, max_length=128)
    input_payload: dict = Field(default_factory=dict)


class CrawlTaskResponse(BaseModel):
    """采集任务响应。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    account_id: int
    task_type: str
    provider_name: str
    keyword: str | None
    status: str
    result_count: int
    success_count: int
    failed_count: int
    confidence: float
    error_message: str | None
    input_payload: dict
    created_at: datetime
    updated_at: datetime
    started_at: datetime | None
    finished_at: datetime | None


class CompetitorAccountCreate(BaseModel):
    """创建同行账号快照数据。"""

    account_id: int
    platform: str = "xhs"
    platform_account_id: str | None = None
    nickname: str
    homepage_url: str | None = None
    bio: str | None = None
    follower_count: int | None = None
    note_count: int | None = None
    source_type: str = "SEED_SAMPLE"
    provider_name: str = "seed_sample"
    is_mock: bool = True
    confidence: float = Field(default=0.8, ge=0, le=1)
    raw_snapshot: dict = Field(default_factory=dict)


class CompetitorNoteCreate(BaseModel):
    """创建竞品笔记快照数据。"""

    account_id: int
    competitor_account_id: int | None = None
    note_id: str | None = None
    note_url: str | None = None
    author_name: str | None = None
    title: str | None = None
    content: str | None = None
    tags: list[str] = Field(default_factory=list)
    like_count: int | None = None
    collect_count: int | None = None
    comment_count: int | None = None
    source_type: str = "SEED_SAMPLE"
    provider_name: str = "seed_sample"
    is_mock: bool = True
    confidence: float = Field(default=0.8, ge=0, le=1)
    raw_snapshot: dict = Field(default_factory=dict)


class CompetitorCommentCreate(BaseModel):
    """创建竞品评论样本数据。"""

    account_id: int
    competitor_note_id: int | None = None
    comment_id: str | None = None
    user_name: str | None = None
    content: str
    like_count: int | None = None
    source_type: str = "SEED_SAMPLE"
    provider_name: str = "seed_sample"
    is_mock: bool = True
    confidence: float = Field(default=0.8, ge=0, le=1)
    raw_snapshot: dict = Field(default_factory=dict)


class CompetitorAccountResponse(BaseModel):
    """同行账号快照响应。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    account_id: int
    platform: str
    platform_account_id: str | None
    nickname: str
    homepage_url: str | None
    bio: str | None
    follower_count: int | None
    note_count: int | None
    source_type: str
    provider_name: str
    is_mock: bool
    collected_at: datetime
    confidence: float
    raw_snapshot: dict
    created_at: datetime


class CompetitorNoteResponse(BaseModel):
    """竞品笔记快照响应。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    account_id: int
    competitor_account_id: int | None
    note_id: str | None
    note_url: str | None
    author_name: str | None
    title: str | None
    content: str | None
    tags: list[str]
    like_count: int | None
    collect_count: int | None
    comment_count: int | None
    source_type: str
    provider_name: str
    is_mock: bool
    collected_at: datetime
    confidence: float
    raw_snapshot: dict
    created_at: datetime


class CompetitorCommentResponse(BaseModel):
    """竞品评论样本响应。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    account_id: int
    competitor_note_id: int | None
    comment_id: str | None
    user_name: str | None
    content: str
    like_count: int | None
    source_type: str
    provider_name: str
    is_mock: bool
    collected_at: datetime
    confidence: float
    raw_snapshot: dict
    created_at: datetime


class CrawlerProviderResult(BaseModel):
    """Provider 采集结果。"""

    accounts: list[CompetitorAccountCreate] = Field(default_factory=list)
    notes: list[CompetitorNoteCreate] = Field(default_factory=list)
    comments: list[CompetitorCommentCreate] = Field(default_factory=list)
    provider_name: str = "seed_sample"
    source_type: str = "SEED_SAMPLE"
    is_mock: bool = True
    confidence: float = Field(default=0.8, ge=0, le=1)
    error_message: str | None = None
