from dataclasses import dataclass

from app.context.context_slots import BuiltContextSlot


DEFAULT_CONTEXT_BUDGETS = {
    "default": 4000,
    "draft_generation": 6000,
    "draft_regeneration": 5000,
    "competitor_analysis": 7000,
    "review_report": 6000,
    "agent_step": 3000,
}


def estimate_tokens(value: str | None) -> int:
    """Estimate tokens without introducing a tokenizer dependency."""
    if not value:
        return 0
    ascii_chars = sum(1 for char in value if ord(char) < 128)
    non_ascii_chars = len(value) - ascii_chars
    return max(1, (ascii_chars + (non_ascii_chars * 2) + 3) // 4)


def trim_to_token_budget(value: str, max_tokens: int) -> tuple[str, bool]:
    """Trim text to an approximate token budget."""
    if max_tokens <= 0:
        return "", bool(value)
    if estimate_tokens(value) <= max_tokens:
        return value, False
    max_chars = max(0, max_tokens * 4)
    marker = "\n[TRUNCATED_BY_CONTEXT_BUDGET]"
    if max_chars <= len(marker):
        return marker[:max_chars], True
    return value[: max_chars - len(marker)] + marker, True


@dataclass(frozen=True)
class ContextBudgetReport:
    """Budget application details."""

    token_budget: int
    original_tokens: int
    injected_tokens: int
    truncated_slots: list[str]
    dropped_slots: list[str]


class ContextBudgetManager:
    """Apply per-task prompt token budgets to context slots."""

    def __init__(self, budgets: dict[str, int] | None = None):
        self.budgets = {**DEFAULT_CONTEXT_BUDGETS, **(budgets or {})}

    def budget_for(self, task_name: str, override: int | None = None) -> int:
        """Resolve a budget for a task."""
        if override is not None:
            return override
        return self.budgets.get(task_name, self.budgets["default"])

    def apply(self, slots: list[BuiltContextSlot], token_budget: int) -> tuple[list[BuiltContextSlot], ContextBudgetReport]:
        """Trim or drop lower-priority slots until the budget is satisfied."""
        original_tokens = sum(slot.original_tokens for slot in slots)
        remaining = token_budget
        result: list[BuiltContextSlot] = []
        truncated: list[str] = []
        dropped: list[str] = []

        for slot in sorted(slots, key=lambda item: item.priority, reverse=True):
            if remaining <= 0:
                slot.content = ""
                slot.injected_tokens = 0
                slot.was_truncated = True
                slot.truncation_reason = "dropped_by_token_budget"
                dropped.append(slot.name)
                result.append(slot)
                continue

            target = min(slot.injected_tokens, remaining)
            content, was_trimmed = trim_to_token_budget(slot.content, target)
            if was_trimmed:
                slot.was_truncated = True
                slot.truncation_reason = "trimmed_by_token_budget"
                truncated.append(slot.name)
            slot.content = content
            slot.injected_tokens = estimate_tokens(content)
            remaining -= slot.injected_tokens
            result.append(slot)

        order = {slot.name: index for index, slot in enumerate(slots)}
        ordered = sorted(result, key=lambda item: order[item.name])
        injected_tokens = sum(slot.injected_tokens for slot in ordered)
        return ordered, ContextBudgetReport(token_budget, original_tokens, injected_tokens, truncated, dropped)

