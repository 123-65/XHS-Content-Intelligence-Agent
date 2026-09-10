from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.context.context_snapshot import TracePayloadGovernor
from app.models.agent_run import AgentRun
from app.models.agent_step import AgentStep
from app.models.mcp_server_config import MCPServerConfig
from app.models.mcp_tool_binding import MCPToolBinding
from app.models.mcp_tool_call_log import MCPToolCallLog
from app.models.strategy_memory_usage import StrategyMemoryUsage
from app.enums.agent import AgentStepStatus
from app.schemas.agent import AgentRunCreate, AgentStepCreate


class AgentRunRepository:
    """Agent 运行轨迹的数据库访问层。"""

    def __init__(self, db: Session):
        """初始化 Agent 运行仓储。"""
        self.db = db
        self.trace_governor = TracePayloadGovernor()

    def create_run(self, data: AgentRunCreate) -> AgentRun:
        """创建 AgentRun 记录。"""
        fields = data.model_dump()
        fields["input_payload"] = self.trace_governor.govern_payload(fields.get("input_payload", {}), "agent_step")
        run = AgentRun(**fields, status="RUNNING")
        self.db.add(run)
        self.db.commit()
        self.db.refresh(run)
        return run

    def get_run(self, agent_run_id: int) -> AgentRun | None:
        """根据 ID 查询 AgentRun。"""
        return self.db.get(AgentRun, agent_run_id)

    def list_runs(self, account_id: int | None = None) -> list[AgentRun]:
        """查询 AgentRun 列表。"""
        stmt = select(AgentRun).order_by(AgentRun.created_at.desc(), AgentRun.id.desc())
        if account_id is not None:
            stmt = stmt.where(AgentRun.account_id == account_id)
        return list(self.db.execute(stmt).scalars().all())

    def finish_run(self, run: AgentRun, status: str, output_payload: dict, stop_reason: str | None = None, error_message: str | None = None) -> AgentRun:
        """完成 AgentRun 并写入输出。"""
        run.status = status
        run.output_payload = self.trace_governor.govern_payload(output_payload, "agent_step")
        run.stop_reason = stop_reason
        run.error_message = self.trace_governor.govern_text(error_message, "agent_step")
        run.finished_at = datetime.now(UTC).replace(tzinfo=None)
        self.db.commit()
        self.db.refresh(run)
        return run

    def increment_failure(self, run: AgentRun) -> AgentRun:
        """累加连续失败次数。"""
        run.consecutive_failures += 1
        self.db.commit()
        self.db.refresh(run)
        return run

    def reset_failure(self, run: AgentRun) -> AgentRun:
        """清零连续失败次数。"""
        run.consecutive_failures = 0
        self.db.commit()
        self.db.refresh(run)
        return run

    def create_step(self, data: AgentStepCreate) -> AgentStep:
        """创建 AgentStep 记录。"""
        fields = data.model_dump()
        fields["input_payload"] = self.trace_governor.govern_payload(fields.get("input_payload", {}), "agent_step")
        step = AgentStep(**fields, status="RUNNING")
        self.db.add(step)
        self.db.commit()
        self.db.refresh(step)
        return step

    def finish_step(self, step: AgentStep, status: str, output_payload: dict, retry_count: int = 0, error_message: str | None = None) -> AgentStep:
        """完成 AgentStep 并写入工具输出。"""
        finished_at = datetime.now(UTC).replace(tzinfo=None)
        started_at = step.started_at or finished_at
        step.status = status
        step.output_payload = self.trace_governor.govern_payload(output_payload, "agent_step")
        if status == AgentStepStatus.FALLBACK_USED.value:
            metadata = output_payload.get("metadata") or {}
            step.fallback_tool_name = metadata.get("fallback_tool_name") or step.fallback_tool_name
        step.retry_count = retry_count
        step.error_message = self.trace_governor.govern_text(error_message, "agent_step")
        step.finished_at = finished_at
        step.duration_ms = max(0, int((finished_at - started_at).total_seconds() * 1000))
        self.db.commit()
        self.db.refresh(step)
        return step

    def list_steps(self, agent_run_id: int) -> list[AgentStep]:
        """查询 AgentRun 的步骤列表。"""
        stmt = select(AgentStep).where(AgentStep.agent_run_id == agent_run_id).order_by(AgentStep.step_index.asc(), AgentStep.id.asc())
        return list(self.db.execute(stmt).scalars().all())

    def get_mcp_binding(self, tool_name: str) -> MCPToolBinding | None:
        """查询 MCP 工具绑定配置。"""
        stmt = select(MCPToolBinding).where(MCPToolBinding.tool_name == tool_name, MCPToolBinding.enabled.is_(True))
        return self.db.execute(stmt).scalar_one_or_none()

    def create_mcp_server_config(self, fields: dict) -> MCPServerConfig:
        """创建 MCP Server 配置。"""
        config = MCPServerConfig(**fields)
        self.db.add(config)
        self.db.commit()
        self.db.refresh(config)
        return config

    def create_mcp_tool_binding(self, fields: dict) -> MCPToolBinding:
        """创建 MCP 工具绑定。"""
        binding = MCPToolBinding(**fields)
        self.db.add(binding)
        self.db.commit()
        self.db.refresh(binding)
        return binding

    def record_mcp_call(self, fields: dict) -> MCPToolCallLog:
        """记录 MCP 工具调用日志。"""
        governed = {**fields}
        governed["input_payload"] = self.trace_governor.govern_payload(governed.get("input_payload", {}), "mcp_tool_call_log")
        governed["output_payload"] = self.trace_governor.govern_payload(governed.get("output_payload", {}), "mcp_tool_call_log")
        governed["error_message"] = self.trace_governor.govern_text(governed.get("error_message"), "mcp_tool_call_log")
        log = MCPToolCallLog(**governed)
        self.db.add(log)
        self.db.commit()
        self.db.refresh(log)
        return log

    def record_memory_usage(self, fields: dict) -> StrategyMemoryUsage:
        """记录策略记忆使用情况。"""
        usage = StrategyMemoryUsage(**fields)
        self.db.add(usage)
        self.db.commit()
        self.db.refresh(usage)
        return usage
