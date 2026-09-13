import hashlib
from typing import Any

from app.context.context_budget import ContextBudgetManager, build_slot_budget_meta, estimate_tokens, trim_to_token_budget
from app.context.context_compressor import ToolResultCompressor, select_competitor_evidence_top_k
from app.context.context_sanitizer import ContextSanitizer
from app.context.context_slots import BuiltContext, BuiltContextSlot, ContextRole, ContextSlot, ContextSlotName, ContextTrustLevel


class ContextManager:
    """为一次 LLM 调用构建受治理的上下文。"""

    def __init__(
        self,
        task_name: str = "default",
        token_budget: int | None = None,
        budgets: dict[str, int] | None = None,
    ):
        self.task_name = task_name
        self.budget_manager = ContextBudgetManager(budgets)
        self.token_budget = self.budget_manager.budget_for(task_name, token_budget)
        self.sanitizer = ContextSanitizer()
        self.compressor = ToolResultCompressor()
        self.slots: list[ContextSlot] = []

    def add_slot(self, slot: ContextSlot) -> "ContextManager":
        """向上下文管理器添加一个 slot。"""
        self.slots.append(slot)
        return self

    def extend(self, slots: list[ContextSlot]) -> "ContextManager":
        """批量添加多个 slot。"""
        self.slots.extend(slots)
        return self

    def build(self) -> BuiltContext:
        """生成最终 system/user prompt，并附带快照所需元数据。"""
        built_slots = [self._prepare_slot(slot) for slot in self.slots]
        budgeted_slots, report = self.budget_manager.apply(built_slots, self.token_budget)
        system_sections = [self._format_slot(slot) for slot in budgeted_slots if slot.role == ContextRole.SYSTEM.value and slot.injected_tokens > 0]
        user_sections = [self._format_slot(slot) for slot in budgeted_slots if slot.role != ContextRole.SYSTEM.value and slot.injected_tokens > 0]
        system_prompt = "\n\n".join(system_sections)
        user_prompt = "\n\n".join(user_sections)
        sanitizer_summary = self._sanitizer_summary(budgeted_slots)
        memory_slots = [slot for slot in budgeted_slots if slot.name == ContextSlotName.STRATEGY_MEMORY.value and slot.injected_tokens > 0]
        return BuiltContext(
            task_name=self.task_name,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            token_budget=self.token_budget,
            total_tokens=estimate_tokens(system_prompt) + estimate_tokens(user_prompt),
            slots=budgeted_slots,
            truncation_summary={
                "original_tokens": report.original_tokens,
                "injected_tokens": report.injected_tokens,
                "truncated_slots": report.truncated_slots,
                "dropped_slots": report.dropped_slots,
            },
            sanitizer_summary=sanitizer_summary,
            memory_usage_summary={
                "slot_count": len(memory_slots),
                "tokens": sum(slot.injected_tokens for slot in memory_slots),
                "used": bool(memory_slots),
            },
        )

    def _prepare_slot(self, slot: ContextSlot) -> BuiltContextSlot:
        if slot.slot_name == ContextSlotName.COMPETITOR_EVIDENCE.value and isinstance(slot.content, list):
            selected, compression_meta = select_competitor_evidence_top_k(
                slot.content,
                top_k=slot.metadata.get("top_k", 5),
                query_context=slot.metadata.get("query_context"),
            )
            slot.content = selected
            slot.metadata = {
                **slot.metadata,
                "compression_meta": compression_meta,
            }

        if slot.slot_name == ContextSlotName.TOOL_RESULT.value:
            compressed = self.compressor.compress(
                slot.content,
                top_k=slot.metadata.get("top_k"),
                allowed_fields=slot.metadata.get("allowed_fields"),
                max_tokens=slot.token_limit,
            )
            slot.content = compressed["summary"]
            slot.metadata = {
                **slot.metadata,
                "compression": compressed["compression"],
                "raw_hash": compressed["raw_hash"],
                "raw_length": compressed["raw_length"],
            }

        sanitized = self.sanitizer.sanitize_slot(slot)
        rendered = sanitized.slot.render_content()
        metadata: dict[str, Any] = {**sanitized.slot.metadata}
        if sanitized.warnings:
            metadata["sanitizer_warnings"] = sanitized.warnings

        original_tokens = estimate_tokens(rendered)
        injected = rendered
        was_truncated = False
        if sanitized.slot.token_limit:
            injected, was_truncated = trim_to_token_budget(rendered, sanitized.slot.token_limit)

        role = sanitized.slot.role.value if isinstance(sanitized.slot.role, ContextRole) else str(sanitized.slot.role)
        trust_level = sanitized.slot.trust_level.value if isinstance(sanitized.slot.trust_level, ContextTrustLevel) else str(sanitized.slot.trust_level)
        metadata["budget_meta"] = build_slot_budget_meta(
            sanitized.slot.slot_name,
            injected,
            source=sanitized.slot.source_type,
            source_version=metadata.get("source_version"),
            data_status=metadata.get("data_status"),
        )
        if metadata.get("compression_meta"):
            metadata["budget_meta"].update(metadata["compression_meta"])
        if was_truncated:
            metadata["budget_meta"]["truncated"] = True
        return BuiltContextSlot(
            name=sanitized.slot.slot_name,
            role=role,
            source_type=sanitized.slot.source_type,
            trust_level=trust_level,
            priority=sanitized.slot.priority,
            content=injected,
            original_tokens=original_tokens,
            injected_tokens=estimate_tokens(injected),
            was_truncated=was_truncated,
            truncation_reason="slot_token_limit" if was_truncated else None,
            content_hash=hashlib.sha256(rendered.encode("utf-8")).hexdigest(),
            metadata=metadata,
        )

    def _format_slot(self, slot: BuiltContextSlot) -> str:
        return f"## 上下文槽位：{slot.name}\n{slot.content}"

    def _sanitizer_summary(self, slots: list[BuiltContextSlot]) -> dict[str, Any]:
        warnings = []
        untrusted = []
        for slot in slots:
            if slot.trust_level == "untrusted":
                untrusted.append(slot.name)
            warnings.extend(slot.metadata.get("sanitizer_warnings", []))
        return {"untrusted_slots": untrusted, "warnings": sorted(set(warnings))}
