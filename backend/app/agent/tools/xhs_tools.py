from datetime import UTC, datetime
from typing import Any

from app.agent.schemas.evidence import EvidenceRef, EvidenceType
from app.agent.tools.definitions import ToolError, ToolResult
from app.agent.tools.xhs_contracts import (
    CollectionAccessScope,
    CollectionAuthorizationSource,
    CollectXhsAccountsInput,
    CollectXhsAccountsResult,
    CollectXhsNotesInput,
    CollectXhsNotesResult,
    CollectedAccountResult,
    CollectedNoteResult,
    FailedCollectionItem,
)
from app.services.xhs_collector_sev import XhsCollectorService
from app.services.published_note_refresh_sev import PublishedNoteRefreshService


_SUCCESS_STATUSES = {"SUCCESS", "PARTIAL_SUCCESS"}


class XhsCollectionToolBase:
    """两个公开采集 Tool 共用的结果与错误标准化能力。"""

    def _provider_failure(self, warnings: list[str] | None = None, code: str = "PROVIDER_ERROR") -> ToolResult:
        """将全部失败或 Service 异常转换为显式 Provider Error。"""
        return ToolResult(
            success=False,
            data=None,
            warnings=warnings or [],
            error=ToolError(
                code=code or "PROVIDER_ERROR",
                category="PROVIDER",
                retryable=True,
                user_action="请稍后重试或检查授权 URL。",
                safe_message="小红书公开数据采集未产生有效结果。",
            ),
        )

    def _authorization_failure(self, safe_message: str) -> ToolResult:
        """在调用 Collector 前返回默认拒绝的权限错误。"""
        return ToolResult(
            success=False,
            data=None,
            error=ToolError(
                code="PERMISSION_ERROR",
                category="PERMISSION",
                retryable=False,
                user_action="请从当前用户输入或已绑定 Published Note 重新建立可信授权范围。",
                safe_message=safe_message,
            ),
        )


class CollectXhsNotesTool(XhsCollectionToolBase):
    """通过唯一 Canonical XHS Collector 采集授权 Note URL。"""

    name = "collect_xhs_notes"

    def __init__(self, db: Any = None, collector: XhsCollectorService | None = None, access_scope: CollectionAccessScope | None = None, refresh_service: PublishedNoteRefreshService | None = None):
        """注入 Canonical Collector 与可信采集授权范围。"""
        self.collector = collector or XhsCollectorService(db)
        self.access_scope = access_scope
        self.refresh_service = refresh_service or PublishedNoteRefreshService(db, collector=self.collector)

    def execute(self, data: CollectXhsNotesInput) -> ToolResult[CollectXhsNotesResult]:
        """执行有数量和评论上限的批量 Note 采集并保留部分成功。"""
        authorization_error = self._validate_access(data)
        if authorization_error:
            return self._authorization_failure(authorization_error)
        try:
            if data.collection_purpose.value == "REFRESH_BOUND_PUBLISHED_NOTE":
                raw = self.refresh_service.refresh(
                    data.account_ref,
                    self.access_scope.published_note_ref,
                    data.note_urls[0],
                    include_comments=data.include_comments,
                    max_comments=data.max_comments,
                )
            else:
                raw = self.collector.collect_notes(
                    data.account_ref,
                    data.note_urls,
                    collect_comments=data.include_comments,
                    max_comments=data.max_comments,
                    enable_ocr=True,
                )
            return self._normalize_result(data, raw)
        except Exception as exc:
            return self._provider_failure(code=getattr(exc, "code", "PROVIDER_ERROR"))

    def _validate_access(self, data: CollectXhsNotesInput) -> str | None:
        """验证可信 Scope、账号、授权来源和全部请求 URL 的子集关系。"""
        scope = self.access_scope
        if scope is None:
            return "缺少可信 CollectionAccessScope，已拒绝采集。"
        if scope.workspace_account_ref != data.account_ref:
            return "采集请求与可信 Workspace Account 不一致。"
        if not set(data.note_urls).issubset(scope.allowed_note_urls):
            return "请求包含未授权的 Note URL。"
        if data.collection_purpose.value == "RESEARCH_INPUT" and scope.authorization_source != CollectionAuthorizationSource.USER_PROVIDED:
            return "Research Note 采集只接受 USER_PROVIDED 授权。"
        if data.collection_purpose.value == "REFRESH_BOUND_PUBLISHED_NOTE" and scope.authorization_source != CollectionAuthorizationSource.BOUND_PUBLISHED_NOTE:
            return "Published Note 刷新只接受 BOUND_PUBLISHED_NOTE 授权。"
        return None

    def _normalize_result(self, data: CollectXhsNotesInput, raw: dict) -> ToolResult[CollectXhsNotesResult]:
        """将 Canonical Service 批量摘要映射为类型化 ToolResult。"""
        collected_at = datetime.now(UTC)
        items: list[CollectedNoteResult] = []
        failed: list[FailedCollectionItem] = []
        for item in raw.get("items", []):
            if item.get("status") in _SUCCESS_STATUSES and item.get("ids", {}).get("competitor_note_id"):
                note_ref = int(item["ids"]["competitor_note_id"])
                account_ref = item.get("ids", {}).get("competitor_account_id")
                evidence_refs = []
                if account_ref:
                    evidence_refs.append(EvidenceRef(type=EvidenceType.ACCOUNT, id=int(account_ref)))
                evidence_refs.append(EvidenceRef(type=EvidenceType.NOTE, id=note_ref))
                items.append(
                    CollectedNoteResult(
                        source_url=item["input_value"],
                        note_ref=note_ref,
                        evidence_refs=evidence_refs,
                        collected_at=collected_at,
                        comments_collected=int(item.get("data_count", {}).get("comments_saved", 0)),
                        authorized_by=self.access_scope.authorization_source,
                        collection_purpose=data.collection_purpose,
                        published_note_ref=self.access_scope.published_note_ref,
                        warnings=item.get("warnings", []),
                    )
                )
            else:
                failed.append(
                    FailedCollectionItem(
                        source_url=item.get("input_value", ""),
                        error_code=item.get("error_code") or "PROVIDER_ERROR",
                        safe_message="该 Note URL 采集失败。",
                    )
                )
        warnings = list(dict.fromkeys(raw.get("warnings", [])))
        if items and failed:
            warnings.append("PARTIAL_XHS_COLLECTION")
        if not items:
            return self._provider_failure(warnings=warnings, code=raw.get("error_code") or "PROVIDER_ERROR")
        result = CollectXhsNotesResult(
            requested_count=len(data.note_urls),
            collected_count=len(items),
            failed_count=len(failed),
            items=items,
            failed_items=failed,
            warnings=warnings,
        )
        return ToolResult(success=True, data=result, warnings=warnings)


