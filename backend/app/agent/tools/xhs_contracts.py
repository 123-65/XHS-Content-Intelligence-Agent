from datetime import datetime
from enum import StrEnum
from urllib.parse import urlparse

from pydantic import Field, model_validator

from app.agent.schemas.evidence import EvidenceRef
from app.agent.tools.query_contracts import QueryContract


class CollectionAuthorizationSource(StrEnum):
    """公开采集输入 URL 的可信授权来源。"""

    USER_PROVIDED = "USER_PROVIDED"
    BOUND_PUBLISHED_NOTE = "BOUND_PUBLISHED_NOTE"


class NoteCollectionPurpose(StrEnum):
    """笔记采集允许的业务目的。"""

    RESEARCH_INPUT = "RESEARCH_INPUT"
    REFRESH_BOUND_PUBLISHED_NOTE = "REFRESH_BOUND_PUBLISHED_NOTE"


class AccountCollectionPurpose(StrEnum):
    """账号 Profile 采集允许的业务目的。"""

    RESEARCH_INPUT = "RESEARCH_INPUT"


class CollectionAccessScope(QueryContract):
    """由可信 Runtime 或 Context 注入的公开采集授权范围。"""

    model_config = QueryContract.model_config | {"frozen": True}

    workspace_account_ref: int = Field(gt=0)
    authorization_source: CollectionAuthorizationSource
    allowed_note_urls: tuple[str, ...] = ()
    allowed_profile_urls: tuple[str, ...] = ()
    published_note_ref: int | None = Field(default=None, gt=0)

    @model_validator(mode="after")
    def normalize_allowed_urls(self):
        """清理可信 URL 范围并拒绝错误资源类型。"""
        note_urls = tuple(_deduplicate_urls(list(self.allowed_note_urls)))
        profile_urls = tuple(_deduplicate_urls(list(self.allowed_profile_urls)))
        if any(not _is_xhs_note_url(url) for url in note_urls):
            raise ValueError("allowed_note_urls 包含非小红书 Note URL")
        if any(not _is_xhs_profile_url(url) for url in profile_urls):
            raise ValueError("allowed_profile_urls 包含非小红书 Profile URL")
        object.__setattr__(self, "allowed_note_urls", note_urls)
        object.__setattr__(self, "allowed_profile_urls", profile_urls)
        return self


class CollectXhsNotesInput(QueryContract):
    """采集用户授权公开 Note URL 的输入合同。"""

    account_ref: int = Field(gt=0)
    note_urls: list[str] = Field(min_length=1, max_length=20)
    include_comments: bool = True
    max_comments: int = Field(default=20, ge=0, le=100)
    collection_purpose: NoteCollectionPurpose

    @model_validator(mode="after")
    def validate_and_deduplicate_urls(self):
        """校验 Note URL 资源类型、授权语义并按原顺序去重。"""
        normalized = _deduplicate_urls(self.note_urls)
        if any(not _is_xhs_note_url(url) for url in normalized):
            raise ValueError("note_urls 只能包含公开小红书 Note URL")
        self.note_urls = normalized
        return self


class FailedCollectionItem(QueryContract):
    """批量采集中显式保留的失败项。"""

    source_url: str
    error_code: str
    safe_message: str | None = None


class CollectedNoteResult(QueryContract):
    """成功采集并持久化的内部 Note 与 Evidence 引用。"""

    source_url: str
    note_ref: int
    evidence_refs: list[EvidenceRef]
    collected_at: datetime
    comments_collected: int
    authorized_by: CollectionAuthorizationSource
    collection_purpose: NoteCollectionPurpose
    published_note_ref: int | None = None
    warnings: list[str] = Field(default_factory=list)


class CollectXhsNotesResult(QueryContract):
    """支持 Partial Success 的批量 Note 采集结果。"""

    requested_count: int
    collected_count: int
    failed_count: int
    items: list[CollectedNoteResult]
    failed_items: list[FailedCollectionItem]
    warnings: list[str] = Field(default_factory=list)


class CollectXhsAccountsInput(QueryContract):
    """采集用户明确提供的公开 Profile URL 输入合同。"""

    workspace_account_ref: int = Field(gt=0)
    profile_urls: list[str] = Field(min_length=1, max_length=20)
    collection_purpose: AccountCollectionPurpose = AccountCollectionPurpose.RESEARCH_INPUT

    @model_validator(mode="after")
    def validate_and_deduplicate_urls(self):
        """校验 Profile URL 类型并按原顺序去重。"""
        normalized = _deduplicate_urls(self.profile_urls)
        if any(not _is_xhs_profile_url(url) for url in normalized):
            raise ValueError("profile_urls 只能包含公开小红书 Profile URL")
        self.profile_urls = normalized
        return self


class CollectedAccountResult(QueryContract):
    """成功采集并持久化的内部账号及 Evidence 引用。"""

    source_url: str
    account_ref: int
    external_account_ref: str
    evidence_refs: list[EvidenceRef]
    attached_note_refs: list[int] = Field(default_factory=list)
    collected_at: datetime
    authorized_by: CollectionAuthorizationSource
    collection_purpose: AccountCollectionPurpose
    warnings: list[str] = Field(default_factory=list)


class CollectXhsAccountsResult(QueryContract):
    """支持 Partial Success 的批量 Profile 采集结果。"""

    requested_count: int
    collected_count: int
    failed_count: int
    items: list[CollectedAccountResult]
    failed_items: list[FailedCollectionItem]
    warnings: list[str] = Field(default_factory=list)


def _deduplicate_urls(values: list[str]) -> list[str]:
    """清理 URL 两侧空白并保持首次出现顺序去重。"""
    return list(dict.fromkeys(value.strip() for value in values if value and value.strip()))


def _is_xhs_note_url(value: str) -> bool:
    """判断 URL 是否为允许的小红书公开 Note 资源。"""
    parsed = urlparse(value)
    host = (parsed.hostname or "").lower()
    if parsed.scheme not in {"http", "https"}:
        return False
    if host in {"xhslink.com", "www.xhslink.com"}:
        return bool(parsed.path.strip("/"))
    if host == "xiaohongshu.com" or host.endswith(".xiaohongshu.com"):
        return parsed.path.startswith(("/explore/", "/discovery/item/"))
    return False


def _is_xhs_profile_url(value: str) -> bool:
    """判断 URL 是否为明确的小红书公开 Profile 资源。"""
    parsed = urlparse(value)
    host = (parsed.hostname or "").lower()
    return parsed.scheme in {"http", "https"} and (host == "xiaohongshu.com" or host.endswith(".xiaohongshu.com")) and parsed.path.startswith("/user/profile/")
