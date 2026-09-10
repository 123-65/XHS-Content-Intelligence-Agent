from app.agent.tools.base import ToolDefinition


class FallbackPolicy:
    """Agent 工具调用降级策略。"""

    def fallback_for(self, tool: ToolDefinition, error: Exception | None = None) -> str | None:
        """根据工具定义和错误类型选择降级工具。"""
        mapped = {
            "LLM_OUTPUT_FAILED": "llm_output_failed_fallback",
            "COLLECTION_FAILED": "collection_failed_fallback",
            "COMMENT_SAMPLE_INSUFFICIENT": "comment_sample_insufficient_fallback",
            "MCP_CALL_FAILED": "mcp_call_failed_fallback",
        }
        error_key = self._error_key(error)
        if error_key:
            return mapped.get(error_key)
        return tool.fallback_tool_name if self._is_technical_failure(error) else None

    def _is_technical_failure(self, error: Exception | None) -> bool:
        """业务状态不降级，只有未预期的技术异常才走工具默认降级。"""
        return error is not None and not isinstance(error, ValueError)

    def _error_key(self, error: Exception | None) -> str | None:
        """从错误信息中提取降级类型。"""
        if not error:
            return None
        text = str(error).upper()
        return next((key for key in ("LLM_OUTPUT_FAILED", "COLLECTION_FAILED", "COMMENT_SAMPLE_INSUFFICIENT", "MCP_CALL_FAILED") if key in text), None)
