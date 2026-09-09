from sqlalchemy.orm import Session

from app.agent.tools.base import ToolDefinition
from app.enums.agent import ToolType
from app.mcp.gateway import MCPToolGateway, MCP_DEFAULT_BINDINGS


class MCPToolRegistry:
    """MCP 外部通用能力工具注册表。"""

    def __init__(self, db: Session):
        """初始化 MCP 工具注册表。"""
        self.gateway = MCPToolGateway(db)
        self.tools = self._build_tools()

    def get_tool(self, tool_name: str) -> ToolDefinition | None:
        """按名称获取 MCP 工具。"""
        return self.tools.get(tool_name)

    def list_tools(self) -> list[ToolDefinition]:
        """列出全部 MCP 工具。"""
        return list(self.tools.values())

    def _build_tools(self) -> dict[str, ToolDefinition]:
        """构造 MCP 工具映射。"""
        return {
            name: ToolDefinition(
                name=name,
                tool_type=ToolType.MCP.value,
                handler=lambda payload, tool_name=name: self.gateway.invoke(tool_name, payload, payload.get("_agent_run_id"), payload.get("_agent_step_id")),
                description=f"{name} MCP Mock 工具",
                risk_level=config["risk_level"],
                requires_confirmation=config["requires_confirmation"],
                fallback_tool_name=config["fallback_tool_name"],
                whitelist_rules={"allowed": True, "mode": "mock"},
            )
            for name, config in MCP_DEFAULT_BINDINGS.items()
        }
