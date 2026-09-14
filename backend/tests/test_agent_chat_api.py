import json

from fastapi.testclient import TestClient

from app.agent.product_entry.chat_service import AgentChatPreviewService
from app.agent.product_entry.execution import ExecutionMode
from app.agent.product_entry.executor import ActionHandlerRegistry, ExecutionOrchestrator
from app.agent.product_entry.llm_router import LLMUserInputRouter
from app.agent.product_entry.pipeline import AgentEntryPreviewPipeline
from app.agent.product_entry.schemas import Action, AgentChatRequest, AllowedEffect, InputType, TargetType
from app.agent.product_entry.task_planner import LLMTaskPlanner
from app.api import agent_chat
from app.api.agent_chat import get_agent_chat_preview_service
from app.main import app


class FakeLLMClient:
    """测试用 FakeLLMClient，不调用真实 LLM。"""

    def __init__(self, output: str):
        """保存预置输出。"""
        self.output = output
        self.calls = []

    def generate_text(self, prompt: str, system_prompt: str | None = None, **kwargs):
        """记录调用并返回预置 JSON。"""
        self.calls.append({"prompt": prompt, "system_prompt": system_prompt, "kwargs": kwargs})
        return self.output


class RaisingPreviewService:
    """测试用异常服务，模拟 Pipeline 内部失败。"""

    def preview(self, request: AgentChatRequest):
        """抛出异常以验证 API 兜底响应。"""
        raise RuntimeError("boom with sk-1234567890abcdef")


def _router_payload(**overrides) -> str:
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


def _plan_payload(steps=None, **overrides) -> str:
    """构造 Plan JSON。"""
    payload = {
        "intent": "GENERATE_CONTENT_OPPORTUNITY",
        "steps": steps
        if steps is not None
        else [
            {
                "step_no": 1,
                "action": "GENERATE_CONTENT_OPPORTUNITY",
                "description": "把用户想法整理成内容机会。",
                "input_params": {"account_id": 1, "topic": "27 届双非本科做 Agent 求职"},
                "expected_output": "内容机会预览",
                "allowed_effect": "LOCAL_GENERATION",
                "can_execute": True,
            }
        ],
        "missing_params": [],
        "risk_flags": [],
        "confirmation_requirement": "NONE",
        "can_execute": True,
        "summary_for_user": "已规划入口链路预览。",
    }
    payload.update(overrides)
    return json.dumps(payload, ensure_ascii=False)


def _service(router_output: str, planner_output: str, orchestrator: ExecutionOrchestrator | None = None) -> AgentChatPreviewService:
    """构造使用 FakeLLMClient 的预览服务。"""
    pipeline = AgentEntryPreviewPipeline(
        LLMUserInputRouter(FakeLLMClient(router_output)),
        LLMTaskPlanner(FakeLLMClient(planner_output)),
        orchestrator=orchestrator,
    )
    return AgentChatPreviewService(pipeline)


def _client_with_service(service) -> TestClient:
    """创建带 dependency override 的测试客户端。"""
    app.dependency_overrides[get_agent_chat_preview_service] = lambda: service
    return TestClient(app)


def _post(service, payload: dict):
    """调用 Agent Chat preview API 并清理依赖替换。"""
    client = _client_with_service(service)
    try:
        return client.post("/agent/chat/preview", json=payload)
    finally:
        app.dependency_overrides.clear()


def _base_payload(**overrides) -> dict:
    """构造 API 请求 payload。"""
    payload = {
        "session_id": "demo-session",
        "account_id": 1,
        "text": "帮我找一个选题",
        "input_type": "TEXT",
        "attachments": [],
        "context": {},
    }
    payload.update(overrides)
    return payload


def test_post_agent_chat_preview_returns_agent_chat_response():
    """测试 POST /agent/chat/preview 可以返回 AgentChatResponse。"""
    response = _post(_service(_router_payload(), _plan_payload()), _base_payload())

    assert response.status_code == 200
    assert response.json()["status"] == "READY_TO_EXECUTE"
    assert "code" not in response.json()


def test_response_contains_trace_id():
    """测试返回体包含 trace_id。"""
    data = _post(_service(_router_payload(), _plan_payload()), _base_payload()).json()

    assert data["trace_id"]


