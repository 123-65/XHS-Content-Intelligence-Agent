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
from app.models.competitor_comment import CompetitorComment
from app.models.competitors_analysis import CompetitorAnalysisReport
from app.models.content_opportunity import ContentOpportunity
from app.models.strategy_memory import StrategyMemory
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


def _router_result(intent=Intent.QUERY_STATUS, account_id: int = 1, **overrides) -> RouterResult:
    data = {
        "intent": intent,
        "confidence": 0.95,
        "input_type": InputType.TEXT,
        "target_type": TargetType.ACCOUNT,
        "target_id": account_id,
        "extracted_params": {"account_id": account_id},
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


def _readonly_plan_for_action(action: Action, account_id: int) -> Plan:
    return _plan_for_step(
        PlanStep(
            step_no=1,
            action=action,
            description=f"readonly {action.value}",
            input_params={"account_id": account_id},
            allowed_effect=AllowedEffect.READ_ONLY,
            can_execute=True,
        )
    )


def _execute_fake_readonly_action(action: Action, account_id: int) -> dict:
    db = SessionLocal()
    try:
        service = AgentChatReadonlyExecuteService(
            router=FakeRouter(_router_result(account_id=account_id)),
            planner=FakePlanner(_readonly_plan_for_action(action, account_id)),
            db=db,
        )
        return _post_with_service(service, _base_payload(account_id=account_id, text=action.value)).json()
    finally:
        db.close()


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


def test_query_competitor_evidence_can_real_execute_with_empty_result():
    account_id = _create_account()
    data = _execute_fake_readonly_action(Action.QUERY_COMPETITOR_EVIDENCE, account_id)

    assert data["status"] == "SUCCESS"
    assert data["metadata"]["execution"]["mode"] == "REAL"
    assert data["metadata"]["execution"]["step_results"][0]["action"] == "QUERY_COMPETITOR_EVIDENCE"
    result = data["metadata"]["business_result"]["competitor_evidence"]
    assert result["items"] == []
    assert result["total"] == 0
    assert result["data_status"] == "NOT_PROVIDED"
    stages = [event["stage"] for event in data["metadata"]["entry_trace"]["events"]]
    assert "EXECUTION_STARTED" in stages
    assert "STEP_EXECUTION_FINISHED" in stages
    assert "EXECUTION_FINISHED" in stages


def test_query_comment_insight_can_real_execute_with_empty_result():
    account_id = _create_account()
    data = _execute_fake_readonly_action(Action.QUERY_COMMENT_INSIGHT, account_id)

    assert data["status"] == "SUCCESS"
    assert data["metadata"]["execution"]["mode"] == "REAL"
    assert data["metadata"]["execution"]["step_results"][0]["action"] == "QUERY_COMMENT_INSIGHT"
    result = data["metadata"]["business_result"]["comment_insight"]
    assert result["representative_comments"] == []
    assert result["data_status"] == "NOT_PROVIDED"


def test_query_strategy_memory_can_real_execute_with_empty_result():
    account_id = _create_account()
    data = _execute_fake_readonly_action(Action.QUERY_STRATEGY_MEMORY, account_id)

    assert data["status"] == "SUCCESS"
    assert data["metadata"]["execution"]["mode"] == "REAL"
    assert data["metadata"]["execution"]["step_results"][0]["action"] == "QUERY_STRATEGY_MEMORY"
    result = data["metadata"]["business_result"]["strategy_memory"]
    assert result["items"] == []
    assert result["total"] == 0
    assert result["data_status"] == "NOT_PROVIDED"


def test_context_evidence_text_routes_and_plans_without_calling_real_model():
    account_id = _create_account()
    db = SessionLocal()
    try:
        service, llm = _service_with_fake_llm(db)
        data = _post_with_service(
            service,
            _base_payload(account_id=account_id, text="查看这个账号最近能用于写作的上下文证据"),
        ).json()
    finally:
        db.close()

    assert data["status"] == "SUCCESS"
    assert llm.calls == []
    actions = [step["action"] for step in data["metadata"]["execution"]["step_results"]]
    assert actions == ["QUERY_COMPETITOR_EVIDENCE", "QUERY_COMMENT_INSIGHT", "QUERY_STRATEGY_MEMORY"]
    assert data["metadata"]["business_result"]["competitor_evidence"]["data_status"] == "NOT_PROVIDED"
    assert data["metadata"]["business_result"]["comment_insight"]["data_status"] == "NOT_PROVIDED"
    assert data["metadata"]["business_result"]["strategy_memory"]["data_status"] == "NOT_PROVIDED"


def test_readonly_registry_registers_only_safe_readonly_actions_not_generation_or_memory_write():
    db = SessionLocal()
    try:
        registry = build_readonly_action_handler_registry(db)
    finally:
        db.close()

    assert registry.is_registered(Action.NOOP)
    assert registry.is_registered(Action.ASK_CLARIFICATION)
    assert registry.is_registered(Action.QUERY_ACCOUNT_PROFILE)
    assert registry.is_registered(Action.QUERY_COMPETITOR_EVIDENCE)
    assert registry.is_registered(Action.QUERY_COMMENT_INSIGHT)
    assert registry.is_registered(Action.QUERY_STRATEGY_MEMORY)
    assert not registry.is_registered(Action.GENERATE_DRAFT)
    assert not registry.is_registered(Action.REVIEW_DRAFT)
    assert not registry.is_registered(Action.GENERATE_CONTENT_OPPORTUNITY)
    assert not registry.is_registered(Action.CREATE_CONTENT_EXPERIMENT)
    assert not registry.is_registered(Action.CREATE_CANDIDATE_MEMORY)


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


def test_create_candidate_memory_cannot_execute_in_execute_readonly():
    db = SessionLocal()
    try:
        service = AgentChatReadonlyExecuteService(
            router=FakeRouter(_router_result()),
            planner=FakePlanner(
                _plan_for_step(
                    PlanStep(
                        step_no=1,
                        action=Action.CREATE_CANDIDATE_MEMORY,
                        description="不应在只读入口写候选记忆",
                        input_params={"account_id": 1, "memory_content": "用户不喜欢功利标题", "source": "user_feedback"},
                        allowed_effect=AllowedEffect.LOCAL_WRITE,
                        can_execute=True,
                    )
                )
            ),
            db=db,
        )
        data = _post_with_service(service, _base_payload(account_id=1, text="记住我不喜欢功利标题")).json()
    finally:
        db.close()

    assert data["status"] in {"WAITING_CONFIRMATION", "BLOCKED"}
    assert data["metadata"]["execution"]["mode"] == "REAL"
    assert data["metadata"]["execution"]["step_results"] == []
    assert "NEEDS_HUMAN_CONFIRMATION" in data["plan_validation"]["risk_flags"]


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


def test_destructive_action_remains_blocked():
    db = SessionLocal()
    try:
        service = AgentChatReadonlyExecuteService(
            router=FakeRouter(_router_result()),
            planner=FakePlanner(
                _plan_for_step(
                    PlanStep(
                        step_no=1,
                        action=Action.NOOP,
                        description="破坏性动作应被阻断",
                        input_params={"account_id": 1},
                        allowed_effect=AllowedEffect.DESTRUCTIVE,
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
    assert "DESTRUCTIVE_ACTION" in data["plan_validation"]["risk_flags"]


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
        before_reports = db.query(CompetitorAnalysisReport).count()
        before_opportunities = db.query(ContentOpportunity).count()
        before_comments = db.query(CompetitorComment).count()
        before_memories = db.query(StrategyMemory).count()
        data = _execute_fake_readonly_action(Action.QUERY_COMPETITOR_EVIDENCE, account_id)
        after = len(AccountProfileService(db).list_accounts())
        after_reports = db.query(CompetitorAnalysisReport).count()
        after_opportunities = db.query(ContentOpportunity).count()
        after_comments = db.query(CompetitorComment).count()
        after_memories = db.query(StrategyMemory).count()
    finally:
        db.close()

    assert data["status"] == "SUCCESS"
    assert after == before
    assert after_reports == before_reports
    assert after_opportunities == before_opportunities
    assert after_comments == before_comments
    assert after_memories == before_memories
