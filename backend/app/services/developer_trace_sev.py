from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session

from app.enums.agent import AgentStepStatus
from app.models.agent_run import AgentRun
from app.models.agent_step import AgentStep
from app.models.context_snapshot import ContextSnapshot
from app.models.mcp_tool_call_log import MCPToolCallLog
from app.models.prompt_run_log import PromptRunLog
from app.repositories.agent_run_repo import AgentRunRepository
from app.schemas.developer_trace import DeveloperAgentRunDetail, DeveloperAgentRunSummary, DeveloperAgentStepTrace


SUCCESS_STATUSES = {AgentStepStatus.SUCCESS.value, AgentStepStatus.FALLBACK_USED.value}
FAILED_STATUSES = {AgentStepStatus.FAILED.value, AgentStepStatus.RISK_BLOCKED.value}


class DeveloperTraceService:
    """Read-only developer trace aggregation for Agent runs."""

    def __init__(self, db: Session):
        self.db = db
        self.repo = AgentRunRepository(db)

    def list_runs(self, limit: int = 20) -> list[DeveloperAgentRunSummary]:
        """Return recent AgentRun summaries."""
        runs = self.repo.list_runs()[:limit]
        return [self._run_summary(run, self.repo.list_steps(run.id)) for run in runs]

    def get_run(self, run_id: int) -> DeveloperAgentRunDetail:
        """Return one AgentRun with its timeline."""
        run = self._get_run_or_raise(run_id)
        return self._run_detail(run)

    def list_steps(self, run_id: int) -> list[DeveloperAgentStepTrace]:
        """Return timeline steps for one run."""
        run = self._get_run_or_raise(run_id)
        return self._step_traces(run, self.repo.list_steps(run.id))

    def latest_run(self) -> DeveloperAgentRunDetail:
        """Return the latest AgentRun detail."""
        runs = self.repo.list_runs()
        if not runs:
            raise ValueError("AgentRun does not exist")
        return self._run_detail(runs[0])

    def latest_steps(self) -> list[DeveloperAgentStepTrace]:
        """Return steps for the latest AgentRun."""
        latest = self.latest_run()
        return latest.steps

    def _run_detail(self, run: AgentRun) -> DeveloperAgentRunDetail:
        steps = self.repo.list_steps(run.id)
        step_traces = self._step_traces(run, steps)
        summary = self._run_summary(run, steps)
        tool_calls = [call for step in step_traces for call in step.tool_calls]
        llm_calls = [call for step in step_traces for call in step.llm_calls]
        fallback_records = [
            {"step_order": step.step_order, "tool_name": step.tool_name, "status": step.status, "error_message": step.error_message}
            for step in step_traces
            if step.fallback_used
        ]
        errors = [
            {"step_order": step.step_order, "tool_name": step.tool_name, "status": step.status, "error_code": step.error_code, "error_message": step.error_message}
            for step in step_traces
            if step.error_code or step.error_message or step.status in FAILED_STATUSES
        ]
        return DeveloperAgentRunDetail(**summary.model_dump(), steps=step_traces, tool_calls=tool_calls, llm_calls=llm_calls, fallback_records=fallback_records, errors=errors)

    def _run_summary(self, run: AgentRun, steps: list[AgentStep]) -> DeveloperAgentRunSummary:
        llm_logs = self._prompt_logs_for_run(run.id)
        total_token_count = int(getattr(run, "token_count", 0) or sum(log.total_tokens for log in llm_logs) or self._sum_step_metadata(steps, "token_count"))
        estimated_cost = Decimal(str(getattr(run, "estimated_cost", 0) or sum(Decimal(str(log.estimated_cost)) for log in llm_logs)))
        return DeveloperAgentRunSummary(
            id=run.id,
            account_id=run.account_id,
            workflow_name=run.workflow_name,
            agent_type=getattr(run, "agent_type", "WORKFLOW_AGENT"),
            status=run.status,
            stop_reason=run.stop_reason,
            total_steps=len(steps),
            success_steps=len([step for step in steps if step.status in SUCCESS_STATUSES]),
            failed_steps=len([step for step in steps if step.status in FAILED_STATUSES]),
            llm_call_count=len(llm_logs),
            total_latency_ms=sum(int(step.duration_ms or 0) for step in steps),
            total_token_count=total_token_count,
            estimated_cost=estimated_cost,
            started_at=run.started_at,
            finished_at=run.finished_at,
        )

    def _step_traces(self, run: AgentRun, steps: list[AgentStep]) -> list[DeveloperAgentStepTrace]:
        prompt_logs = self._prompt_logs_by_step(run.id)
        mcp_logs = self._mcp_logs_by_step(run.id)
        return [self._step_trace(step, prompt_logs.get(step.id, []), mcp_logs.get(step.id, [])) for step in steps]

    def _step_trace(self, step: AgentStep, prompt_logs: list[PromptRunLog], mcp_logs: list[MCPToolCallLog]) -> DeveloperAgentStepTrace:
        output = step.output_payload or {}
        metadata = output.get("metadata") or {}
        data = output.get("data") or {}
        prompt_log = prompt_logs[0] if prompt_logs else None
        mcp_log = mcp_logs[0] if mcp_logs else None
        provider_name = self._provider_name(prompt_log, mcp_log, metadata, data)
        is_mock = bool(
            (prompt_log.is_mock if prompt_log else False)
            or metadata.get("mock")
            or data.get("is_mock")
            or (mcp_log is not None and str((mcp_log.output_payload or {}).get("metadata", {}).get("mock")).lower() == "true")
        )
        token_count = int((prompt_log.total_tokens if prompt_log else 0) or metadata.get("token_count") or 0)
        estimated_cost = Decimal(str((prompt_log.estimated_cost if prompt_log else 0) or metadata.get("estimated_cost") or 0))
        return DeveloperAgentStepTrace(
            id=step.id,
            run_id=step.agent_run_id,
            step_order=step.step_index + 1,
            step_name=f"{step.step_index + 1}. {step.tool_name}",
            tool_name=step.tool_name,
            tool_input_summary=self._payload_summary(step.input_payload),
            tool_output_summary=self._payload_summary(output),
            provider_name=provider_name,
            is_mock=is_mock,
            prompt_key=getattr(prompt_log, "prompt_key", None),
            prompt_version=getattr(prompt_log, "prompt_version", None),
            latency_ms=int(step.duration_ms or getattr(mcp_log, "latency_ms", 0) or 0),
            token_count=token_count,
            estimated_cost=estimated_cost,
            fallback_used=step.status == AgentStepStatus.FALLBACK_USED.value or bool(metadata.get("fallback_tool_name")),
            status=step.status,
            error_code=self._error_code(step),
            error_message=step.error_message or output.get("error"),
            llm_calls=[self._prompt_log_summary(log) for log in prompt_logs],
            tool_calls=[self._mcp_log_summary(log) for log in mcp_logs],
        )

    def _prompt_logs_for_run(self, run_id: int) -> list[PromptRunLog]:
        rows = (
            self.db.query(PromptRunLog)
            .join(ContextSnapshot, ContextSnapshot.prompt_run_log_id == PromptRunLog.id)
            .filter(ContextSnapshot.agent_run_id == run_id)
            .order_by(PromptRunLog.created_at.desc(), PromptRunLog.id.desc())
            .all()
        )
        return list(rows)

    def _prompt_logs_by_step(self, run_id: int) -> dict[int, list[PromptRunLog]]:
        rows = (
            self.db.query(ContextSnapshot.agent_step_id, PromptRunLog)
            .join(PromptRunLog, ContextSnapshot.prompt_run_log_id == PromptRunLog.id)
            .filter(ContextSnapshot.agent_run_id == run_id, ContextSnapshot.agent_step_id.isnot(None))
            .order_by(PromptRunLog.created_at.desc(), PromptRunLog.id.desc())
            .all()
        )
        grouped: dict[int, list[PromptRunLog]] = {}
        for step_id, log in rows:
            grouped.setdefault(int(step_id), []).append(log)
        return grouped

    def _mcp_logs_by_step(self, run_id: int) -> dict[int, list[MCPToolCallLog]]:
        rows = (
            self.db.query(MCPToolCallLog)
            .filter(MCPToolCallLog.agent_run_id == run_id, MCPToolCallLog.agent_step_id.isnot(None))
            .order_by(MCPToolCallLog.created_at.desc(), MCPToolCallLog.id.desc())
            .all()
        )
        grouped: dict[int, list[MCPToolCallLog]] = {}
        for log in rows:
            grouped.setdefault(int(log.agent_step_id), []).append(log)
        return grouped

    def _prompt_log_summary(self, log: PromptRunLog) -> dict[str, Any]:
        return {
            "id": log.id,
            "prompt_key": log.prompt_key,
            "prompt_name": log.prompt_name,
            "prompt_version": log.prompt_version,
            "provider": log.provider,
            "model": log.model,
            "is_mock": log.is_mock,
            "total_tokens": log.total_tokens,
            "estimated_cost": str(log.estimated_cost),
            "status": log.status,
            "raw_response_id": log.raw_response_id,
            "created_at": log.created_at.isoformat() if log.created_at else None,
        }

    def _mcp_log_summary(self, log: MCPToolCallLog) -> dict[str, Any]:
        return {
            "id": log.id,
            "tool_name": log.tool_name,
            "status": log.status,
            "latency_ms": log.latency_ms,
            "risk_level": log.risk_level,
            "requires_confirmation": log.requires_confirmation,
            "provider_name": (log.output_payload or {}).get("metadata", {}).get("tool_name"),
            "is_mock": bool((log.output_payload or {}).get("metadata", {}).get("mock")),
            "created_at": log.created_at.isoformat() if log.created_at else None,
        }

    def _payload_summary(self, payload: Any) -> dict[str, Any]:
        if not payload:
            return {}
        if isinstance(payload, dict) and payload.get("storage_policy") == "summary_only":
            return payload
        if isinstance(payload, dict):
            data = payload.get("data") if isinstance(payload.get("data"), dict) else payload
            return {
                "keys": list(data.keys())[:12] if isinstance(data, dict) else [],
                "ok": payload.get("ok"),
                "tool_name": payload.get("tool_name"),
                "error": payload.get("error"),
                "metadata": payload.get("metadata", {}),
            }
        text = str(payload)
        return {"summary": text[:600], "truncated": len(text) > 600}

    def _provider_name(self, prompt_log, mcp_log, metadata: dict, data: dict) -> str | None:
        if prompt_log:
            return prompt_log.provider
        if mcp_log:
            return (mcp_log.output_payload or {}).get("metadata", {}).get("tool_name") or "mcp"
        return metadata.get("provider") or metadata.get("tool_name") or data.get("provider_name")

    def _error_code(self, step: AgentStep) -> str | None:
        metadata = (step.output_payload or {}).get("metadata") or {}
        codes = metadata.get("codes") or []
        return codes[0] if codes else None

    def _sum_step_metadata(self, steps: list[AgentStep], key: str) -> int:
        values = [((step.output_payload or {}).get("metadata") or {}).get(key, 0) for step in steps]
        return sum(int(value) for value in values if isinstance(value, int | float))

    def _get_run_or_raise(self, run_id: int) -> AgentRun:
        run = self.repo.get_run(run_id)
        if not run:
            raise ValueError("AgentRun does not exist")
        return run

