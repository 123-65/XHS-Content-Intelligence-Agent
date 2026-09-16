from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


XhsUrlCollectRunStatus = Literal["WAITING_CONFIRMATION", "COMPLETED", "PARTIAL_SUCCESS", "FAILED"]
XhsUrlCollectItemStatus = Literal[
    "SUCCESS",
    "PARTIAL_SUCCESS",
    "COLLECT_FAILED",
    "LOGIN_REQUIRED",
    "CAPTCHA_REQUIRED",
    "RATE_LIMITED",
    "UNSUPPORTED_URL",
    "PARSE_FAILED",
]


class XhsUrlCollectRequest(BaseModel):
    account_id: int = Field(gt=0)
    confirmed: bool = False
    urls: list[str] = Field(default_factory=list)
    collect_comments: bool = True
    max_comments: int = Field(default=20, ge=0, le=100)


class XhsUrlCollectAction(BaseModel):
    action: str
    label: str
    enabled: bool = True


class XhsUrlCollectItemResult(BaseModel):
    url: str
    status: XhsUrlCollectItemStatus
    note_id: int | None = None
    xhs_note_snapshot_id: int | None = None
    competitor_account_id: int | None = None
    competitor_note_id: int | None = None
    comment_count_saved: int = 0
    author_name: str | None = None
    title: str | None = None
    like_count: int | None = None
    collect_count: int | None = None
    comment_count: int | None = None
    warnings: list[str] = Field(default_factory=list)
    error_code: str | None = None
    error_message: str | None = None


class XhsUrlCollectResponse(BaseModel):
    status: XhsUrlCollectRunStatus
    account_id: int
    run_id: int | None = None
    total: int = 0
    success_count: int = 0
    failed_count: int = 0
    results: list[XhsUrlCollectItemResult] = Field(default_factory=list)
    next_actions: list[XhsUrlCollectAction] = Field(default_factory=list)
    error_code: str | None = None
    error_message: str | None = None
    created_at: datetime | None = None
    finished_at: datetime | None = None
