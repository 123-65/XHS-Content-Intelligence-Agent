from types import SimpleNamespace

import pytest

from app.agent.conversation_v2.execution_gate import (
    ExecutionGate,
    ExecutionGateInput,
    ExecutionGateReason,
    ExecutionGateResult,
    ExecutionMode,
)


class GateClient:
    def __init__(self, result: ExecutionGateResult):
        self.result = result
        self.calls = []

    def generate_structured(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(data=self.result)


def _result(mode, reason, confidence=0.99):
    return ExecutionGateResult(mode=mode, confidence=confidence, reason_code=reason)


def test_gate_input_is_bounded_and_uses_fast_non_thinking_model(monkeypatch):
    monkeypatch.setattr("app.agent.conversation_v2.execution_gate.settings.llm_control_semantic_model", "qwen3.8-flash")
    client = GateClient(_result(ExecutionMode.CONVERSATION, ExecutionGateReason.MEMORY_QUESTION))
    data = ExecutionGateInput(
        latest_user_text="你有记忆吗",
        current_material_types=("NOTE",),
        workspace_object_type=("DRAFT",),
        recent_business_context_types=("RESEARCH",),
        active_pending_type="CLARIFICATION",
    )

    result = ExecutionGate(client).classify(data)

    call = client.calls[0]
    assert result.mode == ExecutionMode.CONVERSATION
    assert call["model"] == "qwen3.8-flash"
    assert call["extra_body"] == {"enable_thinking": False}
    assert call["timeout_seconds"] <= 15
    assert set(data.model_dump()) == {
        "latest_user_text",
        "current_material_types",
        "workspace_object_type",
        "recent_business_context_types",
        "active_pending_type",
    }
    assert "assistant_history" not in call["prompt"]
    assert "research_content" not in call["prompt"]


@pytest.mark.parametrize(
    "text,reason",
    [
        ("你好", ExecutionGateReason.CASUAL_CONVERSATION),
        ("你能做什么", ExecutionGateReason.CAPABILITY_QUESTION),
        ("你是怎么知道的", ExecutionGateReason.FOLLOW_UP_EXPLANATION),
        ("现在起你叫张三", ExecutionGateReason.IDENTITY_OR_PERSONA),
        ("你现在叫张三", ExecutionGateReason.IDENTITY_OR_PERSONA),
        ("你有记忆吗", ExecutionGateReason.MEMORY_QUESTION),
        ("你记得我刚才让你叫什么吗", ExecutionGateReason.MEMORY_QUESTION),
        ("什么是内容策略", ExecutionGateReason.META_QUESTION),
        ("复盘是什么意思", ExecutionGateReason.META_QUESTION),
        ("你能修改草稿吗", ExecutionGateReason.CAPABILITY_QUESTION),
        ("为什么你不能自动发布", ExecutionGateReason.CAPABILITY_QUESTION),
        ("我跟你普通聊聊天", ExecutionGateReason.CASUAL_CONVERSATION),
    ],
)
def test_chat_dataset_classifies_as_conversation(text, reason):
    gate = ExecutionGate(GateClient(_result(ExecutionMode.CONVERSATION, reason)))

    result = gate.classify(ExecutionGateInput(latest_user_text=text))

    assert result.mode == ExecutionMode.CONVERSATION


def test_low_confidence_business_prediction_fails_closed_to_conversation():
    gate = ExecutionGate(GateClient(_result(
        ExecutionMode.BUSINESS_ACTION,
        ExecutionGateReason.EXPLICIT_BUSINESS_ACTION,
        confidence=0.74,
    )))

    result = gate.classify(ExecutionGateInput(latest_user_text="也许做点什么"))

    assert result.mode == ExecutionMode.CONVERSATION
    assert result.reason_code == ExecutionGateReason.AMBIGUOUS


def test_invalid_business_reason_fails_closed_to_conversation():
    gate = ExecutionGate(GateClient(_result(
        ExecutionMode.BUSINESS_ACTION,
        ExecutionGateReason.MEMORY_QUESTION,
    )))

    result = gate.classify(ExecutionGateInput(latest_user_text="你有记忆吗"))

    assert result.mode == ExecutionMode.CONVERSATION
    assert result.reason_code == ExecutionGateReason.AMBIGUOUS


def test_pending_continuation_can_open_business_action():
    gate = ExecutionGate(GateClient(_result(
        ExecutionMode.BUSINESS_ACTION,
        ExecutionGateReason.PENDING_CONTINUATION,
    )))

    result = gate.classify(ExecutionGateInput(
        latest_user_text="https://www.xiaohongshu.com/user/profile/u1",
        current_material_types=("PROFILE",),
        active_pending_type="CLARIFICATION",
    ))

    assert result.mode == ExecutionMode.BUSINESS_ACTION
    assert result.reason_code == ExecutionGateReason.PENDING_CONTINUATION


def test_gate_failure_does_not_fallback_to_legacy_control():
    class FailingClient:
        def generate_structured(self, **kwargs):
            raise ValueError("invalid structured response")

    result = ExecutionGate(FailingClient()).classify(ExecutionGateInput(latest_user_text="你好"))

    assert result == ExecutionGate.safe_conversation_result()
