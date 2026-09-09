from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ToolResult:
    """结构化工具执行结果。"""

    ok: bool
    tool_name: str
    data: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def model_dump(self) -> dict:
        """转换为可写入 JSONB 的字典。"""
        return {
            "ok": self.ok,
            "tool_name": self.tool_name,
            "data": self.data,
            "error": self.error,
            "metadata": self.metadata,
        }


ToolHandler = Callable[[dict[str, Any]], ToolResult]


@dataclass(frozen=True)
class ToolDefinition:
    """工具定义元数据。"""

    name: str
    tool_type: str
    handler: ToolHandler
    description: str
    risk_level: str = "LOW"
    requires_confirmation: bool = False
    fallback_tool_name: str | None = None
    whitelist_rules: dict[str, Any] = field(default_factory=dict)


class ToolNotFoundError(ValueError):
    """工具不存在错误。"""