class CollectXhsAccountsTool(XhsCollectionToolBase):
    """通过唯一 Canonical XHS Collector 采集授权 Profile URL。"""

    name = "collect_xhs_accounts"

    def __init__(self, db: Any = None, collector: XhsCollectorService | None = None, access_scope: CollectionAccessScope | None = None):
        """注入 Canonical Collector 与可信采集授权范围。"""
        self.collector = collector or XhsCollectorService(db)
        self.access_scope = access_scope

    def execute(self, data: CollectXhsAccountsInput) -> ToolResult[CollectXhsAccountsResult]:
        """采集 Profile 及 user_profile 同次返回的 recent-note 摘要，不执行 Note Detail fan-out。"""
        authorization_error = self._validate_access(data)
        if authorization_error:
            return self._authorization_failure(authorization_error)
        try:
            raw = self.collector.collect_accounts(
                data.workspace_account_ref,
                data.profile_urls,
                recent_note_limit=10,
            )
            return self._normalize_result(data, raw)
        except Exception as exc:
            return self._provider_failure(code=getattr(exc, "code", "PROVIDER_ERROR"))

    def _validate_access(self, data: CollectXhsAccountsInput) -> str | None:
        """验证 Profile 请求只能使用同账号 USER_PROVIDED Scope 的完整 URL 子集。"""
        scope = self.access_scope
        if scope is None:
            return "缺少可信 CollectionAccessScope，已拒绝采集。"
        if scope.workspace_account_ref != data.workspace_account_ref:
            return "采集请求与可信 Workspace Account 不一致。"
        if scope.authorization_source != CollectionAuthorizationSource.USER_PROVIDED:
            return "Profile 采集只接受 USER_PROVIDED 授权。"
        if not set(data.profile_urls).issubset(scope.allowed_profile_urls):
            return "请求包含未授权的 Profile URL。"
        return None

    def _normalize_result(self, data: CollectXhsAccountsInput, raw: dict) -> ToolResult[CollectXhsAccountsResult]:
        """将 Canonical Service 账号摘要映射为类型化 ToolResult。"""
        collected_at = datetime.now(UTC)
        items: list[CollectedAccountResult] = []
        failed: list[FailedCollectionItem] = []
        for item in raw.get("items", []):
            if item.get("status") in _SUCCESS_STATUSES and item.get("ids", {}).get("competitor_account_id"):
                account_ref = int(item["ids"]["competitor_account_id"])
                attached_note_refs = [int(value) for value in item.get("ids", {}).get("competitor_note_ids", [])]
                items.append(
                    CollectedAccountResult(
                        source_url=item["input_value"],
                        account_ref=account_ref,
                        external_account_ref=item["input_value"],
                        evidence_refs=[
                            EvidenceRef(type=EvidenceType.ACCOUNT, id=account_ref),
                            *(EvidenceRef(type=EvidenceType.NOTE, id=ref) for ref in attached_note_refs),
                        ],
                        attached_note_refs=attached_note_refs,
                        collected_at=collected_at,
                        authorized_by=self.access_scope.authorization_source,
                        collection_purpose=data.collection_purpose,
                        warnings=item.get("warnings", []),
                    )
                )
            else:
                failed.append(
                    FailedCollectionItem(
                        source_url=item.get("input_value", ""),
                        error_code=item.get("error_code") or "PROVIDER_ERROR",
                        safe_message="该 Profile URL 采集失败。",
                    )
                )
        warnings = list(dict.fromkeys(raw.get("warnings", [])))
        if items and failed:
            warnings.append("PARTIAL_XHS_COLLECTION")
        if not items:
            return self._provider_failure(warnings=warnings, code=raw.get("error_code") or "PROVIDER_ERROR")
        result = CollectXhsAccountsResult(
            requested_count=len(data.profile_urls),
            collected_count=len(items),
            failed_count=len(failed),
            items=items,
            failed_items=failed,
            warnings=warnings,
        )
        return ToolResult(success=True, data=result, warnings=warnings)