def test_response_contains_router_result():
    """测试返回体包含 router_result。"""
    data = _post(_service(_router_payload(), _plan_payload()), _base_payload()).json()

    assert data["router_result"]["intent"] == "GENERATE_CONTENT_OPPORTUNITY"


def test_response_contains_plan():
    """测试返回体包含 plan。"""
    data = _post(_service(_router_payload(), _plan_payload()), _base_payload()).json()

    assert data["plan"]["steps"][0]["action"] == "GENERATE_CONTENT_OPPORTUNITY"


def test_response_metadata_contains_entry_trace():
    """测试返回体 metadata 包含 entry_trace。"""
    data = _post(_service(_router_payload(), _plan_payload()), _base_payload()).json()

    assert data["metadata"]["entry_trace"]["trace_id"] == data["trace_id"]


def test_new_topic_without_account_id_returns_need_clarification():
    """测试新选题缺 account_id 返回 NEED_CLARIFICATION。"""
    steps = [
        {
            "step_no": 1,
            "action": "GENERATE_CONTENT_OPPORTUNITY",
            "description": "整理内容机会。",
            "input_params": {"topic": "27 届双非本科做 Agent 求职"},
            "allowed_effect": "LOCAL_GENERATION",
            "can_execute": True,
        }
    ]
    data = _post(
        _service(_router_payload(extracted_params={"topic": "27 届双非本科做 Agent 求职"}), _plan_payload(steps=steps)),
        _base_payload(account_id=None, text="我想写一篇 27 届双非本科做 Agent 求职的帖子"),
    ).json()

    assert data["status"] == "NEED_CLARIFICATION"
    assert data["can_execute"] is False
    assert data["confirmation_card"]["title"] == "需要补充信息"


def test_ambiguous_feedback_without_target_returns_need_clarification():
    """测试“这个不行”无 target 返回 NEED_CLARIFICATION。"""
    data = _post(
        _service(
            _router_payload(
                intent="REFINE_OR_REJECT_RESULT",
                target_type="UNKNOWN",
                feedback_action="REJECT",
                feedback_polarity="NEGATIVE",
                extracted_params={},
                can_execute=True,
            ),
            _plan_payload(),
        ),
        _base_payload(account_id=None, text="这个不行"),
    ).json()

    assert data["status"] == "NEED_CLARIFICATION"
    assert "TARGET_AMBIGUOUS" in data["router_result"]["risk_flags"] or "target" in data["router_result"]["missing_params"]


def test_title_ai_with_current_target_returns_confirmation_card():
    """测试“标题太 AI”有 current_target 返回确认卡片。"""
    steps = [
        {
            "step_no": 1,
            "action": "REFINE_DRAFT",
            "description": "修改当前草稿标题。",
            "input_params": {"account_id": 1, "draft_id": 123, "feedback": "标题太 AI，换自然一点", "scope": "title"},
            "allowed_effect": "LOCAL_GENERATION",
            "can_execute": True,
        },
        {
            "step_no": 2,
            "action": "CREATE_CANDIDATE_MEMORY",
            "description": "暂存用户标题偏好。",
            "input_params": {"account_id": 1, "memory_content": "用户偏好自然标题", "source": "user_feedback"},
            "allowed_effect": "LOCAL_WRITE",
            "requires_confirmation": True,
        },
    ]
    data = _post(
        _service(
            _router_payload(intent="REFINE_OR_REJECT_RESULT", target_type="DRAFT", target_id=123, extracted_params={"scope": "title"}),
            _plan_payload(intent="REFINE_OR_REJECT_RESULT", steps=steps),
        ),
        _base_payload(text="这个标题太 AI 了，换自然一点", current_target_type=TargetType.DRAFT.value, current_target_id=123),
    ).json()

    assert data["status"] == "WAITING_CONFIRMATION"
    assert data["can_execute"] is False
    assert data["confirmation_card"]["title"] == "请确认执行计划"
    assert "REFINE_DRAFT" in [step["action"] for step in data["plan"]["steps"]]


