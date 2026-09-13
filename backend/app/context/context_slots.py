import json
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class ContextSlotName(str, Enum):
    """LLM 调用前统一使用的上下文槽位名称。"""

    SYSTEM_RULES = "system_rules"
    TASK_INSTRUCTION = "task_instruction"
    ACCOUNT_PROFILE = "account_profile"
    DOMAIN_PROFILE = "domain_profile"
    USER_INPUT = "user_input"
    WORKFLOW_STATE = "workflow_state"
    COMPETITOR_EVIDENCE = "competitor_evidence"
    COMMENT_INSIGHT = "comment_insight"
    TOOL_RESULT = "tool_result"
    STRATEGY_MEMORY = "strategy_memory"
    RISK_CONSTRAINTS = "risk_constraints"
    OUTPUT_SCHEMA = "output_schema"
    DRAFT_CONTENT = "draft_content"


class ContextTrustLevel(str, Enum):
    """上下文可信等级，用于避免外部文本被当成系统指令。"""

    TRUSTED = "trusted"
    UNTRUSTED = "untrusted"


class ContextRole(str, Enum):
    """上下文槽位最终进入 prompt 时使用的角色。"""

    SYSTEM = "system"
    USER = "user"


@dataclass
class ContextSlot:
    """准备注入 LLM prompt 的单个结构化上下文槽位。"""

    name: ContextSlotName | str
    content: Any
    role: ContextRole | str = ContextRole.USER
    priority: int = 50
    trust_level: ContextTrustLevel | str = ContextTrustLevel.TRUSTED
    source_type: str = "internal"
    token_limit: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def slot_name(self) -> str:
        """返回稳定的字符串槽位名。"""
        return self.name.value if isinstance(self.name, Enum) else str(self.name)

    def render_content(self) -> str:
        """把 slot 内容渲染为稳定的 prompt 文本。"""
        if isinstance(self.content, str):
            return self.content
        return json.dumps(self.content, ensure_ascii=False, indent=2, default=str)


@dataclass
class BuiltContextSlot:
    """经过清洗、压缩和整体预算处理后的上下文槽位。"""

    name: str
    role: str
    source_type: str
    trust_level: str
    priority: int
    content: str
    original_tokens: int
    injected_tokens: int
    was_truncated: bool = False
    truncation_reason: str | None = None
    content_hash: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class BuiltContext:
    """一次 LLM 调用最终使用的 prompt 片段和上下文元数据。"""

    task_name: str
    system_prompt: str
    user_prompt: str
    token_budget: int
    total_tokens: int
    slots: list[BuiltContextSlot]
    truncation_summary: dict[str, Any] = field(default_factory=dict)
    sanitizer_summary: dict[str, Any] = field(default_factory=dict)
    memory_usage_summary: dict[str, Any] = field(default_factory=dict)

    @property
    def injected_slot_names(self) -> list[str]:
        """返回所有实际注入 prompt 的槽位名。"""
        return [slot.name for slot in self.slots if slot.injected_tokens > 0]
