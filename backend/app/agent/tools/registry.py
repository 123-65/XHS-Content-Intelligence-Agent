from sqlalchemy.orm import Session

from app.agent.tools.base import ToolDefinition, ToolNotFoundError
from app.agent.tools.fallback_registry import FallbackToolRegistry
from app.agent.tools.local_registry import LocalToolRegistry
from app.agent.tools.mcp_registry import MCPToolRegistry


class ToolRegistry:
    """组合 Local、MCP 和 Fallback 的工具注册表。"""

    def __init__(self, db: Session):
        """初始化组合工具注册表。"""
        self.local = LocalToolRegistry(db)
        self.mcp = MCPToolRegistry(db)
        self.fallback = FallbackToolRegistry()
        self.registries = (self.local, self.mcp, self.fallback)

    def get_tool(self, tool_name: str) -> ToolDefinition:
        """根据工具名查找工具。"""
        for registry in self.registries:
            tool = registry.get_tool(tool_name)
            if tool:
                return tool
        raise ToolNotFoundError(f"Tool not found: {tool_name}")

    def list_tools(self) -> list[ToolDefinition]:
        """列出全部已注册工具。"""
        return [tool for registry in self.registries for tool in registry.list_tools()]
