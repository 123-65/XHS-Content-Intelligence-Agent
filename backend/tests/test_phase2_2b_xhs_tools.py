from pathlib import Path

import pytest
from pydantic import ValidationError

from app.agent.schemas.evidence import EvidenceType
from app.agent.tools.definitions import ToolEffect, ToolName
from app.agent.tools.implementation_registry import TOOL_HANDLER_REGISTRY
from app.agent.tools.registry import TOOL_REGISTRY
from app.agent.tools.xhs_contracts import (
    AccountCollectionPurpose,
    CollectionAccessScope,
    CollectionAuthorizationSource,
    CollectXhsAccountsInput,
    CollectXhsNotesInput,
    NoteCollectionPurpose,
)
from app.agent.tools.xhs_tools import CollectXhsAccountsTool, CollectXhsNotesTool


AGENT_ROOT = Path(__file__).resolve().parents[1] / "app" / "agent"
NOTE_1 = "https://www.xiaohongshu.com/explore/note-1"
NOTE_2 = "https://www.xiaohongshu.com/explore/note-2"
NOTE_BAD = "https://www.xiaohongshu.com/explore/bad"
PROFILE_1 = "https://www.xiaohongshu.com/user/profile/user-1"
PROFILE_2 = "https://www.xiaohongshu.com/user/profile/user-2"
PROFILE_BAD = "https://www.xiaohongshu.com/user/profile/bad"


class FakeCollector:
    """模拟唯一 Canonical XHS Collector 的批量摘要。"""

    def __init__(self, fail_all: bool = False, raise_provider: bool = False):
        """配置全部失败或 Provider 异常场景。"""
        self.fail_all = fail_all
        self.raise_provider = raise_provider
        self.note_calls = []
        self.account_calls = []

    def collect_notes(self, account_id, note_urls, *, collect_comments, max_comments, enable_ocr):
        """返回与 XhsCollectorService 相同结构的 Note 批量摘要。"""
        self.note_calls.append({"account_id": account_id, "urls": note_urls, "collect_comments": collect_comments, "max_comments": max_comments, "enable_ocr": enable_ocr})
        if self.raise_provider:
            raise RuntimeError("provider unavailable")
        items = [self._note_item(url, index) for index, url in enumerate(note_urls, start=1)]
        return self._summary("COLLECT_XHS_NOTES", items)

    def collect_accounts(self, account_id, profile_urls, *, recent_note_limit):
        """返回与 XhsCollectorService 相同结构的 Profile 批量摘要。"""
        self.account_calls.append({"account_id": account_id, "urls": profile_urls, "recent_note_limit": recent_note_limit})
        if self.raise_provider:
            raise RuntimeError("provider unavailable")
        items = [self._account_item(url, index) for index, url in enumerate(profile_urls, start=1)]
        return self._summary("COLLECT_XHS_ACCOUNTS", items)

    def _note_item(self, url, index):
        """构造单个 Note 采集结果。"""
        failed = self.fail_all or url == NOTE_BAD
        return {
            "input_value": url,
            "status": "PROVIDER_TIMEOUT" if failed else "SUCCESS",
            "error_code": "PROVIDER_TIMEOUT" if failed else None,
            "error_message": "公开数据源超时" if failed else None,
            "warnings": [],
            "ids": {} if failed else {"competitor_account_id": 300 + index, "competitor_note_id": 100 + index},
            "data_count": {} if failed else {"comments_saved": 3},
        }

    def _account_item(self, url, index):
        """构造单个 Profile 采集结果。"""
        failed = self.fail_all or url == PROFILE_BAD
        return {
            "input_value": url,
            "status": "PROVIDER_TIMEOUT" if failed else "SUCCESS",
            "error_code": "PROVIDER_TIMEOUT" if failed else None,
            "error_message": "公开数据源超时" if failed else None,
            "warnings": [],
            "ids": {} if failed else {"competitor_account_id": 200 + index, "competitor_note_ids": [400 + index]},
            "data_count": {} if failed else {"accounts_saved": 1, "recent_notes_saved": 1},
        }

    def _summary(self, action, items):
        """汇总批量结果并显式区分成功、部分成功和全部失败。"""
        success_count = sum(item["status"] == "SUCCESS" for item in items)
        errors = [{"input": item["input_value"], "error_code": item["error_code"], "error_message": item["error_message"]} for item in items if item["error_code"]]
        return {
            "action": action,
            "status": "SUCCESS" if success_count == len(items) else "PARTIAL_SUCCESS" if success_count else "FAILED",
            "success_count": success_count,
            "failed_count": len(items) - success_count,
            "items": items,
            "warnings": [],
            "errors": errors,
            "error_code": errors[0]["error_code"] if errors else None,
        }


