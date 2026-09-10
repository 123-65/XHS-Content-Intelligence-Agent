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
        """返回 LLM 输出失败错误。"""
        return ToolResult(
            False,
            "llm_output_failed_fallback",
            {
                "fallback_level": "L3",
                "fallback_reason": "LLM_OUTPUT_FAILED",
                "error_code": "LLM_OUTPUT_PARSE_FAILED",
                "data_status": "FAILED",
                "data_quality": "UNUSABLE",
                "confidence": "LOW",
                "hint": "LLM 输出不可用，请检查 Prompt、Schema 或真实 Provider 配置后重试。",
                "warning_message": "LLM 输出解析失败，系统未生成可用结果。",
                "suggestion": "请检查 Prompt、输出 Schema 或更换真实 LLM Provider 后重试。",
            },
            error="LLM_OUTPUT_PARSE_FAILED",
            metadata={"fallback_used": True, "mock_used": False},
        )

    def _collection_failed(self, payload: dict) -> ToolResult:
        """返回采集失败时的人工补充提示，不再使用 Seed/Mock 数据。"""
        return ToolResult(
            True,
            "collection_failed_fallback",
            {
                "fallback_reason": "COLLECTION_FAILED",
                "error_code": "MANUAL_SNAPSHOT_REQUIRED",
                "data_status": "NOT_PROVIDED",
                "confidence": "LOW",
                "warning_message": "当前没有可用的真实小红书样本，系统不会生成模拟数据。",
                "suggestion": "请先通过 MCP 采集或手动录入 10-30 条真实公开笔记样本。",
                "can_continue": False,
            },
            metadata={"fallback_used": True, "mock_used": False, "data_status": "NOT_PROVIDED"},
        )

    def _comment_sample_insufficient(self, payload: dict) -> ToolResult:
        """返回评论样本不足时的低置信度提示，不编造评论需求。"""
        return ToolResult(
            True,
            "comment_sample_insufficient_fallback",
            {
                "fallback_level": "L1",
                "fallback_reason": "COMMENT_SAMPLE_INSUFFICIENT",
                "error_code": "COMMENT_SAMPLE_MISSING",
                "data_status": "PARTIAL",
                "data_quality": "PARTIAL",
                "demand_type": "UNKNOWN",
                "confidence": "LOW",
                "hint": "评论样本不足，需求分类只能作为低置信参考。",
                "warning_message": "评论样本不足，无法可靠识别用户需求，相关结论仅供参考。",
                "suggestion": "建议补充至少 10 条真实评论样本后重新分析。",
            },
            metadata={"fallback_used": True, "mock_used": False},
        )

    def _mcp_call_failed(self, payload: dict) -> ToolResult:
        """返回 MCP 调用失败提示，不生成 Mock 外部工具结果。"""
        return ToolResult(
            True,
            "mcp_call_failed_fallback",
            {
                "fallback_level": "L3",
                "fallback_reason": "MCP_CALL_FAILED",
                "error_code": "MCP_PROVIDER_FAILED",
                "data_status": "FAILED",
                "data_quality": "UNUSABLE",
                "confidence": "LOW",
                "hint": "外部 MCP 数据源调用失败，请稍后重试或检查 Provider 配置。",
                "warning_message": "MCP 数据源暂时不可用，系统不会生成模拟数据。",
                "suggestion": "请稍后重试 MCP 数据源，或手动录入真实公开笔记快照。",
            },
            metadata={"fallback_used": True, "mock_used": False},
        )
