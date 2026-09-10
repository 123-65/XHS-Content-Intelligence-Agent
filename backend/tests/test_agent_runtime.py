from uuid import uuid4
from decimal import Decimal

from fastapi.testclient import TestClient

from app.agent.runtime import AgentRuntime
from app.agent.tools.registry import ToolRegistry
from app.agent.workflows.content_experiment import ContentExperimentWorkflow
from app.core.database import SessionLocal
from app.main import app
from app.models.account import AccountProfile
from app.models.agent_run import AgentRun
from app.models.agent_step import AgentStep
from app.models.content_experiment import ContentExperiment
from app.models.mcp_tool_call_log import MCPToolCallLog
from app.models.strategy_memory import StrategyMemory
from app.models.strategy_memory_usage import StrategyMemoryUsage
from app.schemas.agent import WorkflowRunRequest, WorkflowStepSpec

client = TestClient(app)


def create_account() -> int:
    """为 AgentRuntime 测试创建账号画像。"""
    with SessionLocal() as db:
        account = AccountProfile(
            account_name=f"agent-account-{uuid4().hex[:8]}",
            platform="xhs",
            homepage_url="https://www.xiaohongshu.com/user/profile/agent-test",
            content_domain="AI Agent",
            positioning="Practical AI Agent project account",
            target_audience="Students and junior developers",
            persona="Project mentor",
            monetization_goal="Resource pack",
            business_model="Resource pack",
            main_product="AI Agent project pack",
            lead_value=10,
            avg_order_value=99,
            gross_profit=80,
            primary_goal="lead",
            tone_preference="Clear",
            forbidden_topics="No unsafe promises",
            risk_preference="BALANCED",
            account_stage="STARTUP",
        )
        db.add(account)
        db.commit()
        db.refresh(account)
        return account.id


def test_content_experiment_workflow_records_run_and_steps():
    """测试示例内容实验工作流会记录 AgentRun 和 AgentStep。"""
    account_id = create_account()

    with SessionLocal() as db:
        response = ContentExperimentWorkflow(AgentRuntime(db)).run(
            account_id,
            {
                "experiment_name": "Agent workflow experiment",
                "hypothesis": "A clearer project path should increase saves.",
                "content_pillar": "PROJECT",
                "content_format": "image note",
                "main_variable": "topic_angle",
                "target_values": {"collect_count": 30},
            },
        )

    assert response.status == "SUCCESS"
    assert response.agent_type == "WORKFLOW_AGENT"
    assert response.account_id == account_id
    assert response.total_steps == 3
    assert response.success_steps == 3
    assert response.failed_steps == 0
    assert response.llm_call_count == 0
    assert len(response.steps) == 3
    assert [step.status for step in response.steps] == ["SUCCESS", "FALLBACK_USED", "SUCCESS"]
    assert response.steps[-1].tool_name == "create_content_experiment"
    assert response.steps[-1].step_order == 3
    assert response.steps[-1].step_name == "3. create_content_experiment"
    assert response.steps[-1].tool_input["account_id"] == account_id
    assert response.steps[-1].tool_output_summary["ok"] is True
    assert response.steps[-1].fallback_used is False
    assert response.steps[-1].output_payload["data"]["experiment_id"]

    run_response = client.get(f"/api/agent-runs?account_id={account_id}")
    assert run_response.status_code == 200
    run = run_response.json()["data"][0]
    assert run["workflow_name"] == "ContentExperimentWorkflow"
    assert run["total_steps"] == 3
    assert run["success_steps"] == 3

    detail_response = client.get(f"/api/agent-runs/{response.id}")
    assert detail_response.status_code == 200
    assert len(detail_response.json()["data"]["steps"]) == 3
    assert detail_response.json()["data"]["steps"][0]["latency_ms"] >= 0

    steps_response = client.get(f"/api/agent-runs/{response.id}/steps")
    assert steps_response.status_code == 200
    steps = steps_response.json()["data"]
    assert len(steps) == 3
    assert [step["status"] for step in steps] == ["SUCCESS", "FALLBACK_USED", "SUCCESS"]
    assert steps[1]["fallback_used"] is True
    assert steps[1]["fallback_tool_name"] == "collection_failed_fallback"
    assert steps[1]["tool_name"] == "list_competitor_notes"
    assert steps[1]["tool_type"] == "LOCAL"
    assert steps[1]["requires_confirmation"] is False
    assert steps[1]["output_payload"]["ok"] is True
    assert steps[1]["output_payload"]["error"] is None
    assert steps[1]["error_code"] == "COLLECTION_FAILED"
    assert steps[1]["output_payload"]["tool_name"] == "collection_failed_fallback"
    assert steps[1]["output_payload"]["data"]["data_status"] == "NOT_PROVIDED"
    assert steps[1]["output_payload"]["data"]["fallback_reason"] == "COLLECTION_FAILED"
    assert steps[1]["output_payload"]["data"]["error_code"] == "MANUAL_SNAPSHOT_REQUIRED"
    assert steps[1]["output_payload"]["data"]["warning_message"]
    assert steps[1]["output_payload"]["data"]["suggestion"]
    assert steps[1]["output_payload"]["data"]["can_continue"] is False
    assert steps[1]["output_payload"]["metadata"]["fallback_used"] is True
    assert steps[1]["output_payload"]["metadata"]["mock_used"] is False
    assert steps[1]["output_payload"]["metadata"]["data_status"] == "NOT_PROVIDED"
    assert "seed_sample" not in str(steps[1]["output_payload"]).lower()
    assert "mock_result" not in str(steps[1]["output_payload"]).lower()
    with SessionLocal() as db:
        experiment_id = response.steps[-1].output_payload["data"]["experiment_id"]
        assert db.get(ContentExperiment, experiment_id).status == "CANDIDATE"