def _note_input(urls):
    """构造用户授权的 Research Note 采集输入。"""
    return CollectXhsNotesInput(
        account_ref=7,
        note_urls=urls,
        include_comments=True,
        max_comments=20,
        collection_purpose=NoteCollectionPurpose.RESEARCH_INPUT,
    )


def _account_input(urls):
    """构造用户授权的 Profile 采集输入。"""
    return CollectXhsAccountsInput(
        workspace_account_ref=7,
        profile_urls=urls,
        collection_purpose=AccountCollectionPurpose.RESEARCH_INPUT,
    )


def _note_scope(urls, source=CollectionAuthorizationSource.USER_PROVIDED, published_note_ref=None):
    """构造由可信上游注入的 Note URL 授权范围。"""
    return CollectionAccessScope(
        workspace_account_ref=7,
        authorization_source=source,
        allowed_note_urls=tuple(urls),
        published_note_ref=published_note_ref,
    )


def _profile_scope(urls, source=CollectionAuthorizationSource.USER_PROVIDED):
    """构造由可信上游注入的 Profile URL 授权范围。"""
    return CollectionAccessScope(
        workspace_account_ref=7,
        authorization_source=source,
        allowed_profile_urls=tuple(urls),
    )


def test_collect_single_and_batch_notes_with_deduplication_and_comment_limit():
    """验证单条、批量、URL 去重和评论硬上限合同。"""
    collector = FakeCollector()
    tool = CollectXhsNotesTool(collector=collector, access_scope=_note_scope([NOTE_1, NOTE_2]))
    single = tool.execute(_note_input([NOTE_1]))
    assert single.success is True
    assert [ref.type for ref in single.data.items[0].evidence_refs] == [EvidenceType.ACCOUNT, EvidenceType.NOTE]
    assert single.data.items[0].comments_collected == 3

    batch_input = _note_input([NOTE_1, NOTE_1, NOTE_2])
    batch = tool.execute(batch_input)
    assert batch.data.requested_count == 2
    assert batch.data.collected_count == 2
    assert collector.note_calls[-1]["urls"] == [NOTE_1, NOTE_2]
    assert collector.note_calls[-1]["max_comments"] == 20
    with pytest.raises(ValidationError):
        CollectXhsNotesInput(
            account_ref=7,
            note_urls=[NOTE_1],
            max_comments=101,
            collection_purpose=NoteCollectionPurpose.RESEARCH_INPUT,
        )


def test_collect_notes_partial_all_failed_and_provider_exception():
    """验证 Note 批量部分成功保留结果，全部失败不制造 Fake Success。"""
    partial = CollectXhsNotesTool(collector=FakeCollector(), access_scope=_note_scope([NOTE_1, NOTE_BAD])).execute(_note_input([NOTE_1, NOTE_BAD]))
    assert partial.success is True
    assert partial.data.collected_count == 1
    assert partial.data.failed_count == 1
    assert partial.data.items
    assert partial.data.failed_items[0].error_code == "PROVIDER_TIMEOUT"
    assert "PARTIAL_XHS_COLLECTION" in partial.warnings

    failed = CollectXhsNotesTool(collector=FakeCollector(fail_all=True), access_scope=_note_scope([NOTE_1, NOTE_2])).execute(_note_input([NOTE_1, NOTE_2]))
    assert failed.success is False
    assert failed.data is None
    assert failed.error.code == "PROVIDER_TIMEOUT"
    provider_error = CollectXhsNotesTool(collector=FakeCollector(raise_provider=True), access_scope=_note_scope([NOTE_1])).execute(_note_input([NOTE_1]))
    assert provider_error.success is False
    assert provider_error.error.code == "PROVIDER_ERROR"


