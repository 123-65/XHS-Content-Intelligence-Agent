from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.agent.tools.base import ToolResult
from app.repositories.agent_run_repo import AgentRunRepository


MCP_DEFAULT_BINDINGS = {
    "web_search": {"risk_level": "LOW", "requires_confirmation": False, "fallback_tool_name": "mcp_call_failed_fallback"},
    "page_reader": {"risk_level": "LOW", "requires_confirmation": False, "fallback_tool_name": "mcp_call_failed_fallback"},
    "ocr": {"risk_level": "MEDIUM", "requires_confirmation": False, "fallback_tool_name": "mcp_call_failed_fallback"},
    "file_parser": {"risk_level": "MEDIUM", "requires_confirmation": False, "fallback_tool_name": "mcp_call_failed_fallback"},
    "data_query": {"risk_level": "MEDIUM", "requires_confirmation": True, "fallback_tool_name": "mcp_call_failed_fallback"},
}


class MCPToolGateway:
    """MCP 工具网关的 Mock 适配实现。"""

    def __init__(self, db: Session):
        """初始化 MCP 工具网关。"""
        self.repo = AgentRunRepository(db)

    def invoke(self, tool_name: str, payload: dict, agent_run_id: int | None = None, agent_step_id: int | None = None) -> ToolResult:
        """调用白名单内的 Mock MCP 工具。"""
        started_at = datetime.now(UTC)
        binding = self.repo.get_mcp_binding(tool_name)
        config = MCP_DEFAULT_BINDINGS.get(tool_name)
        if not binding and not config:
            return ToolResult(False, tool_name, error="MCP tool is not whitelisted", metadata={"risk_blocked": True})
        metadata = self._metadata(tool_name, binding, config)
        result = ToolResult(True, tool_name, self._mock_payload(tool_name, payload), metadata=metadata)
        self._record_call(tool_name, payload, result, started_at, agent_run_id, agent_step_id, metadata, binding)
        return result

    def _metadata(self, tool_name: str, binding, config: dict | None) -> dict:
        """构造 MCP 工具元数据。"""
        source = config or {}
        return {
            "tool_name": tool_name,
            "risk_level": getattr(binding, "risk_level", None) or source.get("risk_level", "LOW"),
            "requires_confirmation": getattr(binding, "requires_confirmation", None) if binding else source.get("requires_confirmation", False),
            "fallback_tool_name": getattr(binding, "fallback_tool_name", None) or source.get("fallback_tool_name"),
            "mock": True,
        }

    def _mock_payload(self, tool_name: str, payload: dict) -> dict:
        """生成 Mock MCP 工具输出。"""
        builders = {
            "web_search": lambda item: {"query": item.get("query"), "results": [{"title": "mock result", "url": "mock://web-search", "summary": "Mock search result"}]},
            "page_reader": lambda item: {"url": item.get("url"), "text": "Mock page reader content"},
            "ocr": lambda item: {"image_ref": item.get("image_ref"), "text": "Mock OCR text"},
            "file_parser": lambda item: {"file_ref": item.get("file_ref"), "records": []},
            "data_query": lambda item: {"query": item.get("query"), "rows": []},
        }
        return builders[tool_name](payload)

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
