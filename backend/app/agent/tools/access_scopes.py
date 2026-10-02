from dataclasses import dataclass
from typing import ClassVar

from app.agent.schemas.evidence import EvidenceRef
from app.agent.tools.definitions import ToolResult
from app.agent.tools.xhs_contracts import CollectXhsAccountsResult, CollectXhsNotesResult


@dataclass(frozen=True, init=False)
class RunLocalEvidenceGrant:
    """仅封装同一 Run 内授权 Collection 成功产生的 EvidenceRef。"""

    trusted_collected_refs: frozenset[EvidenceRef]
    _factory_token: ClassVar[object] = object()

    def __init__(self, trusted_collected_refs: frozenset[EvidenceRef], *, _token: object):
        """拒绝普通调用方直接把用户输入引用包装成可信 Grant。"""
        if _token is not self._factory_token:
            raise TypeError("RunLocalEvidenceGrant 只能由成功 Collection ToolResult 创建")
        object.__setattr__(self, "trusted_collected_refs", trusted_collected_refs)

    @classmethod
    def from_successful_collection_result(cls, result: ToolResult) -> "RunLocalEvidenceGrant":
        """只提取成功 Collection ToolResult 中实际持久化成功项的 EvidenceRef。"""
        if not result.success or result.data is None:
            raise ValueError("失败的 Collection ToolResult 不能产生 Evidence Grant")
        if not isinstance(result.data, (CollectXhsNotesResult, CollectXhsAccountsResult)):
            raise TypeError("只有 Collection ToolResult 可以产生 Evidence Grant")
        refs = frozenset(
            evidence_ref
            for item in result.data.items
            for evidence_ref in item.evidence_refs
        )
        return cls(refs, _token=cls._factory_token)


@dataclass(frozen=True)
class EvidenceAccessScope:
    """表示由可信 Workflow 或 Artifact Resolver 注入的证据授权范围。"""

    authorized_refs: frozenset[EvidenceRef]

    @classmethod
    def deny_all(cls) -> "EvidenceAccessScope":
        """在没有可信授权上下文时返回默认拒绝范围。"""
        return cls(authorized_refs=frozenset())

    def with_run_local_grant(self, grant: RunLocalEvidenceGrant) -> "EvidenceAccessScope":
        """不可变合并外部授权与本 Run 内成功 Collection 派生的可信引用。"""
        if not isinstance(grant, RunLocalEvidenceGrant):
            raise TypeError("EvidenceAccessScope 只能接受 RunLocalEvidenceGrant")
        return EvidenceAccessScope(
            authorized_refs=self.authorized_refs | grant.trusted_collected_refs
        )

    @classmethod
    def from_run_local_grant(cls, grant: RunLocalEvidenceGrant) -> "EvidenceAccessScope":
        """在没有历史 Scope 时，仅使用本 Run 成功采集产生的可信引用。"""
        return cls.deny_all().with_run_local_grant(grant)


__all__ = ["EvidenceAccessScope", "RunLocalEvidenceGrant"]