def test_note_url_and_caller_self_authorization_are_rejected():
    """验证非法 Note URL 以及调用者自报授权字段均被合同拒绝。"""
    with pytest.raises(ValidationError):
        _note_input(["https://example.com/note/1"])
    with pytest.raises(ValidationError):
        CollectXhsNotesInput(
            account_ref=7,
            note_urls=[NOTE_1],
            collection_purpose=NoteCollectionPurpose.RESEARCH_INPUT,
            authorized_by=CollectionAuthorizationSource.USER_PROVIDED,
        )


def test_note_collection_denies_missing_scope_and_urls_outside_allowlist():
    """验证无可信 Scope 或请求集合并非 allowlist 子集时 Collector 零调用。"""
    collector = FakeCollector()
    without_scope = CollectXhsNotesTool(collector=collector).execute(_note_input([NOTE_1]))
    assert without_scope.error.code == "PERMISSION_ERROR"
    outside_scope = CollectXhsNotesTool(collector=collector, access_scope=_note_scope([NOTE_1])).execute(_note_input([NOTE_1, NOTE_2]))
    assert outside_scope.error.code == "PERMISSION_ERROR"
    assert collector.note_calls == []


def test_published_note_refresh_requires_matching_bound_scope():
    """验证发布后刷新仅接受匹配 URL 的 BOUND_PUBLISHED_NOTE Scope。"""
    collector = FakeCollector()
    request = CollectXhsNotesInput(account_ref=7, note_urls=[NOTE_1], collection_purpose=NoteCollectionPurpose.REFRESH_BOUND_PUBLISHED_NOTE)
    class FakeRefreshService:
        def refresh(self, account_ref, published_note_ref, note_url, *, include_comments, max_comments):
            return collector.collect_notes(account_ref, [note_url], collect_comments=include_comments, max_comments=max_comments, enable_ocr=True)

    valid_tool = CollectXhsNotesTool(
        collector=collector,
        access_scope=_note_scope([NOTE_1], CollectionAuthorizationSource.BOUND_PUBLISHED_NOTE, published_note_ref=31),
        refresh_service=FakeRefreshService(),
    )
    valid = valid_tool.execute(request)
    assert valid.success is True
    assert valid.data.items[0].published_note_ref == 31

    user_scope = CollectXhsNotesTool(collector=collector, access_scope=_note_scope([NOTE_1])).execute(request)
    mismatched_url = CollectXhsNotesTool(
        collector=collector,
        access_scope=_note_scope([NOTE_2], CollectionAuthorizationSource.BOUND_PUBLISHED_NOTE, published_note_ref=31),
    ).execute(request)
    assert user_scope.error.code == "PERMISSION_ERROR"
    assert mismatched_url.error.code == "PERMISSION_ERROR"
    assert len(collector.note_calls) == 1


