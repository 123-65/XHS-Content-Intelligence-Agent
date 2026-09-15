from fastapi.testclient import TestClient

from app.agent.product_entry.chat_service import AgentChatPreviewService, AgentChatReadonlyExecuteService
from app.agent.product_entry.pipeline import AgentEntryPreviewPipeline
from app.agent.product_entry.schemas import (
    Action,
    AgentChatRequest,
    AllowedEffect,
    ConfirmationRequirement,
    InputType,
    Intent,
    Plan,
    PlanStep,
    RouterResult,
    TargetType,
)
from app.agent.product_entry.llm_router import LLMUserInputRouter
from app.agent.product_entry.task_planner import LLMTaskPlanner
from app.api.agent_chat import get_agent_chat_preview_service, get_agent_chat_readonly_execute_service
from app.core.database import SessionLocal
from app.main import app
from app.schemas.account import AccountProfileCreate
from app.schemas.agent_conversation import ConversationCreate
from app.services.account_sev import AccountProfileService
from app.services.agent_conversation_sev import AgentConversationService


class FailingLLMClient:
    """测试用 Fake LLM，调用即失败。"""

    def __init__(self):
        """初始化调用记录。"""
        self.calls = []

    def generate_text(self, *args, **kwargs):
        """阻止测试调用真实或模拟 LLM。"""
        self.calls.append({"args": args, "kwargs": kwargs})
        raise AssertionError("LLM should not be called in conversation flow tests")


class FakeRouter:
    """测试用 Router，返回固定 RouterResult 并记录输入。"""

    def __init__(self, result: RouterResult):
        """保存固定结果。"""
        self.result = result
        self.inputs = []

    def route(self, agent_input, recorder=None):
        """记录输入并返回固定结果。"""
        self.inputs.append(agent_input)
        if recorder:
            recorder.record_router_result(self.result)
        return self.result


class FakePlanner:
    """测试用 Planner，返回固定 Plan 并记录输入。"""

    def __init__(self, plan: Plan):
        """保存固定计划。"""
        self._plan = plan
        self.inputs = []

    def plan(self, agent_input, router_result, recorder=None):
        """记录输入并返回固定计划。"""
        self.inputs.append(agent_input)
        if recorder:
            recorder.record_plan(self._plan)
        return self._plan


def _create_account() -> int:
    """创建测试账号。"""
    db = SessionLocal()
    try:
        account = AccountProfileService(db).create_account(
            AccountProfileCreate(
                account_name="B1 Agent Chat 会话账号",
                platform="xhs",
                content_domain="AI 求职",
                positioning="帮助新人拆解 Agent 项目",
                target_audience="AI 应用工程新人",
                primary_goal="lead",
            )
        )
        return account.id
    finally:
        db.close()


def _create_conversation(account_id: int | None = None) -> int:
    """创建测试会话。"""
    db = SessionLocal()
    try:
        return AgentConversationService(db).create_conversation(ConversationCreate(account_id=account_id)).id
    finally:
        db.close()


def _messages(conversation_id: int) -> list[dict]:
    """读取会话消息。"""
    return TestClient(app).get(f"/agent/conversations/{conversation_id}/messages").json()


def _state(conversation_id: int) -> dict:
    """读取会话状态。"""
    return TestClient(app).get(f"/agent/conversations/{conversation_id}/state").json()


def _router_result(account_id: int | None = 1, **overrides) -> RouterResult:
    """构造 RouterResult。"""
    data = {
        "intent": Intent.QUERY_STATUS,
        "confidence": 0.95,
        "input_type": InputType.TEXT,
        "target_type": TargetType.ACCOUNT,
        "target_id": account_id,
        "extracted_params": {"account_id": account_id} if account_id else {},
        "can_execute": True,
    }
    data.update(overrides)
    return RouterResult(**data)


def _plan(action: Action = Action.NOOP, account_id: int | None = 1, **overrides) -> Plan:
    """构造测试 Plan。"""
    step = PlanStep(
        step_no=1,
        action=action,
        description=f"test {action.value}",
        input_params={"account_id": account_id} if account_id else {},
        allowed_effect=AllowedEffect.READ_ONLY,
        can_execute=True,
    )
    data = {
        "intent": Intent.QUERY_STATUS,
        "steps": [step],
        "confirmation_requirement": ConfirmationRequirement.NONE,
        "can_execute": True,
    }
    data.update(overrides)
    return Plan(**data)


