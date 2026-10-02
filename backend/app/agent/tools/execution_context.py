from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.agent.tools.access_scopes import EvidenceAccessScope
from app.agent.tools.xhs_contracts import CollectionAccessScope


@dataclass(frozen=True)
class RuntimeExecutionIdentity:
    """Server-generated durable Workflow execution identity."""

    run_ref: str
    workflow_name: str


@dataclass(frozen=True)
class ToolExecutionContext:
    """保存由服务器端确认并在 Tool 构建时注入的可信执行依赖。"""

    db: Session | None
    evidence_access_scope: EvidenceAccessScope | None = None
    collection_access_scope: CollectionAccessScope | None = None
    runtime_identity: RuntimeExecutionIdentity | None = None


__all__ = ["RuntimeExecutionIdentity", "ToolExecutionContext"]
