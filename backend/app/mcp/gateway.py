from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.agent.tools.base import ToolResult
from app.repositories.agent_run_repo import AgentRunRepository
from app.schemas.provider_status import DataStatus, ProviderErrorCode


MCP_DEFAULT_BINDINGS = {
    "web_search": {"risk_level": "LOW", "requires_confirmation": False, "fallback_tool_name": "mcp_call_failed_fallback"},
    "page_reader": {"risk_level": "LOW", "requires_confirmation": False, "fallback_tool_name": "mcp_call_failed_fallback"},
    "ocr": {"risk_level": "MEDIUM", "requires_confirmation": False, "fallback_tool_name": "mcp_call_failed_fallback"},
    "file_parser": {"risk_level": "MEDIUM", "requires_confirmation": False, "fallback_tool_name": "mcp_call_failed_fallback"},
    "data_query": {"risk_level": "MEDIUM", "requires_confirmation": True, "fallback_tool_name": "mcp_call_failed_fallback"},
}


class MCPToolGateway:
    """MCP 工具网关；未配置真实服务时返回明确失败。"""

    def __init__(self, db: Session):
        """初始化 MCP 工具网关。"""
        self.repo = AgentRunRepository(db)

    def invoke(self, tool_name: str, payload: dict, agent_run_id: int | None = None, agent_step_id: int | None = None) -> ToolResult:
        """调用 MCP 工具；未接入真实 MCP 时返回结构化失败，不伪装成功。"""
        started_at = datetime.now(UTC)
        binding = self.repo.get_mcp_binding(tool_name)
        config = MCP_DEFAULT_BINDINGS.get(tool_name)
        if not binding and not config:
            metadata = self._blocked_metadata(tool_name)
            result = ToolResult(False, tool_name, error=ProviderErrorCode.MCP_TOOL_NOT_WHITELISTED.value, metadata=metadata)
            self._record_call(tool_name, payload, result, started_at, agent_run_id, agent_step_id, metadata, binding)
            return result

        metadata = self._metadata(tool_name, binding, config)
        result = ToolResult(
            False,
            tool_name,
            {
                "error_code": ProviderErrorCode.MCP_NOT_CONFIGURED.value,
                "data_status": DataStatus.NOT_PROVIDED.value,
                "warning_message": "MCP 数据源未配置，当前没有可用真实工具调用结果。",
                "suggestion": "请配置真实 MCP 服务，或改用手动录入真实公开样本。",
                "can_continue": False,
            },
            error=ProviderErrorCode.MCP_NOT_CONFIGURED.value,
            metadata={**metadata, "mock": False, "mock_used": False, "data_status": DataStatus.NOT_PROVIDED.value},
        )
        self._record_call(tool_name, payload, result, started_at, agent_run_id, agent_step_id, result.metadata, binding)
        return result

    def _metadata(self, tool_name: str, binding, config: dict | None) -> dict:
        """构造 MCP 工具元数据。"""
        source = config or {}
        return {
            "tool_name": tool_name,
            "risk_level": getattr(binding, "risk_level", None) or source.get("risk_level", "LOW"),
            "requires_confirmation": getattr(binding, "requires_confirmation", None) if binding else source.get("requires_confirmation", False),
            "fallback_tool_name": getattr(binding, "fallback_tool_name", None) or source.get("fallback_tool_name"),
        }

    def _blocked_metadata(self, tool_name: str) -> dict:
        """构造 MCP 工具未授权时的元数据。"""
        return {
            "tool_name": tool_name,
            "risk_level": "HIGH",
            "requires_confirmation": True,
            "fallback_tool_name": None,
            "mock": False,
            "mock_used": False,
            "risk_blocked": True,
        }

    def _record_call(self, tool_name: str, payload: dict, result: ToolResult, started_at: datetime, agent_run_id: int | None, agent_step_id: int | None, metadata: dict, binding) -> None:
        """记录 MCP 工具调用日志。"""
        latency_ms = int((datetime.now(UTC) - started_at).total_seconds() * 1000)
        self.repo.record_mcp_call(
            {
                "agent_run_id": agent_run_id,
                "agent_step_id": agent_step_id,
                "server_config_id": getattr(binding, "server_config_id", None),
                "tool_name": tool_name,
                "status": "SUCCESS" if result.ok else "FAILED",
                "input_payload": payload,
                "output_payload": result.model_dump(),
                "error_message": result.error,
                "latency_ms": latency_ms,
                "risk_level": metadata["risk_level"],
                "requires_confirmation": metadata["requires_confirmation"],
            }
        )