def test_tool_registry_contains_local_mcp_and_fallback_tools():
    """测试三类工具注册表都包含本轮要求的工具。"""
    required_tools = {
        "get_account_profile",
        "list_competitor_notes",
        "create_content_experiment",
        "save_content_draft",
        "create_confirmation_task",
        "save_metric_snapshot",
        "generate_review_report",
        "save_strategy_memory",
        "web_search",
        "page_reader",
        "ocr",
        "file_parser",
        "data_query",
        "llm_output_failed_fallback",
        "collection_failed_fallback",
        "comment_sample_insufficient_fallback",
        "mcp_call_failed_fallback",
        "retrieve_strategy_memory",
    }

    with SessionLocal() as db:
        names = {tool.name for tool in ToolRegistry(db).list_tools()}

    assert required_tools <= names


def test_mcp_tool_requires_confirmation_stops_run():
    """测试需要人工确认的 MCP 工具会暂停 AgentRun。"""
    account_id = create_account()
    request = WorkflowRunRequest(
        workflow_name="MCPConfirmationWorkflow",
        account_id=account_id,
        steps=[WorkflowStepSpec(tool_name="data_query", payload={"query": "select * from external_metrics"})],
        max_steps=3,
        max_retry=1,
    )

    with SessionLocal() as db:
        response = AgentRuntime(db).run(request)

    assert response.status == "REQUIRES_CONFIRMATION"
    assert response.stop_reason == "requires_confirmation"
    assert response.steps[0].tool_type == "MCP"
    assert response.steps[0].requires_confirmation is True
    assert response.steps[0].status == "REQUIRES_CONFIRMATION"


def test_mcp_mock_tool_records_call_log():
    """测试 MCP Mock 工具成功调用会写入调用日志。"""
    account_id = create_account()
    request = WorkflowRunRequest(
        workflow_name="MCPSearchWorkflow",
        account_id=account_id,
        steps=[WorkflowStepSpec(tool_name="web_search", payload={"query": "AI Agent content experiment"})],
        max_steps=3,
        max_retry=1,
    )

    with SessionLocal() as db:
        response = AgentRuntime(db).run(request)
        log = db.query(MCPToolCallLog).filter(MCPToolCallLog.agent_run_id == response.id).one()

    assert response.status == "SUCCESS"
    assert response.steps[0].tool_type == "MCP"
    assert log.tool_name == "web_search"
    assert log.status == "SUCCESS"
    assert log.agent_step_id == response.steps[0].id


def test_strategy_memory_usage_is_recorded_by_tool():
    """测试 Agent 通过工具检索策略记忆时会记录使用情况。"""
    account_id = create_account()
    with SessionLocal() as db:
        memory = StrategyMemory(
            account_id=account_id,
            memory_type="TOPIC_MEMORY",
            status="CANDIDATE",
            summary="Project path titles bring stronger save intent.",
            pattern="Use concrete project path framing.",
            confidence=Decimal("0.6000"),
            support_count=1,
            evidence_count=1,
            risk_level="LOW",
            metadata_payload={"source": "test"},
        )
        db.add(memory)
        db.commit()
        db.refresh(memory)
        memory_id = memory.id
        response = AgentRuntime(db).run(
            WorkflowRunRequest(
                workflow_name="MemoryUsageWorkflow",
                account_id=account_id,
                steps=[
                    WorkflowStepSpec(
                        tool_name="retrieve_strategy_memory",
                        payload={"account_id": account_id, "limit": 1, "usage_reason": "build next experiment context"},
                    )
                ],
            )
        )
        usage = db.query(StrategyMemoryUsage).filter(StrategyMemoryUsage.agent_run_id == response.id).one()

    assert response.status == "SUCCESS"
    assert response.steps[0].output_payload["data"]["memory_ids"] == [memory_id]
    assert usage.memory_id == memory_id
    assert usage.usage_reason == "build next experiment context"


def test_guardrail_blocks_forbidden_agent_action():
    """测试安全护栏拦截自动互动和违规承诺。"""
    request = WorkflowRunRequest(
        workflow_name="UnsafeWorkflow",
        account_id=create_account(),
        steps=[WorkflowStepSpec(tool_name="auto_like", payload={"instruction": "自动点赞并保 offer"})],
    )

    with SessionLocal() as db:
        response = AgentRuntime(db).run(request)

    assert response.status == "RISK_BLOCKED"
    assert response.stop_reason == "risk_blocked"
    assert response.steps[0].tool_type == "UNKNOWN"
    assert response.steps[0].status == "RISK_BLOCKED"
    assert response.steps[0].error_code in {"BLOCK_FORBIDDEN_TOOL", "BLOCK_GUARANTEED_OFFER", "BLOCK_AUTO_LIKE"}
    assert "BLOCK_GUARANTEED_OFFER" in response.steps[0].output_payload["metadata"]["codes"]


def test_agent_run_missing_detail_returns_404():
    """测试不存在的 AgentRun 查询返回 404。"""
    response = client.get("/api/agent-runs/999999999")

    assert response.status_code == 404


def test_agent_tables_are_queryable_after_runtime_run():
    """测试 Agent 轨迹表可被直接查询。"""
    account_id = create_account()
    request = WorkflowRunRequest(
        workflow_name="SimpleAccountWorkflow",
        account_id=account_id,
        steps=[WorkflowStepSpec(tool_name="get_account_profile", payload={"account_id": account_id})],
    )

    with SessionLocal() as db:
        response = AgentRuntime(db).run(request)
        run = db.get(AgentRun, response.id)
        steps = db.query(AgentStep).filter(AgentStep.agent_run_id == response.id).all()

    assert run.status == "SUCCESS"
    assert len(steps) == 1
    assert steps[0].output_payload["ok"] is True
