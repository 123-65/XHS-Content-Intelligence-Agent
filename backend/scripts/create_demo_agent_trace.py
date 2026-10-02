"""Create a mock-only AgentRun trace for the developer console."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.context.context_builder import ContextManager
from app.context.context_slots import ContextRole, ContextSlot, ContextSlotName
from app.context.context_usage_logger import ContextUsageLogger
from app.core.database import SessionLocal
from app.enums.agent import AgentStepStatus
from app.repositories.agent_run_repo import AgentRunRepository
from app.models.prompt_run_log import PromptRunLog
from app.schemas.agent import AgentRunCreate, AgentStepCreate


def create_demo_agent_trace() -> int:
    """Create a demo AgentRun with tool, LLM, MCP, and fallback records."""
    with SessionLocal() as db:
        repo = AgentRunRepository(db)
        run = repo.create_run(
            AgentRunCreate(
                account_id=None,
                workflow_name="DemoDeveloperTraceWorkflow",
                agent_type="WORKFLOW_AGENT",
                input_payload={"demo": True, "source": "scripts/create_demo_agent_trace.py"},
                max_steps=4,
                max_retry=1,
            )
        )

        step1 = repo.create_step(
            AgentStepCreate(
                agent_run_id=run.id,
                step_index=0,
                tool_name="get_account_profile",
                tool_type="LOCAL",
                input_payload={"account_id": "demo"},
            )
        )
        repo.finish_step(step1, AgentStepStatus.SUCCESS.value, {"ok": True, "tool_name": "get_account_profile", "data": {"account_name": "Demo account"}, "metadata": {"mock": True}})

        step2 = repo.create_step(
            AgentStepCreate(
                agent_run_id=run.id,
                step_index=1,
                tool_name="web_search",
                tool_type="MCP",
                input_payload={"query": "AI Agent content growth demo"},
            )
        )
        mcp_result = {"ok": True, "tool_name": "web_search", "data": {"results": [{"title": "mock result", "url": "mock://demo"}]}, "metadata": {"tool_name": "web_search", "mock": True}}
        repo.record_mcp_call(
            {
                "agent_run_id": run.id,
                "agent_step_id": step2.id,
                "server_config_id": None,
                "tool_name": "web_search",
                "status": "SUCCESS",
                "input_payload": {"query": "AI Agent content growth demo"},
                "output_payload": mcp_result,
                "error_message": None,
                "latency_ms": 18,
                "risk_level": "LOW",
                "requires_confirmation": False,
            }
        )
        repo.finish_step(step2, AgentStepStatus.SUCCESS.value, mcp_result)

        step3 = repo.create_step(
            AgentStepCreate(
                agent_run_id=run.id,
                step_index=2,
                tool_name="save_content_draft",
                tool_type="LOCAL",
                input_payload={"generate_from_experiment": True, "experiment_id": "demo"},
            )
        )
        prompt_log = PromptRunLog(
                prompt_template_id=None,
                prompt_name="demo_draft_generation",
                prompt_version="v1",
                input_payload={"demo": True},
                rendered_prompt="Generate a mock draft for developer trace demo.",
                output_text='{"title":"mock draft"}',
                output_json={"title": "mock draft"},
                model="mock-qwen-plus",
                provider="mock",
                prompt_key="demo_draft_generation",
                prompt_tokens=120,
                completion_tokens=45,
                total_tokens=165,
                input_token_count=120,
                output_token_count=45,
                estimated_cost=0,
                is_mock=True,
                raw_response_id="mock-demo-response",
        )
        db.add(prompt_log)
        db.commit()
        db.refresh(prompt_log)
        built_context = (
            ContextManager(task_name="demo_developer_trace", token_budget=600)
            .extend(
                [
                    ContextSlot(ContextSlotName.SYSTEM_RULES, "Mock-only demo. Do not publish or interact.", role=ContextRole.SYSTEM, priority=100),
                    ContextSlot(ContextSlotName.TASK_INSTRUCTION, "Generate a demo draft.", priority=90),
                    ContextSlot(ContextSlotName.TOOL_RESULT, mcp_result, source_type="mcp", priority=70, token_limit=200),
                ]
            )
            .build()
        )
        ContextUsageLogger(db).record_snapshot(built_context, agent_run_id=run.id, agent_step_id=step3.id, prompt_run_log_id=prompt_log.id, model=prompt_log.model, provider=prompt_log.provider)
        repo.finish_step(
            step3,
            AgentStepStatus.SUCCESS.value,
            {"ok": True, "tool_name": "save_content_draft", "data": {"draft_id": "demo", "status": "GENERATED"}, "metadata": {"token_count": 165, "estimated_cost": 0, "mock": True}},
        )

        step4 = repo.create_step(
            AgentStepCreate(
                agent_run_id=run.id,
                step_index=3,
                tool_name="llm_output_failed_fallback",
                tool_type="FALLBACK",
                input_payload={"original_tool": "save_content_draft"},
            )
        )
        repo.finish_step(
            step4,
            AgentStepStatus.FALLBACK_USED.value,
            {"ok": True, "tool_name": "llm_output_failed_fallback", "data": {"fallback": "stored safe placeholder"}, "metadata": {"fallback_tool_name": "llm_output_failed_fallback", "mock": True}},
        )

        finished = repo.finish_run(run, "SUCCESS", {"demo": True, "steps": 4})
        return finished.id


if __name__ == "__main__":
    print(create_demo_agent_trace())
