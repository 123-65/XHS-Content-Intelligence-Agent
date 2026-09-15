from decimal import Decimal

from fastapi.testclient import TestClient

from app.agent.product_entry.business_handlers import build_readonly_action_handler_registry
from app.agent.product_entry.chat_service import AgentChatReadonlyExecuteService
from app.agent.product_entry.llm_router import LLMUserInputRouter
from app.agent.product_entry.registry import UNSUPPORTED_ACTION_REGISTRY
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
from app.models.competitor_note import CompetitorNote
from app.models.competitors_analysis import CompetitorAnalysisReport
from app.models.content_draft import ContentDraft
from app.models.content_experiment import ContentExperiment
from app.models.content_opportunity import ContentOpportunity
from app.models.context_snapshot import ContextSnapshot
from app.models.prompt_run_log import PromptRunLog
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


def _preview_context_plan(account_id: int, experiment_id: int | None = None, user_requirement: str | None = None) -> Plan:
    input_params = {"account_id": account_id}
    if experiment_id is not None:
        input_params["experiment_id"] = experiment_id
    if user_requirement:
        input_params["user_requirement"] = user_requirement
    return _plan_for_step(
        PlanStep(
            step_no=1,
            action=Action.PREVIEW_DRAFT_CONTEXT,
            description="readonly PREVIEW_DRAFT_CONTEXT",
            input_params=input_params,
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


def _execute_preview_context(account_id: int, experiment_id: int | None, user_requirement: str | None = None) -> dict:
    db = SessionLocal()
    try:
        router_result = _router_result(
            account_id=account_id,
            extracted_params={
                "account_id": account_id,
                "experiment_id": experiment_id,
                "readonly_actions": [Action.PREVIEW_DRAFT_CONTEXT.value],
            },
        )
        service = AgentChatReadonlyExecuteService(
            router=FakeRouter(router_result),
            planner=FakePlanner(_preview_context_plan(account_id, experiment_id, user_requirement)),
            db=db,
        )
        return _post_with_service(
            service,
            _base_payload(
                account_id=account_id,
                text="预览草稿上下文",
                context={"experiment_id": experiment_id} if experiment_id is not None else {},
            ),
        ).json()
    finally:
        db.close()


def _create_draft_context_fixture(status: str = "APPROVED", with_context: bool = False, account_id: int | None = None) -> tuple[int, int]:
    account_id = account_id or _create_account()
    db = SessionLocal()
    try:
        report = None
        opportunity = None
        if with_context:
            note = CompetitorNote(
                account_id=account_id,
                note_id="note-7-3",
                note_url="https://www.xiaohongshu.com/explore/note-7-3",
                author_name="工程求职同学",
                title="普通本科如何做 Agent 项目",
                content="用真实项目拆解学习路线更容易被收藏。",
                tags=["Agent", "求职"],
                like_count=120,
                collect_count=60,
                comment_count=8,
                source_type="XHS_PUBLIC_READONLY",
                provider_name="manual",
                is_mock=False,
                confidence=0.9,
                raw_snapshot={"source": "test_fixture"},
            )
            db.add(note)
            db.flush()
            report = CompetitorAnalysisReport(
                account_id=account_id,
                name="7.3 草稿上下文报告",
                keyword="Agent 求职",
                source_type="COMPETITOR",
                target_metric="engagement",
                note_snapshot_ids=[],
                competitor_account_ids=[],
                competitor_note_ids=[note.id],
                note_count=1,
                comment_count=3,
                persona_patterns=[],
                content_pillars=[{"name": "Agent 求职"}],
                top_tags=[],
                title_patterns=[],
                cover_patterns=[],
                content_structures=[],
                comment_demands=[{"type": "学习路线", "count": 3, "examples": ["想知道路线"]}],
                conversion_signals=[{"name": "咨询课程", "count": 2}],
                replicability_summary={},
                risk_points=[{"name": "避免承诺 offer", "count": 1}],
                high_performance_notes=[],
                content_insights=["工程拆解更受欢迎"],
                suggestions=["用真实项目路径"],
                summary="竞品报告摘要",
                status="SUCCESS",
            )
            db.add(report)
            db.flush()
            opportunity = ContentOpportunity(
                report_id=report.id,
                opportunity_title="普通本科 Agent 项目路线",
                suggested_angle="从项目拆解讲学习路线",
                target_audience="AI 应用工程新人",
                content_pillar="Agent 求职",
                comment_demand_type="学习路线",
                evidence_summary="评论集中问学习路线",
                replicability_score=80,
                risk_level="LOW",
                risk_points=["避免保 offer"],
                opportunity_score=90,
            )
            db.add(opportunity)
            db.flush()
            db.add(
                CompetitorComment(
                    account_id=account_id,
                    competitor_note_id=note.id,
                    comment_id="c-7-3",
                    user_name="用户A",
                    content="想知道普通本科怎么做 Agent 项目",
                    like_count=9,
                    source_type="XHS_PUBLIC_READONLY",
                    provider_name="manual",
                    is_mock=False,
                    confidence=0.9,
                    raw_snapshot={"demand_type": "学习路线"},
                )
            )
            db.add(
                StrategyMemory(
                    account_id=account_id,
                    memory_type="TITLE_MEMORY",
                    status="VALIDATED",
                    summary="标题要具体到普通本科项目场景",
                    pattern="人群 + 项目阶段 + 具体收益",
                    confidence=Decimal("0.8000"),
                    support_count=2,
                    evidence_count=1,
                    risk_level="LOW",
                    metadata_payload={"content_pillar": "Agent 求职", "verified": True},
                )
            )

        experiment = ContentExperiment(
            account_id=account_id,
            analysis_report_id=report.id if report else None,
            content_opportunity_id=opportunity.id if opportunity else None,
            experiment_name="7.3 草稿上下文实验",
            hypothesis="普通本科项目路线能提升收藏。",
            content_pillar="Agent 求职",
            content_format="图文笔记",
            main_variable="标题角度",
            control_variables=[],
            primary_metric="collect",
            secondary_metrics=["comment"],
            success_criteria={"collect": 50},
            failure_criteria={"collect": 10},
            fallback_strategy="改成更具体的项目拆解",
            risk_level="LOW",
            target_metric="collect",
            expected_result="收藏提升",
            topic_angle="普通本科 Agent 项目路线",
            selected_topic="普通本科如何做 Agent 项目",
            target_values={"collect": 50},
            source_type="COMPETITOR_ANALYSIS",
            status=status,
        )
        db.add(experiment)
        db.commit()
        db.refresh(experiment)
        return account_id, experiment.id
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


def test_preview_draft_context_can_be_triggered_through_execute_readonly():
    account_id, experiment_id = _create_draft_context_fixture(with_context=True)
    data = _execute_preview_context(account_id, experiment_id, user_requirement="更自然，不要太功利")

    assert data["status"] == "SUCCESS"
    assert data["metadata"]["execution"]["mode"] == "REAL"
    assert data["metadata"]["execution"]["step_results"][0]["action"] == "PREVIEW_DRAFT_CONTEXT"
    result = data["metadata"]["business_result"]["draft_context_preview"]
    assert result["account_id"] == account_id
    assert result["experiment_id"] == experiment_id
    assert result["can_generate_draft"] is True
    assert result["slot_count"] >= 7
    slot_names = {slot["name"] for slot in result["slots"]}
    assert "ACCOUNT_PROFILE" in slot_names
    assert "WORKFLOW_STATE" in slot_names
    assert "COMPETITOR_EVIDENCE" in slot_names
    assert "COMMENT_INSIGHT" in slot_names
    assert "STRATEGY_MEMORY" in slot_names
    assert any(slot["trust_level"] == "untrusted" for slot in result["slots"])
    stages = [event["stage"] for event in data["metadata"]["entry_trace"]["events"]]
    assert "EXECUTION_STARTED" in stages
    assert "STEP_EXECUTION_STARTED" in stages
    assert "STEP_EXECUTION_FINISHED" in stages
    assert "EXECUTION_FINISHED" in stages


def test_preview_draft_context_missing_account_id_returns_need_clarification():
    db = SessionLocal()
    try:
        service, llm = _service_with_fake_llm(db)
        data = _post_with_service(
            service,
            _base_payload(account_id=None, text="预览草稿上下文", context={"experiment_id": 1}),
        ).json()
    finally:
        db.close()

    assert data["status"] == "NEED_CLARIFICATION"
    assert "account_id" in data["router_result"]["missing_params"]
    assert llm.calls == []


def test_preview_draft_context_missing_experiment_id_returns_need_clarification():
    account_id = _create_account()
    db = SessionLocal()
    try:
        service, llm = _service_with_fake_llm(db)
        data = _post_with_service(
            service,
            _base_payload(account_id=account_id, text="预览草稿上下文", context={}),
        ).json()
    finally:
        db.close()

    assert data["status"] == "NEED_CLARIFICATION"
    assert "experiment_id" in data["router_result"]["missing_params"]
    assert llm.calls == []


def test_preview_draft_context_nonexistent_experiment_returns_failed():
    account_id = _create_account()
    data = _execute_preview_context(account_id, 999999999)

    assert data["status"] == "FAILED"
    assert data["metadata"]["execution"]["mode"] == "REAL"
    assert data["metadata"]["execution"]["step_results"][0]["status"] == "FAILED"
    assert data["metadata"]["execution"]["step_results"][0]["error_code"] == "HANDLER_FAILED"


def test_preview_draft_context_experiment_account_mismatch_fails():
    owner_account_id, experiment_id = _create_draft_context_fixture(with_context=False)
    other_account_id = _create_account()
    assert other_account_id != owner_account_id

    data = _execute_preview_context(other_account_id, experiment_id)

    assert data["status"] == "FAILED"
    assert data["metadata"]["execution"]["step_results"][0]["status"] == "FAILED"
    assert "does not belong" in data["metadata"]["execution"]["step_results"][0]["message"]


def test_preview_draft_context_unapproved_experiment_returns_block_reason_without_draft():
    account_id, experiment_id = _create_draft_context_fixture(status="DRAFT", with_context=True)
    db = SessionLocal()
    try:
        before_drafts = db.query(ContentDraft).count()
    finally:
        db.close()
    data = _execute_preview_context(account_id, experiment_id)
    db = SessionLocal()
    try:
        after_drafts = db.query(ContentDraft).count()
    finally:
        db.close()

    result = data["metadata"]["business_result"]["draft_context_preview"]
    assert data["status"] == "SUCCESS"
    assert result["can_generate_draft"] is False
    assert result["block_reason"] == "experiment is not APPROVED"
    assert "EXPERIMENT_NOT_APPROVED" in result["risk_flags"]
    assert after_drafts == before_drafts


def test_preview_draft_context_does_not_call_llm_or_write_draft_prompt_or_context_snapshot():
    account_id, experiment_id = _create_draft_context_fixture(with_context=True)
    db = SessionLocal()
    try:
        service, llm = _service_with_fake_llm(db)
        before_drafts = db.query(ContentDraft).count()
        before_prompt_runs = db.query(PromptRunLog).count()
        before_context_snapshots = db.query(ContextSnapshot).count()
        data = _post_with_service(
            service,
            _base_payload(
                account_id=account_id,
                text="预览草稿上下文",
                context={"experiment_id": experiment_id, "user_requirement": "别太像广告"},
            ),
        ).json()
        after_drafts = db.query(ContentDraft).count()
        after_prompt_runs = db.query(PromptRunLog).count()
        after_context_snapshots = db.query(ContextSnapshot).count()
    finally:
        db.close()

    assert data["status"] == "SUCCESS"
    assert data["metadata"]["execution"]["mode"] == "REAL"
    assert llm.calls == []
    assert after_drafts == before_drafts
    assert after_prompt_runs == before_prompt_runs
    assert after_context_snapshots == before_context_snapshots


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
    assert registry.is_registered(Action.PREVIEW_DRAFT_CONTEXT)
    assert not registry.is_registered(Action.GENERATE_DRAFT)
    assert not registry.is_registered(Action.REVIEW_DRAFT)
    assert not registry.is_registered(Action.GENERATE_CONTENT_OPPORTUNITY)
    assert not registry.is_registered(Action.CREATE_CONTENT_EXPERIMENT)
    assert not registry.is_registered(Action.CREATE_CANDIDATE_MEMORY)
    for action_name in ["AUTO_PUBLISH_XHS", "AUTO_REPLY_COMMENT", "DELETE_NOTE", "MODIFY_EXTERNAL_ACCOUNT"]:
        assert action_name in UNSUPPORTED_ACTION_REGISTRY
        assert UNSUPPORTED_ACTION_REGISTRY[action_name].supported_in_current_stage is False


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
