from app.agent.tools.base import ToolDefinition, ToolResult
from app.enums.agent import ToolType


class FallbackToolRegistry:
    """降级工具注册表。"""

    def __init__(self):
        """初始化降级工具集合。"""
        self.tools = self._build_tools()

    def get_tool(self, tool_name: str) -> ToolDefinition | None:
        """按名称获取降级工具。"""
        return self.tools.get(tool_name)

    def list_tools(self) -> list[ToolDefinition]:
        """列出全部降级工具。"""
        return list(self.tools.values())

    def _build_tools(self) -> dict[str, ToolDefinition]:
        """构造降级工具映射。"""
        handlers = {
            "llm_output_failed_fallback": self._llm_output_failed,
            "collection_failed_fallback": self._collection_failed,
            "comment_sample_insufficient_fallback": self._comment_sample_insufficient,
            "mcp_call_failed_fallback": self._mcp_call_failed,
        }
        return {
            name: ToolDefinition(
                name=name,
                tool_type=ToolType.FALLBACK.value,
                handler=handler,
                description=f"{name} 降级工具",
                risk_level="LOW",
            )
            for name, handler in handlers.items()
        }

    def _llm_output_failed(self, payload: dict) -> ToolResult:
        """返回 LLM 输出失败时的安全结构化占位结果。"""
        return ToolResult(True, "llm_output_failed_fallback", {"fallback_reason": "LLM_OUTPUT_FAILED", "payload": payload})

    def _collection_failed(self, payload: dict) -> ToolResult:
        """返回采集失败时的 Seed/Mock 降级提示。"""
        return ToolResult(True, "collection_failed_fallback", {"fallback_reason": "COLLECTION_FAILED", "recommended_provider": "SeedSampleProvider"})

    def _comment_sample_insufficient(self, payload: dict) -> ToolResult:
        """返回评论样本不足时的保守分析结果。"""
        return ToolResult(True, "comment_sample_insufficient_fallback", {"fallback_reason": "COMMENT_SAMPLE_INSUFFICIENT", "demand_type": "UNKNOWN"})

    def _mcp_call_failed(self, payload: dict) -> ToolResult:
        """返回 MCP 调用失败时的 Mock 外部工具结果。"""
        return ToolResult(True, "mcp_call_failed_fallback", {"fallback_reason": "MCP_CALL_FAILED", "mock_result": payload})
