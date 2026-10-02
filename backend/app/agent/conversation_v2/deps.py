from dataclasses import dataclass
from typing import Protocol

from app.agent.conversation_v2.capabilities import UserCapabilitySnapshot
from app.agent.conversation_v2.decision_context import CanonicalTurnContext
from app.agent.conversation_v2.execution_gate import ExecutionGateResult
from app.agent.conversation_v2.outcomes import TurnExecutionLedger
from app.agent.conversation_v2.workspace import RecentTrustedContext, TrustedWorkspaceSnapshot
from app.agent.tools.execution_context import ToolExecutionContext
from app.runtime.agent_runtime import AgentRuntime, AgentRuntimeResult, WorkflowStartRequest
from app.runtime.workflow_resume import WorkflowResumeRequest
from app.schemas.unified_agent import AgentTurnMaterials


class WorkflowInvoker(Protocol):
    def start(self, request: WorkflowStartRequest, execution_context: ToolExecutionContext) -> AgentRuntimeResult: ...
    def resume(self, request: WorkflowResumeRequest, execution_context: ToolExecutionContext) -> AgentRuntimeResult: ...


@dataclass
class ConversationAgentDeps:
    account_ref: int
    conversation_id: int
    current_text: str
    runtime: AgentRuntime
    execution_context: ToolExecutionContext
    trusted_workspace: TrustedWorkspaceSnapshot
    recent_context: RecentTrustedContext
    current_materials: AgentTurnMaterials
    recent_note_urls: tuple[str, ...]
    recent_profile_urls: tuple[str, ...]
    capabilities: UserCapabilitySnapshot
    turn_execution_ledger: TurnExecutionLedger
    workflow_invoker: WorkflowInvoker
    execution_gate: ExecutionGateResult
    decision_context: CanonicalTurnContext
    active_pending_run_ref: str | None = None
    active_pending_checkpoint_version: int | None = None
