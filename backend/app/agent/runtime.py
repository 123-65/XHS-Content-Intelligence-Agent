from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.orm import Session

from app.agent.observability import AgentObservabilityBuilder
from app.agent.policies.fallback import FallbackPolicy
from app.agent.policies.guardrail import GuardrailPolicy
from app.agent.policies.stop import StopDecision, StopPolicy
from app.agent.tools.base import ToolDefinition, ToolNotFoundError, ToolResult
from app.agent.tools.registry import ToolRegistry
from app.enums.agent import AgentRunStatus, AgentStepStatus
from app.repositories.agent_run_repo import AgentRunRepository
from app.schemas.agent import AgentRunCreate, AgentRunDetailResponse, AgentStepCreate, AgentStepResponse, WorkflowRunRequest


@dataclass(frozen=True)
class AgentWorkflowStep:
    """Agent 工作流步骤。"""

    tool_name: str
    payload: dict[str, Any] = field(default_factory=dict)


class AgentRuntime:
    """Agent 工作流执行器。"""

    def __init__(self, db: Session, registry: ToolRegistry | None = None):
        """初始化 AgentRuntime。"""
        self.db = db
        self.repo = AgentRunRepository(db)
        self.registry = registry or ToolRegistry(db)
        self.guardrail_policy = GuardrailPolicy()
        self.fallback_policy = FallbackPolicy()
        self.observability = AgentObservabilityBuilder()

    def run(self, request: WorkflowRunRequest) -> AgentRunDetailResponse:
        """执行工具化 Agent 工作流并记录完整轨迹。"""
        run = self.repo.create_run(
            AgentRunCreate(
                account_id=request.account_id,
                agent_type=request.agent_type,
                workflow_name=request.workflow_name,
                input_payload=request.input_payload,
                max_steps=request.max_steps,
                max_retry=request.max_retry,
            )
        )
        stop_policy = StopPolicy(max_steps=request.max_steps, max_retry=request.max_retry)
        outputs: list[dict] = []
        try:
            for index, step_spec in enumerate(request.steps):
                stop = stop_policy.before_step(index, run.consecutive_failures)
                if stop.should_stop:
                    return self._finish(run, stop, outputs)
                result = self._execute_step(run, index, step_spec.tool_name, step_spec.payload, stop_policy)
                outputs.append(result.model_dump())
                run = self.repo.get_run(run.id) or run
                terminal = self._terminal_after_result(result)
                if terminal.should_stop:
                    return self._finish(run, terminal, outputs)
            status = AgentRunStatus.SUCCESS.value if all(item.get("ok") for item in outputs) else AgentRunStatus.FAILED.value
            finished = self.repo.finish_run(run, status, {"steps": outputs})
            return self._build_response(finished)
        except Exception as exc:
            failed = self.repo.finish_run(run, AgentRunStatus.FAILED.value, {"steps": outputs}, "runtime_error", str(exc))
            return self._build_response(failed)

    def _execute_step(self, run, step_index: int, tool_name: str, payload: dict, stop_policy: StopPolicy) -> ToolResult:
        """执行单个工具步骤。"""
        guardrail = self.guardrail_policy.inspect(tool_name, payload)
        tool = self._resolve_tool(tool_name)
        step = self.repo.create_step(
            AgentStepCreate(
                agent_run_id=run.id,
                step_index=step_index,
                tool_name=tool_name,
                tool_type=tool.tool_type,
                input_payload=payload,
                risk_level=tool.risk_level,
                requires_confirmation=tool.requires_confirmation,
                fallback_tool_name=tool.fallback_tool_name,
            )
        )
        guardrail_stop = stop_policy.after_guardrail(guardrail.allowed)
        if guardrail_stop.should_stop:
            result = ToolResult(False, tool_name, error=guardrail.reason, metadata={"codes": guardrail.codes, "risk_blocked": True})
            self.repo.finish_step(step, AgentStepStatus.RISK_BLOCKED.value, result.model_dump(), error_message=guardrail.reason)
            return result
        confirmation_stop = stop_policy.after_tool_metadata(tool.requires_confirmation)
        if confirmation_stop.should_stop:
            result = ToolResult(False, tool_name, {"requires_confirmation": True}, metadata={"stop_reason": "requires_confirmation"})
            self.repo.finish_step(step, AgentStepStatus.REQUIRES_CONFIRMATION.value, result.model_dump())
            return result
        result, retry_count, status = self._call_tool_with_fallback(tool, payload, run.id, step.id, stop_policy.max_retry)
        self._update_failure_counter(run, result.ok)
        self.repo.finish_step(step, status, result.model_dump(), retry_count, result.error)
        return result

    def _call_tool_with_fallback(self, tool: ToolDefinition, payload: dict, agent_run_id: int, agent_step_id: int, max_retry: int) -> tuple[ToolResult, int, str]:
        """调用工具并在失败时尝试降级。"""
        attempts = range(0, max_retry + 1)
        for retry_count in attempts:
            try:
                result = tool.handler(self._payload_with_context(payload, agent_run_id, agent_step_id))
                if result.ok:
                    return result, retry_count, AgentStepStatus.SUCCESS.value
                fallback = self.fallback_policy.fallback_for(tool, ValueError(result.error or "tool failed"))
                return self._fallback_result(fallback, payload, retry_count, result.error)
            except Exception as exc:
                fallback = self.fallback_policy.fallback_for(tool, exc)
                if retry_count == max_retry or fallback:
                    return self._fallback_result(fallback, payload, retry_count, str(exc))
        return ToolResult(False, tool.name, error="tool failed"), 1, AgentStepStatus.FAILED.value

    def _fallback_result(self, fallback_tool_name: str | None, payload: dict, retry_count: int, error: str | None) -> tuple[ToolResult, int, str]:
        """执行降级工具并返回步骤状态。"""
        if not fallback_tool_name:
            return ToolResult(False, "fallback_missing", error=error), retry_count, AgentStepStatus.FAILED.value
        fallback_tool = self.registry.get_tool(fallback_tool_name)
        fallback_payload = {"original_payload": payload, "error": error}
        result = fallback_tool.handler(fallback_payload)
        status = AgentStepStatus.FALLBACK_USED.value if result.ok else AgentStepStatus.FAILED.value
        return result, retry_count, status

    def _resolve_tool(self, tool_name: str) -> ToolDefinition:
        """解析工具定义，不存在时返回风险阻断占位工具。"""
        try:
            return self.registry.get_tool(tool_name)
        except ToolNotFoundError:
            return ToolDefinition(
                name=tool_name,
                tool_type="UNKNOWN",
                handler=lambda payload: ToolResult(False, tool_name, error="Tool not found"),
                description="未注册工具",
                risk_level="HIGH",
            )

    def _payload_with_context(self, payload: dict, agent_run_id: int, agent_step_id: int) -> dict:
        """向工具入参追加运行上下文。"""
        return {**payload, "_agent_run_id": agent_run_id, "_agent_step_id": agent_step_id}

    def _update_failure_counter(self, run, ok: bool) -> None:
        """根据工具结果更新连续失败计数。"""
        actions = {True: self.repo.reset_failure, False: self.repo.increment_failure}
        actions[ok](run)

    def _terminal_after_result(self, result: ToolResult) -> StopDecision:
        """根据工具结果判断是否终止运行。"""
        metadata = result.metadata or {}
        decisions = [
            (metadata.get("risk_blocked"), "risk_blocked", AgentRunStatus.RISK_BLOCKED.value),
            (metadata.get("stop_reason") == "requires_confirmation", "requires_confirmation", AgentRunStatus.REQUIRES_CONFIRMATION.value),
        ]
        return next((StopDecision(True, reason, status) for matched, reason, status in decisions if matched), StopDecision(False))

    def _finish(self, run, stop: StopDecision, outputs: list[dict]) -> AgentRunDetailResponse:
        """根据停止决策结束运行。"""
        finished = self.repo.finish_run(run, stop.status or AgentRunStatus.STOPPED.value, {"steps": outputs}, stop.reason)
        return self._build_response(finished)

    def _build_response(self, run) -> AgentRunDetailResponse:
        """构造带步骤详情的运行响应。"""
        return self.observability.build_detail_response(run, self.repo.list_steps(run.id))