def test_auto_publish_returns_blocked():
    """测试自动发布返回 BLOCKED。"""
    steps = [
        {
            "step_no": 1,
            "action": "NOOP",
            "description": "尝试自动发布到小红书。",
            "input_params": {"account_id": 1},
            "allowed_effect": "EXTERNAL_WRITE",
            "risk_flags": ["EXTERNAL_WRITE", "CAPABILITY_BOUNDARY_EXCEEDED"],
            "can_execute": True,
        }
    ]
    data = _post(
        _service(_router_payload(intent="GENERATE_DRAFT", extracted_params={"account_id": 1}), _plan_payload(intent="GENERATE_DRAFT", steps=steps)),
        _base_payload(text="直接帮我发布到小红书"),
    ).json()

    assert data["status"] == "BLOCKED"
    assert data["can_execute"] is False
    assert data["confirmation_card"]["title"] == "当前无法执行"
    assert "EXTERNAL_WRITE" in data["plan_validation"]["risk_flags"]
    assert "CAPABILITY_BOUNDARY_EXCEEDED" in data["plan_validation"]["risk_flags"]


def test_api_does_not_execute_real_mode():
    """测试接口不会执行 REAL mode。"""
    data = _post(_service(_router_payload(), _plan_payload()), _base_payload()).json()

    assert data["metadata"]["execution"]["mode"] == ExecutionMode.DRY_RUN.value


def test_api_does_not_call_business_handler():
    """测试接口不会调用业务 handler。"""
    called = {"value": False}
    registry = ActionHandlerRegistry()
    registry.register(Action.GENERATE_CONTENT_OPPORTUNITY, lambda step, context: called.update(value=True) or {"ok": True})
    orchestrator = ExecutionOrchestrator(registry)

    data = _post(_service(_router_payload(), _plan_payload(), orchestrator), _base_payload()).json()

    assert data["status"] == "READY_TO_EXECUTE"
    assert called["value"] is False


def test_pipeline_exception_returns_failed_response():
    """测试 Pipeline 异常时返回 FAILED。"""
    data = _post(RaisingPreviewService(), _base_payload()).json()

    assert data["status"] == "FAILED"
    assert data["can_execute"] is False
    assert data["requires_confirmation"] is False
    assert data["message"] == "Agent Chat preview failed"
    assert data["trace_id"]
    assert "sk-1234567890abcdef" not in json.dumps(data, ensure_ascii=False)


def test_service_build_failure_returns_failed_response(monkeypatch):
    """测试真实 LLM 未配置等依赖构建失败时返回安全 FAILED。"""
    app.dependency_overrides.clear()
    monkeypatch.setattr(
        agent_chat,
        "build_agent_chat_preview_service",
        lambda: (_ for _ in ()).throw(RuntimeError("LLM_CONFIG_MISSING: sk-1234567890abcdef")),
    )

    response = TestClient(app).post("/agent/chat/preview", json=_base_payload())
    data = response.json()

    assert response.status_code == 200
    assert data["status"] == "FAILED"
    assert data["can_execute"] is False
    assert data["trace_id"]
    assert "sk-1234567890abcdef" not in json.dumps(data, ensure_ascii=False)


def test_extra_fields_are_rejected_by_pydantic():
    """测试请求中额外字段会被 Pydantic 拒绝。"""
    response = _post(_service(_router_payload(), _plan_payload()), _base_payload(unexpected_field=True))

    assert response.status_code == 422


def test_api_test_uses_fake_llm_client():
    """测试中使用 FakeLLMClient，不调用真实 LLM。"""
    router_client = FakeLLMClient(_router_payload())
    planner_client = FakeLLMClient(_plan_payload())
    service = AgentChatPreviewService(
        AgentEntryPreviewPipeline(
            LLMUserInputRouter(router_client),
            LLMTaskPlanner(planner_client),
        )
    )

    data = _post(service, _base_payload()).json()

    assert data["status"] == "READY_TO_EXECUTE"
    assert router_client.calls[0]["kwargs"]["prompt_key"] == "agent_product_entry.llm_router"
    assert planner_client.calls[0]["kwargs"]["prompt_key"] == "agent_product_entry.task_planner"
