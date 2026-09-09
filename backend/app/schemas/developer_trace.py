from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class DeveloperAgentRunSummary(BaseModel):
    """Developer-facing AgentRun summary."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    account_id: int | None
    workflow_name: str
    agent_type: str
    status: str
    stop_reason: str | None
    total_steps: int = 0
    success_steps: int = 0
    failed_steps: int = 0
    llm_call_count: int = 0
    total_latency_ms: int = 0
    total_token_count: int = 0
    estimated_cost: Decimal = Decimal("0")
    started_at: datetime
    finished_at: datetime | None


class DeveloperAgentStepTrace(BaseModel):
    """Developer-facing AgentStep trace item."""

    id: int
    run_id: int
    step_order: int
    step_name: str
    tool_name: str
    tool_input_summary: dict[str, Any] = Field(default_factory=dict)
    tool_output_summary: dict[str, Any] = Field(default_factory=dict)
    provider_name: str | None = None
    is_mock: bool = False
    prompt_key: str | None = None
    prompt_version: str | None = None
    latency_ms: int = 0
    token_count: int = 0
    estimated_cost: Decimal = Decimal("0")
    fallback_used: bool = False
    status: str
    error_code: str | None = None
    error_message: str | None = None
    llm_calls: list[dict[str, Any]] = Field(default_factory=list)
    tool_calls: list[dict[str, Any]] = Field(default_factory=list)


class DeveloperAgentRunDetail(DeveloperAgentRunSummary):
    """Developer-facing run detail with complete timeline."""

    steps: list[DeveloperAgentStepTrace] = Field(default_factory=list)
    tool_calls: list[dict[str, Any]] = Field(default_factory=list)
    llm_calls: list[dict[str, Any]] = Field(default_factory=list)
    fallback_records: list[dict[str, Any]] = Field(default_factory=list)
    errors: list[dict[str, Any]] = Field(default_factory=list)

