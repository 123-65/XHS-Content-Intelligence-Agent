from fastapi.testclient import TestClient

from app.agent.product_entry.business_handlers import build_readonly_action_handler_registry
from app.agent.product_entry.chat_service import AgentChatReadonlyExecuteService
from app.agent.product_entry.llm_router import LLMUserInputRouter
from app.agent.product_entry.schemas import (
    Action,
    AllowedEffect,
    ConfirmationRequirement,
    InputType,
    Intent,
    Plan,
    PlanStep,
    RouterResult,
    TargetType,
)
from app.agent.product_entry.task_planner import LLMTaskPlanner
from app.api.agent_chat import get_agent_chat_readonly_execute_service
from app.core.database import SessionLocal
from app.main import app
from app.schemas.account import AccountProfileCreate
from app.services.account_sev import AccountProfileService


class FailingLLMClient:
    """Fake LLM client; tests fail if any real routing/planning path calls it."""

    def __init__(self):
        self.calls = []

    def generate_text(self, *args, **kwargs):
        self.calls.append({"args": args, "kwargs": kwargs})
        raise AssertionError("LLM should not be called in readonly account profile tests")


class FakeRouter:
    def __init__(self, result: RouterResult):
        self.result = result

    def route(self, agent_input, recorder=None):
        if recorder:
            recorder.record_router_result(self.result)
        return self.result


class FakePlanner:
    def __init__(self, plan: Plan):
        self._plan = plan

    def plan(self, agent_input, router_result, recorder=None):
        if recorder:
            recorder.record_plan(self._plan)
        return self._plan


def _base_payload(**overrides) -> dict:
    payload = {
        "session_id": "readonly-session",
        "account_id": None,
        "text": "查看当前账号画像",
        "input_type": "TEXT",
        "attachments": [],
        "context": {},
    }
    payload.update(overrides)
    return payload


def _create_account() -> int:
    db = SessionLocal()
    try:
        account = AccountProfileService(db).create_account(
            AccountProfileCreate(
                account_name="7.1 只读测试账号",
                platform="xhs",
                homepage_url="https://www.xiaohongshu.com/user/profile/readonly-test",
                content_domain="求职成长",
                positioning="帮助普通背景求职者理解 Agent 工程实践",
                target_audience="想转型 AI 应用工程的学生和新人",
                persona="真实、克制、工程导向",
                business_model="课程咨询",
                main_product="Agent 项目训练营",
                lead_value=10,
                avg_order_value=99,
                gross_profit=80,
                primary_goal="lead",
                tone_preference="真诚、具体、不夸张",
                forbidden_topics="虚假承诺",
                risk_preference="BALANCED",
                account_stage="STARTUP",
            )
        )
        return account.id
    finally:
        db.close()


def _post(payload: dict):
    return TestClient(app).post("/agent/chat/execute-readonly", json=payload)


def _service_with_fake_llm(db):
    llm = FailingLLMClient()
    service = AgentChatReadonlyExecuteService(
        router=LLMUserInputRouter(llm),
        planner=LLMTaskPlanner(llm),
        db=db,
    )
    return service, llm


def _post_with_service(service, payload: dict):
    app.dependency_overrides[get_agent_chat_readonly_execute_service] = lambda: service
    try:
        return TestClient(app).post("/agent/chat/execute-readonly", json=payload)
    finally:
        app.dependency_overrides.clear()


def _router_result(intent=Intent.QUERY_STATUS, **overrides) -> RouterResult:
    data = {
        "intent": intent,
        "confidence": 0.95,
        "input_type": InputType.TEXT,
        "target_type": TargetType.ACCOUNT,
        "target_id": 1,
        "extracted_params": {"account_id": 1},
        "can_execute": True,
    }
    data.update(overrides)
    return RouterResult(**data)


def _plan_for_step(step: PlanStep, **overrides) -> Plan:
    data = {
        "intent": Intent.QUERY_STATUS,
        "steps": [step],
        "confirmation_requirement": ConfirmationRequirement.NONE,
        "can_execute": True,
    }
    data.update(overrides)
    return Plan(**data)


def test_execute_readonly_endpoint_exists():
    response = _post(_base_payload())

    assert response.status_code == 200
    assert response.json()["status"] == "NEED_CLARIFICATION"


def test_missing_account_id_returns_need_clarification_and_does_not_call_llm():
    db = SessionLocal()
    try:
        service, llm = _service_with_fake_llm(db)
        data = _post_with_service(service, _base_payload(account_id=None)).json()
    finally:
        db.close()

    assert data["status"] == "NEED_CLARIFICATION"
    assert data["can_execute"] is False
    assert llm.calls == []


