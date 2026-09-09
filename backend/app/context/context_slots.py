import json
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class ContextSlotName(str, Enum):
    """Canonical context slots used before LLM calls."""

    SYSTEM_RULES = "system_rules"
    TASK_INSTRUCTION = "task_instruction"
    ACCOUNT_PROFILE = "account_profile"
    USER_INPUT = "user_input"
    WORKFLOW_STATE = "workflow_state"
    TOOL_RESULT = "tool_result"
    STRATEGY_MEMORY = "strategy_memory"
    RISK_CONSTRAINTS = "risk_constraints"
    OUTPUT_SCHEMA = "output_schema"


class ContextTrustLevel(str, Enum):
    """Trust labels used to prevent external text from becoming instructions."""

    TRUSTED = "trusted"
    UNTRUSTED = "untrusted"


class ContextRole(str, Enum):
    """Target prompt role for a context slot."""

    SYSTEM = "system"
    USER = "user"


@dataclass
class ContextSlot:
    """A single typed piece of context injected into an LLM prompt."""

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
        """Return the stable string slot name."""
        return self.name.value if isinstance(self.name, Enum) else str(self.name)

    def render_content(self) -> str:
        """Render slot content into stable prompt text."""
        if isinstance(self.content, str):
            return self.content
        return json.dumps(self.content, ensure_ascii=False, indent=2, default=str)


@dataclass
class BuiltContextSlot:
    """A slot after sanitization, compression, and budget trimming."""

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
    """Final prompt pieces and metadata for one LLM call."""

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
        """Return names for all injected slots."""
        return [slot.name for slot in self.slots if slot.injected_tokens > 0]

