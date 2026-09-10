from decimal import Decimal

from app.enums.agent import AgentStepStatus
from app.schemas.agent import AgentRunDetailResponse, AgentRunResponse, AgentStepResponse


SUCCESS_STEP_STATUSES = {AgentStepStatus.SUCCESS.value, AgentStepStatus.FALLBACK_USED.value}
FAILED_STEP_STATUSES = {AgentStepStatus.FAILED.value, AgentStepStatus.RISK_BLOCKED.value}


class AgentObservabilityBuilder:
    """Agent 运行轨迹可观测性响应构造器。"""

    def build_run_response(self, run, steps: list) -> AgentRunResponse:
        """构造带聚合指标的 AgentRun 响应。"""
        return AgentRunResponse.model_validate({**run.__dict__, **self._run_metrics(run, steps)})

    def build_detail_response(self, run, steps: list) -> AgentRunDetailResponse:
        """构造带步骤详情和聚合指标的 AgentRun 详情响应。"""
        step_responses = [self.build_step_response(step) for step in steps]
        return AgentRunDetailResponse.model_validate({**run.__dict__, **self._run_metrics(run, steps), "steps": step_responses})

    def build_step_response(self, step) -> AgentStepResponse:
        """构造增强后的 AgentStep 响应。"""
        return AgentStepResponse.model_validate(
            {
                **step.__dict__,
                "step_order": step.step_index + 1,
                "step_name": self._step_name(step),
                "tool_input": step.input_payload,
                "tool_output_summary": self._tool_output_summary(step.output_payload),
                "error_code": self._error_code(step),
                "latency_ms": step.duration_ms,
                "fallback_used": self._fallback_used(step),
            }
        )

    def _run_metrics(self, run, steps: list) -> dict:
        """计算 AgentRun 聚合观测指标。"""
        return {
            "agent_type": getattr(run, "agent_type", "WORKFLOW_AGENT"),
            "total_steps": len(steps),
            "success_steps": len([step for step in steps if step.status in SUCCESS_STEP_STATUSES]),
            "failed_steps": len([step for step in steps if step.status in FAILED_STEP_STATUSES]),
            "llm_call_count": len([step for step in steps if "draft" in step.tool_name or "llm" in str(step.output_payload).lower()]),
            "token_count": getattr(run, "token_count", 0) or self._sum_metadata(steps, "token_count"),
            "estimated_cost": getattr(run, "estimated_cost", Decimal("0")) or Decimal(str(self._sum_metadata(steps, "estimated_cost"))),
        }

    def _tool_output_summary(self, output_payload: dict) -> dict:
        """压缩工具输出为前端可读摘要。"""
        if not output_payload:
            return {}
        data = output_payload.get("data") or {}
        return {
            "ok": output_payload.get("ok"),
            "tool_name": output_payload.get("tool_name"),
            "keys": list(data.keys())[:8],
            "error": output_payload.get("error"),
            "metadata": output_payload.get("metadata") or {},
        }

    def _error_code(self, step) -> str | None:
        """从工具输出中提取错误码。"""
        output_payload = step.output_payload or {}
        metadata = output_payload.get("metadata") or {}
        data = output_payload.get("data") or {}
        codes = metadata.get("codes") or []
        return (
            codes[0]
            if codes
            else metadata.get("original_error")
            or output_payload.get("error")
            or data.get("fallback_reason")
            or data.get("error_code")
        )

    def _fallback_used(self, step) -> bool:
        """兼容 status 和 metadata 两种 fallback 标记来源。"""
        output_payload = step.output_payload or {}
        metadata = output_payload.get("metadata") or {}
        return step.status == AgentStepStatus.FALLBACK_USED.value or metadata.get("fallback_used") is True

    def _step_name(self, step) -> str:
        """生成步骤名称。"""
        return f"{step.step_index + 1}. {step.tool_name}"

    def _sum_metadata(self, steps: list, key: str) -> int:
        """累加步骤元数据里的数值。"""
        values = [((step.output_payload or {}).get("metadata") or {}).get(key, 0) for step in steps]
        return sum(int(value) for value in values if isinstance(value, int | float))
