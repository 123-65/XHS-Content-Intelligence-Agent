"""Control Agent Semantic Layer：只理解 Turn，不做规划或执行。"""

from pydantic import ValidationError

from app.core.config import settings
from app.agent.control.prompts import (
    SEMANTIC_PROMPT_KEY,
    SEMANTIC_PROMPT_VERSION,
    SEMANTIC_SYSTEM_PROMPT,
    append_semantic_validation_feedback,
    build_semantic_user_prompt,
)
from app.agent.intents import BUSINESS_INTENTS
from app.agent.schemas.semantic import Intent, TaskSemanticFrame
from app.llm.client import LLMClient
from app.llm.evidence import StructuredBusinessValidationError
from app.llm.errors import LLMSchemaValidationError


class ControlAgentSemanticLayer:
    """通过统一 LLMClient 生成并验证纯语义合同。"""

    def __init__(self, llm_client=None, *, max_schema_attempts: int = 2):
        if max_schema_attempts < 1:
            raise ValueError("max_schema_attempts 必须至少为 1")
        self._llm_client = llm_client
        self._max_schema_attempts = max_schema_attempts

    def understand(self, user_turn: str) -> TaskSemanticFrame:
        """理解一轮非空用户输入；Schema 持续无效时安全返回 UNKNOWN。"""
        if not isinstance(user_turn, str) or not user_turn.strip():
            raise ValueError("user_turn 不能为空")

        client = self._llm_client or LLMClient()
        prompt = build_semantic_user_prompt(user_turn)
        for attempt in range(self._max_schema_attempts):
            try:
                response = client.generate_structured(
                    prompt=prompt,
                    schema_model=TaskSemanticFrame,
                    system_prompt=SEMANTIC_SYSTEM_PROMPT,
                    model=settings.llm_control_semantic_model or settings.llm_model,
                    extra_body={"enable_thinking": False},
                    prompt_key=SEMANTIC_PROMPT_KEY,
                    prompt_version=SEMANTIC_PROMPT_VERSION,
                )
                frame = TaskSemanticFrame.model_validate(response.data)
                frame = self._normalize_duplicate_goals(frame)
                if self._has_subsumed_review_strategy_goal(frame, user_turn):
                    error = StructuredBusinessValidationError(
                        "POST_PUBLISH_REVIEW already includes review-derived strategy recommendations",
                        validation_path="sub_goals",
                        expected="CONTENT_STRATEGY only for an explicitly independent strategy deliverable",
                        actual_value=Intent.CONTENT_STRATEGY.value,
                    )
                    self._record_business_validation_failure(client, error, frame, attempt)
                    if attempt + 1 == self._max_schema_attempts:
                        return self._mixed_goal_fallback()
                    prompt = append_semantic_validation_feedback(
                        prompt,
                        "REDUNDANT_SUB_GOAL / GOAL_SUBSUMED: POST_PUBLISH_REVIEW already produces review-derived strategy recommendations and a proposed Strategy Candidate. Remove CONTENT_STRATEGY unless the user explicitly requested a separate strategy artifact/workflow or a complete new strategy based on Research.",
                    )
                    continue
                invalid_sub_goals = [goal for goal in frame.sub_goals if goal not in BUSINESS_INTENTS]
                if frame.primary_intent in BUSINESS_INTENTS and invalid_sub_goals:
                    error = StructuredBusinessValidationError(
                        "Workflow primary intent cannot contain non-Workflow independent sub-goals",
                        validation_path="sub_goals",
                        expected="Workflow intents only when primary_intent is a Workflow intent",
                        actual_value=[goal.value for goal in invalid_sub_goals],
                    )
                    self._record_business_validation_failure(client, error, frame, attempt)
                    if attempt + 1 == self._max_schema_attempts:
                        return self._mixed_goal_fallback()
                    continue
                return frame
            except (ValidationError, LLMSchemaValidationError):
                if attempt + 1 == self._max_schema_attempts:
                    return TaskSemanticFrame(
                        primary_intent=Intent.UNKNOWN,
                        primary_goal="确认用户想完成的任务",
                        missing_info=["模型未能返回有效的语义结构，需要重新确认用户意图"],
                        confidence=0,
                    )
        raise AssertionError("unreachable")

    def _record_business_validation_failure(self, client, error, frame, attempt: int) -> None:
        recorder = getattr(client, "record_business_validation_failure", None)
        if callable(recorder):
            recorder(
                error,
                frame,
                attempt_number=attempt + 1,
                attempt_total=self._max_schema_attempts,
                retry_exhausted=attempt + 1 == self._max_schema_attempts,
            )

    @staticmethod
    def _has_subsumed_review_strategy_goal(frame: TaskSemanticFrame, user_turn: str) -> bool:
        if frame.primary_intent != Intent.POST_PUBLISH_REVIEW or Intent.CONTENT_STRATEGY not in frame.sub_goals:
            return False

        normalized = " ".join(user_turn.lower().split())
        explicit_independent_markers = (
            "content strategy artifact",
            "strategy artifact",
            "strategy workflow",
            "内容策略产物",
            "策略产物",
            "独立策略",
            "完整内容策略",
            "完整的内容策略",
            "重新制定内容策略",
            "重新创建完整内容策略",
            "重新规划",
        )
        explicit_research_context = "research" in normalized or "研究产物" in normalized
        explicit_separate_action = any(marker in normalized for marker in explicit_independent_markers)
        return not (explicit_research_context or explicit_separate_action)

    @staticmethod
    def _normalize_duplicate_goals(frame: TaskSemanticFrame) -> TaskSemanticFrame:
        """Remove duplicate Workflow goals without dropping distinct user intents."""
        seen = {frame.primary_intent}
        sub_goals = []
        for goal in frame.sub_goals:
            if goal not in seen:
                sub_goals.append(goal)
                seen.add(goal)
        return frame.model_copy(update={"sub_goals": sub_goals})

    @staticmethod
    def _mixed_goal_fallback() -> TaskSemanticFrame:
        return TaskSemanticFrame(
            primary_intent=Intent.UNKNOWN,
            primary_goal="确认当前请求中的独立目标",
            missing_info=["当前请求同时包含工作流任务和其他独立目标，请拆分为两个请求。"],
            confidence=0,
        )