def test_collect_accounts_preserves_user_profile_recent_note_evidence_without_detail_fanout():
    """验证 Profile 批量语义及 user_profile 同次返回的 recent-note Evidence。"""
    collector = FakeCollector()
    tool = CollectXhsAccountsTool(collector=collector, access_scope=_profile_scope([PROFILE_1, PROFILE_2, PROFILE_BAD]))
    success = tool.execute(_account_input([PROFILE_1, PROFILE_2]))
    assert success.success is True
    assert success.data.collected_count == 2
    assert success.data.items[0].evidence_refs[0].type == EvidenceType.ACCOUNT
    assert success.data.items[0].evidence_refs[1].type == EvidenceType.NOTE
    assert success.data.items[0].attached_note_refs == [401]
    assert collector.account_calls[-1]["recent_note_limit"] == 10

    partial = tool.execute(_account_input([PROFILE_1, PROFILE_BAD]))
    assert partial.success is True
    assert partial.data.collected_count == 1
    assert partial.data.failed_count == 1
    assert "PARTIAL_XHS_COLLECTION" in partial.warnings

    failed = CollectXhsAccountsTool(collector=FakeCollector(fail_all=True), access_scope=_profile_scope([PROFILE_1])).execute(_account_input([PROFILE_1]))
    assert failed.success is False
    assert failed.data is None
    assert failed.error.code == "PROVIDER_TIMEOUT"
    provider_error = CollectXhsAccountsTool(collector=FakeCollector(raise_provider=True), access_scope=_profile_scope([PROFILE_1])).execute(_account_input([PROFILE_1]))
    assert provider_error.error.code == "PROVIDER_ERROR"


def test_profile_url_and_caller_self_authorization_are_rejected():
    """验证 Profile Input 不接受错误 URL 或调用者自报授权字段。"""
    with pytest.raises(ValidationError):
        _account_input([NOTE_1])
    with pytest.raises(ValidationError):
        _account_input(["https://example.com/user/profile/1"])
    with pytest.raises(ValidationError):
        CollectXhsAccountsInput(
            workspace_account_ref=7,
            profile_urls=[PROFILE_1],
            authorized_by=CollectionAuthorizationSource.BOUND_PUBLISHED_NOTE,
        )


def test_profile_collection_requires_user_scope_and_denies_by_default():
    """验证 Profile 只接受 USER_PROVIDED Scope，且所有拒绝均发生在 Collector 前。"""
    collector = FakeCollector()
    request = _account_input([PROFILE_1])
    no_scope = CollectXhsAccountsTool(collector=collector).execute(request)
    bound_scope = CollectXhsAccountsTool(
        collector=collector,
        access_scope=_profile_scope([PROFILE_1], CollectionAuthorizationSource.BOUND_PUBLISHED_NOTE),
    ).execute(request)
    outside_scope = CollectXhsAccountsTool(collector=collector, access_scope=_profile_scope([PROFILE_2])).execute(request)
    assert no_scope.error.code == "PERMISSION_ERROR"
    assert bound_scope.error.code == "PERMISSION_ERROR"
    assert outside_scope.error.code == "PERMISSION_ERROR"
    assert collector.account_calls == []


def test_implementation_registry_keeps_collection_tools_and_effect_is_frozen():
    """验证最终闭包仍保留两个 COLLECT_PUBLIC 采集 Tool。"""
    assert len(TOOL_REGISTRY) == 17
    assert len(TOOL_HANDLER_REGISTRY) == 17
    assert TOOL_REGISTRY[ToolName.COLLECT_XHS_NOTES].effect == ToolEffect.COLLECT_PUBLIC
    assert TOOL_REGISTRY[ToolName.COLLECT_XHS_ACCOUNTS].effect == ToolEffect.COLLECT_PUBLIC


def test_xhs_tool_architecture_and_product_boundaries():
    """验证 XHS Tool 唯一进入 Canonical Service，且不暴露搜索、旧链或持久化。"""
    source = (AGENT_ROOT / "tools" / "xhs_tools.py").read_text(encoding="utf-8")
    assert "XhsCollectorService" in source
    forbidden = (
        "app.llm",
        "app.agent.workflows",
        "app.repositories",
        "sqlalchemy",
        "fastapi",
        "HTTPException",
        "XiaohongshuMcpProvider",
        "XhsUrlCollectService",
        "CrawlerCollectionService",
        "SimpleHttpXhsProvider",
        "search_feeds",
        "list_feeds",
        "register_tool",
        ".execute(",
    )
    assert [token for token in forbidden if token in source] == []