def test_nonexistent_account_returns_failed_business_error():
    data = _post(_base_payload(account_id=999999999)).json()

    assert data["status"] == "FAILED"
    assert data["metadata"]["execution"]["mode"] == "REAL"
    assert data["metadata"]["execution"]["step_results"][0]["action"] == "QUERY_ACCOUNT_PROFILE"
    assert data["metadata"]["execution"]["step_results"][0]["status"] == "FAILED"


def test_existing_account_returns_success_with_business_result_and_real_trace():
    account_id = _create_account()
    data = _post(_base_payload(account_id=account_id)).json()

    assert data["status"] == "SUCCESS"
    assert data["metadata"]["execution"]["mode"] == "REAL"
    assert data["metadata"]["execution"]["step_results"][0]["action"] == "QUERY_ACCOUNT_PROFILE"
    assert data["metadata"]["business_result"]["account_id"] == account_id
    assert data["metadata"]["business_result"]["account_name"] == "7.1 只读测试账号"
    stages = [event["stage"] for event in data["metadata"]["entry_trace"]["events"]]
    assert "EXECUTION_STARTED" in stages
    assert "STEP_EXECUTION_FINISHED" in stages
    assert "EXECUTION_FINISHED" in stages


def test_readonly_registry_only_registers_query_account_profile_not_generate_draft():
    db = SessionLocal()
    try:
        registry = build_readonly_action_handler_registry(db)
    finally:
        db.close()

    assert registry.is_registered(Action.NOOP)
    assert registry.is_registered(Action.ASK_CLARIFICATION)
    assert registry.is_registered(Action.QUERY_ACCOUNT_PROFILE)
    assert not registry.is_registered(Action.GENERATE_DRAFT)


def test_generate_draft_is_not_real_executed():
    db = SessionLocal()
    try:
        service = AgentChatReadonlyExecuteService(
            router=FakeRouter(_router_result(intent=Intent.GENERATE_DRAFT)),
            planner=FakePlanner(
                _plan_for_step(
                    PlanStep(
                        step_no=1,
                        action=Action.GENERATE_DRAFT,
                        description="尝试生成草稿",
                        input_params={"account_id": 1, "topic": "测试"},
                        allowed_effect=AllowedEffect.LOCAL_GENERATION,
                        can_execute=True,
                    ),
                    intent=Intent.GENERATE_DRAFT,
                )
            ),
            db=db,
        )
        data = _post_with_service(service, _base_payload(account_id=1, text="帮我生成草稿")).json()
    finally:
        db.close()

    assert data["status"] == "BLOCKED"
    assert data["metadata"]["execution"]["mode"] == "REAL"
    assert data["metadata"]["execution"]["error_code"] == "HANDLER_NOT_REGISTERED"


def test_external_write_remains_blocked():
    db = SessionLocal()
    try:
        service = AgentChatReadonlyExecuteService(
            router=FakeRouter(_router_result()),
            planner=FakePlanner(
                _plan_for_step(
                    PlanStep(
                        step_no=1,
                        action=Action.NOOP,
                        description="外部写入应被阻断",
                        input_params={"account_id": 1},
                        allowed_effect=AllowedEffect.EXTERNAL_WRITE,
                        can_execute=True,
                    )
                )
            ),
            db=db,
        )
        data = _post_with_service(service, _base_payload(account_id=1)).json()
    finally:
        db.close()

    assert data["status"] == "BLOCKED"
    assert "EXTERNAL_WRITE" in data["plan_validation"]["risk_flags"]


def test_confirmation_required_action_is_not_executed():
    db = SessionLocal()
    try:
        service = AgentChatReadonlyExecuteService(
            router=FakeRouter(_router_result()),
            planner=FakePlanner(
                _plan_for_step(
                    PlanStep(
                        step_no=1,
                        action=Action.NOOP,
                        description="需要确认",
                        allowed_effect=AllowedEffect.READ_ONLY,
                        requires_confirmation=True,
                        can_execute=True,
                    ),
                    confirmation_requirement=ConfirmationRequirement.USER_CONFIRM_REQUIRED,
                )
            ),
            db=db,
        )
        data = _post_with_service(service, _base_payload(account_id=1)).json()
    finally:
        db.close()

    assert data["status"] == "WAITING_CONFIRMATION"
    assert data["metadata"]["execution"]["step_results"] == []


def test_readonly_query_does_not_write_database_except_test_setup():
    account_id = _create_account()
    db = SessionLocal()
    try:
        before = len(AccountProfileService(db).list_accounts())
        data = _post(_base_payload(account_id=account_id)).json()
        after = len(AccountProfileService(db).list_accounts())
    finally:
        db.close()

    assert data["status"] == "SUCCESS"
    assert after == before
