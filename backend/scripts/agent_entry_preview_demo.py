"""Agent Entry Preview Pipeline demo，使用 FakeLLMClient，不调用真实模型。"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.agent.product_entry.llm_router import LLMUserInputRouter
from app.agent.product_entry.pipeline import AgentEntryPreviewPipeline
from app.agent.product_entry.schemas import AgentChatRequest, InputType, TargetType
from app.agent.product_entry.task_planner import LLMTaskPlanner


class FakeLLMClient:
    """Demo 用 FakeLLMClient，只返回预置 JSON，不消耗真实模型额度。"""

    def __init__(self, output: str):
        """保存本案例的预置 LLM 输出。"""
        self.output = output
        self.calls = []

    def generate_text(self, prompt: str, system_prompt: str | None = None, **kwargs):
        """记录调用参数并返回预置文本。"""
        self.calls.append({"prompt_key": kwargs.get("prompt_key"), "prompt_length": len(prompt), "system_prompt_length": len(system_prompt or "")})
        return self.output


def router_json(**overrides) -> str:
    """构造 RouterResult JSON。"""
    payload = {
        "intent": "GENERATE_CONTENT_OPPORTUNITY",
        "confidence": 0.9,
        "input_type": "TEXT",
        "target_type": "UNKNOWN",
        "feedback_action": "UNKNOWN",
        "feedback_polarity": "UNKNOWN",
        "extracted_params": {"topic": "27 届双非本科做 Agent 求职"},
        "missing_params": [],
        "risk_flags": [],
        "requires_clarification": False,
        "requires_confirmation": False,
        "can_execute": True,
    }
    payload.update(overrides)
    return json.dumps(payload, ensure_ascii=False)


def plan_json(steps, **overrides) -> str:
    """构造 Plan JSON。"""
    payload = {
        "intent": "GENERATE_CONTENT_OPPORTUNITY",
        "steps": steps,
        "missing_params": [],
        "risk_flags": [],
        "confirmation_requirement": "NONE",
        "can_execute": True,
        "summary_for_user": "入口预览链路已完成任务规划。",
    }
    payload.update(overrides)
    return json.dumps(payload, ensure_ascii=False)


def run_case(name: str, request: AgentChatRequest, router_output: str, planner_output: str) -> dict:
    """运行一个 demo case 并返回可保存的 JSON 结果。"""
    pipeline = AgentEntryPreviewPipeline(
        LLMUserInputRouter(FakeLLMClient(router_output)),
        LLMTaskPlanner(FakeLLMClient(planner_output)),
    )
    response = pipeline.preview(request)
    payload = {
        "case": name,
        "trace_id": response.trace_id,
        "response": response.model_dump(mode="json"),
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return payload


def main() -> int:
    """运行四个入口预览案例并保存结果。"""
    root = Path(__file__).resolve().parents[2]
    cases = [
        (
            "new_topic_missing_account",
            AgentChatRequest(session_id="demo_case_1", text="我想写一篇 27 届双非本科做 Agent 求职的帖子", input_type=InputType.TEXT),
            router_json(extracted_params={"topic": "27 届双非本科做 Agent 求职"}),
            plan_json(
                [
                    {
                        "step_no": 1,
                        "action": "GENERATE_CONTENT_OPPORTUNITY",
                        "description": "把自然语言想法整理成可评估的内容机会。",
                        "input_params": {"topic": "27 届双非本科做 Agent 求职"},
                        "expected_output": "内容机会预览",
                        "allowed_effect": "LOCAL_GENERATION",
                        "can_execute": True,
                    }
                ]
            ),
        ),
        (
            "ambiguous_rejection_without_target",
            AgentChatRequest(session_id="demo_case_2", text="这个不行", input_type=InputType.TEXT),
            router_json(
                intent="REFINE_OR_REJECT_RESULT",
                target_type="UNKNOWN",
                feedback_action="REJECT",
                feedback_polarity="NEGATIVE",
                extracted_params={},
                can_execute=True,
                clarification_question="你说的“这个”是指草稿、标题、选题还是执行计划？",
            ),
            plan_json([]),
        ),
        (
            "refine_title_with_current_target",
            AgentChatRequest(
                session_id="demo_case_3",
                account_id=1,
                text="这个标题太 AI 了，换自然一点",
                input_type=InputType.TEXT,
                current_target_type=TargetType.DRAFT,
                current_target_id=123,
            ),
            router_json(
                intent="REFINE_OR_REJECT_RESULT",
                target_type="DRAFT",
                target_id=123,
                feedback_action="REFINE",
                feedback_polarity="NEGATIVE",
                reject_reason="标题太 AI",
                preferred_direction="更自然",
                extracted_params={"scope": "title"},
            ),
            plan_json(
                [
                    {
                        "step_no": 1,
                        "action": "REFINE_DRAFT",
                        "description": "按用户反馈把当前草稿标题改得更自然。",
                        "input_params": {"account_id": 1, "draft_id": 123, "feedback": "标题太 AI，换自然一点", "scope": "title"},
                        "expected_output": "更自然的标题候选",
                        "allowed_effect": "LOCAL_GENERATION",
                        "can_execute": True,
                    },
                    {
                        "step_no": 2,
                        "action": "CREATE_CANDIDATE_MEMORY",
                        "description": "把用户不喜欢 AI 味标题的偏好暂存为候选记忆。",
                        "input_params": {"account_id": 1, "memory_content": "用户偏好更自然、更少 AI 味的标题", "source": "user_feedback"},
                        "depends_on": [1],
                        "expected_output": "候选记忆",
                        "allowed_effect": "LOCAL_WRITE",
                        "requires_confirmation": True,
                    },
                ],
                intent="REFINE_OR_REJECT_RESULT",
            ),
        ),
        (
            "auto_publish_blocked",
            AgentChatRequest(session_id="demo_case_4", account_id=1, text="直接帮我发布到小红书", input_type=InputType.TEXT),
            router_json(intent="GENERATE_DRAFT", extracted_params={"account_id": 1}, risk_flags=["EXTERNAL_WRITE"]),
            plan_json(
                [
                    {
                        "step_no": 1,
                        "action": "NOOP",
                        "description": "用户请求自动发布到小红书，当前阶段明确阻断。",
                        "input_params": {"account_id": 1},
                        "expected_output": "外部发布结果",
                        "allowed_effect": "EXTERNAL_WRITE",
                        "risk_flags": ["EXTERNAL_WRITE", "CAPABILITY_BOUNDARY_EXCEEDED"],
                        "can_execute": True,
                    }
                ],
                intent="GENERATE_DRAFT",
            ),
        ),
    ]

    results = [run_case(*case) for case in cases]
    output_path = root / "docs" / "demo_agent_entry_preview_result.json"
    output_path.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"saved_to={output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
