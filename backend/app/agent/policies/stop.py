from dataclasses import dataclass


@dataclass(frozen=True)
class StopDecision:
    """停止策略判断结果。"""

    should_stop: bool
    reason: str | None = None
    status: str | None = None


class StopPolicy:
    """Agent 执行停止策略。"""

    def __init__(self, max_steps: int = 8, max_retry: int = 1, max_consecutive_failures: int = 2):
        """初始化停止策略阈值。"""
        self.max_steps = max_steps
        self.max_retry = max_retry
        self.max_consecutive_failures = max_consecutive_failures

    def before_step(self, step_index: int, consecutive_failures: int) -> StopDecision:
        """执行步骤前检查 max_steps 和连续失败数。"""
        decisions = [
            (step_index >= self.max_steps, "max_steps", "STOPPED"),
            (consecutive_failures >= self.max_consecutive_failures, "max_consecutive_failures", "FAILED"),
        ]
        return next((StopDecision(True, reason, status) for matched, reason, status in decisions if matched), StopDecision(False))

    def after_guardrail(self, allowed: bool) -> StopDecision:
        """安全护栏拦截后给出停止决策。"""
        return StopDecision(not allowed, "risk_blocked", "RISK_BLOCKED") if not allowed else StopDecision(False)

    def after_tool_metadata(self, requires_confirmation: bool) -> StopDecision:
        """工具需要人工确认时给出停止决策。"""
        return StopDecision(True, "requires_confirmation", "REQUIRES_CONFIRMATION") if requires_confirmation else StopDecision(False)