def _preview_service(router: FakeRouter, planner: FakePlanner, db) -> AgentChatPreviewService:
    """构造带 ConversationService 的 preview service。"""
    return AgentChatPreviewService(AgentEntryPreviewPipeline(router, planner), AgentConversationService(db))


def _post_preview(service, payload: dict):
    """调用 preview API 并清理依赖替换。"""
    app.dependency_overrides[get_agent_chat_preview_service] = lambda: service
    try:
        return TestClient(app).post("/agent/chat/preview", json=payload)
    finally:
        app.dependency_overrides.clear()


def _post_execute(service, payload: dict):
    """调用 execute-readonly API 并清理依赖替换。"""
    app.dependency_overrides[get_agent_chat_readonly_execute_service] = lambda: service
    try:
        return TestClient(app).post("/agent/chat/execute-readonly", json=payload)
    finally:
        app.dependency_overrides.clear()


def _payload(conversation_id: int | None = None, **overrides) -> dict:
    """构造 AgentChatRequest payload。"""
    payload = {
        "conversation_id": conversation_id,
        "session_id": "b1-session",
        "account_id": None,
        "text": "查看当前账号画像",
        "input_type": "TEXT",
        "attachments": [],
        "context": {},
    }
    payload.update(overrides)
    return payload


def test_preview_with_conversation_saves_user_and_assistant_messages():
    """preview 带 conversation_id 时保存 USER 和 ASSISTANT 消息。"""
    account_id = _create_account()
    conversation_id = _create_conversation()
    db = SessionLocal()
    try:
        service = _preview_service(FakeRouter(_router_result(account_id)), FakePlanner(_plan(account_id=account_id)), db)
        data = _post_preview(service, _payload(conversation_id, account_id=account_id, text="看看账号画像")).json()
    finally:
        db.close()

    messages = _messages(conversation_id)
    assert data["conversation_id"] == conversation_id
    assert [item["role"] for item in messages] == ["USER", "ASSISTANT"]
    assert messages[0]["content"] == "看看账号画像"
    assert messages[1]["message_type"] == "AGENT_RESPONSE"


def test_execute_readonly_with_conversation_saves_user_and_assistant_messages():
    """execute-readonly 带 conversation_id 时保存 USER / ASSISTANT 消息。"""
    account_id = _create_account()
    conversation_id = _create_conversation()
    db = SessionLocal()
    try:
        llm = FailingLLMClient()
        service = AgentChatReadonlyExecuteService(
            router=LLMUserInputRouter(llm),
            planner=LLMTaskPlanner(llm),
            db=db,
            conversation_service=AgentConversationService(db),
        )
        data = _post_execute(service, _payload(conversation_id, account_id=account_id)).json()
    finally:
        db.close()

    messages = _messages(conversation_id)
    assert data["status"] == "SUCCESS"
    assert len(messages) == 2
    assert messages[0]["role"] == "USER"
    assert messages[1]["role"] == "ASSISTANT"
    assert messages[1]["metadata_payload"]["actions"] == ["QUERY_ACCOUNT_PROFILE"]
    assert llm.calls == []


def test_request_account_id_updates_active_account_id():
    """request.account_id 会更新 active_account_id。"""
    account_id = _create_account()
    conversation_id = _create_conversation()
    db = SessionLocal()
    try:
        service = _preview_service(FakeRouter(_router_result(account_id)), FakePlanner(_plan(account_id=account_id)), db)
        _post_preview(service, _payload(conversation_id, account_id=account_id))
    finally:
        db.close()

    assert _state(conversation_id)["active_account_id"] == account_id


def test_state_active_account_id_is_used_as_next_round_fallback():
    """state.active_account_id 可以在下一轮作为 account_id 兜底。"""
    account_id = _create_account()
    conversation_id = _create_conversation(account_id=account_id)
    db = SessionLocal()
    try:
        llm = FailingLLMClient()
        service = AgentChatReadonlyExecuteService(
            router=LLMUserInputRouter(llm),
            planner=LLMTaskPlanner(llm),
            db=db,
            conversation_service=AgentConversationService(db),
        )
        data = _post_execute(service, _payload(conversation_id, account_id=None, text="查看当前账号画像")).json()
    finally:
        db.close()

    assert data["status"] == "SUCCESS"
    assert data["metadata"]["business_result"]["account_id"] == account_id
    assert llm.calls == []


