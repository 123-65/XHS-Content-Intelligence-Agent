from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class AgentRunCreate(BaseModel):
    """创建 AgentRun 的数据结构。"""

    account_id: int | None = None
    agent_type: str = "WORKFLOW_AGENT"
    workflow_name: str
    input_payload: dict = Field(default_factory=dict)
    max_steps: int = 8
    max_retry: int = 1


class AgentStepCreate(BaseModel):
    """创建 AgentStep 的数据结构。"""

    agent_run_id: int
    step_index: int
    tool_name: str
    tool_type: str
    input_payload: dict = Field(default_factory=dict)
    risk_level: str = "LOW"
    requires_confirmation: bool = False
    fallback_tool_name: str | None = None


class AgentStepResponse(BaseModel):
    """AgentStep 的响应结构。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    agent_run_id: int
    step_order: int = 0
    step_name: str | None = None
    step_index: int
    tool_name: str
    tool_type: str
    status: str
    tool_input: dict = Field(default_factory=dict)
    tool_output_summary: dict = Field(default_factory=dict)
    input_payload: dict
    output_payload: dict
    error_code: str | None = None
    error_message: str | None
    retry_count: int
    risk_level: str
    requires_confirmation: bool
    fallback_tool_name: str | None
    latency_ms: int = 0
    fallback_used: bool = False
    started_at: datetime
    finished_at: datetime | None
    duration_ms: int


class AgentRunResponse(BaseModel):
    """AgentRun 的响应结构。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    account_id: int | None
    agent_type: str = "WORKFLOW_AGENT"
    workflow_name: str
    status: str
    input_payload: dict
    output_payload: dict
    error_message: str | None
    stop_reason: str | None
    max_steps: int
    max_retry: int
    total_steps: int = 0
    success_steps: int = 0
    failed_steps: int = 0
    llm_call_count: int = 0
    token_count: int = 0
    estimated_cost: Decimal = Decimal("0")
    consecutive_failures: int
    started_at: datetime
    finished_at: datetime | None
    created_at: datetime
    updated_at: datetime


class AgentRunDetailResponse(AgentRunResponse):
    """带步骤详情的 AgentRun 响应结构。"""

    steps: list[AgentStepResponse] = Field(default_factory=list)


class ToolCallRequest(BaseModel):
    """Agent 工具调用请求。"""

    tool_name: str
    payload: dict = Field(default_factory=dict)


class ToolResultModel(BaseModel):
    """结构化工具输出。"""

    ok: bool
    tool_name: str
    data: dict = Field(default_factory=dict)
    error: str | None = None
    metadata: dict = Field(default_factory=dict)


class WorkflowStepSpec(BaseModel):
    """工作流步骤定义。"""

    tool_name: str
    payload: dict = Field(default_factory=dict)


class WorkflowRunRequest(BaseModel):
    """Agent 工作流执行请求。"""

    workflow_name: str
    account_id: int | None = None
    agent_type: str = "WORKFLOW_AGENT"
    input_payload: dict = Field(default_factory=dict)
    steps: list[WorkflowStepSpec] = Field(default_factory=list)
    max_steps: int = 8
    max_retry: int = 1


class MCPServerConfigResponse(BaseModel):
    """MCP Server 配置响应结构。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    server_name: str
    base_url: str | None
    status: str
    auth_type: str
    allowed_tools: list[str]
    risk_level: str
    requires_confirmation: bool
    description: str | None
    metadata_payload: dict
    created_at: datetime
    updated_at: datetime


class MCPToolBindingResponse(BaseModel):
    """MCP 工具绑定响应结构。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    server_config_id: int | None
    tool_name: str
    display_name: str
    description: str | None
    risk_level: str
    requires_confirmation: bool
    fallback_tool_name: str | None
    enabled: bool
    whitelist_rules: dict
    created_at: datetime
    updated_at: datetime


class MCPToolCallLogResponse(BaseModel):
    """MCP 工具调用日志响应结构。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    agent_run_id: int | None
    agent_step_id: int | None
    server_config_id: int | None
    tool_name: str
    status: str
    input_payload: dict
    output_payload: dict
    error_message: str | None
    latency_ms: int
    risk_level: str
    requires_confirmation: bool
    created_at: datetime


class StrategyMemoryUsageResponse(BaseModel):
    """策略记忆使用记录响应结构。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    account_id: int
    agent_run_id: int
    memory_id: int | None
    usage_reason: str
    usage_snapshot: dict[str, Any]
    created_at: datetime