def test_request_current_target_updates_state():
    """request.current_target_type/id 会更新 current_target。"""
    account_id = _create_account()
    conversation_id = _create_conversation(account_id=account_id)
    db = SessionLocal()
    try:
        service = _preview_service(FakeRouter(_router_result(account_id)), FakePlanner(_plan(account_id=account_id)), db)
        _post_preview(
            service,
            _payload(
                conversation_id,
                account_id=account_id,
                current_target_type="CONTENT_EXPERIMENT",
                current_target_id=321,
            ),
        )
    finally:
        db.close()

    state = _state(conversation_id)
    assert state["current_target_type"] == "CONTENT_EXPERIMENT"
    assert state["current_target_id"] == 321
    assert state["active_experiment_id"] == 321


def test_pending_confirmation_is_saved_when_response_requires_confirmation():
    """response.requires_confirmation=true 时保存 pending_confirmation。"""
    account_id = _create_account()
    conversation_id = _create_conversation(account_id=account_id)
    confirm_step = PlanStep(
        step_no=1,
        action=Action.CREATE_CANDIDATE_MEMORY,
        description="暂存候选记忆",
        input_params={"account_id": account_id, "memory_content": "用户不喜欢功利标题", "source": "user_feedback"},
        allowed_effect=AllowedEffect.LOCAL_WRITE,
        requires_confirmation=True,
        can_execute=True,
    )
    plan = Plan(
        intent=Intent.REFINE_OR_REJECT_RESULT,
        steps=[confirm_step],
        confirmation_requirement=ConfirmationRequirement.USER_CONFIRM_REQUIRED,
        can_execute=True,
    )
    db = SessionLocal()
    try:
        service = _preview_service(
            FakeRouter(_router_result(account_id, intent=Intent.REFINE_OR_REJECT_RESULT)),
            FakePlanner(plan),
            db,
        )
        _post_preview(service, _payload(conversation_id, account_id=account_id, text="记住我不喜欢功利标题"))
    finally:
        db.close()

    state = _state(conversation_id)
    pending = state["pending_confirmation"]
    assert pending["action_type"] == "CONFIRM_PLAN"
    assert pending["confirmation_requirement"] == "USER_CONFIRM_REQUIRED"
    assert state["last_action"] == "CREATE_CANDIDATE_MEMORY"


def test_next_round_loads_recent_messages_into_context():
    """下一轮请求能加载最近消息到 context。"""
    account_id = _create_account()
    conversation_id = _create_conversation(account_id=account_id)
    first_router = FakeRouter(_router_result(account_id))
    first_planner = FakePlanner(_plan(account_id=account_id))
    db = SessionLocal()
    try:
        first_service = _preview_service(first_router, first_planner, db)
        _post_preview(first_service, _payload(conversation_id, account_id=account_id, text="第一轮"))
    finally:
        db.close()

    second_router = FakeRouter(_router_result(account_id))
    second_planner = FakePlanner(_plan(account_id=account_id))
    db = SessionLocal()
    try:
        second_service = _preview_service(second_router, second_planner, db)
        _post_preview(second_service, _payload(conversation_id, account_id=None, text="第二轮"))
    finally:
        db.close()

    context = second_router.inputs[0].metadata["context"]["conversation"]
    assert len(context["recent_messages"]) == 2
    assert context["recent_messages"][0]["role"] == "USER"
    assert context["current_state"]["active_account_id"] == account_id


def test_without_conversation_id_keeps_original_behavior():
    """不带 conversation_id 时保持原行为，不保存历史。"""
    router = FakeRouter(_router_result(1))
    planner = FakePlanner(_plan(account_id=1))
    db = SessionLocal()
    try:
        service = _preview_service(router, planner, db)
        data = _post_preview(service, _payload(None, account_id=1)).json()
    finally:
        db.close()

    assert data["conversation_id"] is None
    assert data["metadata"].get("conversation") is None


def test_nonexistent_conversation_id_returns_safe_error():
    """conversation_id 不存在时返回安全错误。"""
    db = SessionLocal()
    try:
        service = _preview_service(FakeRouter(_router_result(1)), FakePlanner(_plan(account_id=1)), db)
        data = _post_preview(service, _payload(999999999, account_id=1)).json()
    finally:
        db.close()

    assert data["status"] == "FAILED"
    assert data["conversation_id"] == 999999999
    assert data["metadata"]["error"]["type"] == "ValueError"
