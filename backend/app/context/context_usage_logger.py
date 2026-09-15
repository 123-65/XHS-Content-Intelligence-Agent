from sqlalchemy import select
from sqlalchemy.orm import Session

from app.context.context_budget import estimate_tokens
from app.context.context_slots import BuiltContext
from app.context.context_snapshot import TracePayloadGovernor
from app.models.context_snapshot import ContextSnapshot
from app.models.context_slot_log import ContextSlotLog


class ContextUsageLogger:
    """Persist context snapshot logs for LLM calls."""

    def __init__(self, db: Session):
        self.db = db
        self.governor = TracePayloadGovernor()

    def record_snapshot(
        self,
        built_context: BuiltContext,
        *,
        agent_run_id: int | None = None,
        agent_step_id: int | None = None,
        prompt_run_log_id: int | None = None,
        model: str | None = None,
        provider: str | None = None,
    ) -> ContextSnapshot:
        """Persist one snapshot and its slot logs."""
        full_prompt = f"{built_context.system_prompt}\n\n{built_context.user_prompt}"
        slot_breakdown = [
            {
                "slot_name": slot.name,
                "tokens": slot.injected_tokens,
                "budget_tokens": (slot.metadata.get("budget_meta") or {}).get("budget_tokens", 0),
                "ratio": round(slot.injected_tokens / max(1, built_context.total_tokens), 4),
                "truncated": slot.was_truncated,
            }
            for slot in built_context.slots
        ]
        snapshot = ContextSnapshot(
            agent_run_id=agent_run_id,
            agent_step_id=agent_step_id,
            prompt_run_log_id=prompt_run_log_id,
            task_name=built_context.task_name,
            model=model,
            provider=provider,
            token_budget=built_context.token_budget,
            total_tokens=built_context.total_tokens,
            system_tokens=estimate_tokens(built_context.system_prompt),
            user_tokens=estimate_tokens(built_context.user_prompt),
            memory_count=1 if built_context.memory_usage_summary.get("used") else 0,
            memory_tokens=int(built_context.memory_usage_summary.get("tokens") or 0),
            slot_count=len(built_context.slots),
            truncated=bool(built_context.truncation_summary.get("truncated_slots") or built_context.truncation_summary.get("dropped_slots")),
            injected_slot_names=built_context.injected_slot_names,
            slot_token_breakdown=slot_breakdown,
            truncation_summary=self.governor.govern_payload(built_context.truncation_summary, "context_snapshot"),
            sanitizer_summary=self.governor.govern_payload(built_context.sanitizer_summary, "context_snapshot"),
            memory_usage_summary=self.governor.govern_payload(built_context.memory_usage_summary, "context_snapshot"),
            prompt_hash=self.governor.hash_text(full_prompt),
            prompt_preview=self.governor.govern_text(full_prompt, "context_snapshot"),
        )
        self.db.add(snapshot)
        self.db.commit()
        self.db.refresh(snapshot)

        for slot in built_context.slots:
            self.db.add(
                ContextSlotLog(
                    context_snapshot_id=snapshot.id,
                    slot_name=slot.name,
                    role=slot.role,
                    source_type=slot.source_type,
                    trust_level=slot.trust_level,
                    priority=slot.priority,
                    original_tokens=slot.original_tokens,
                    injected_tokens=slot.injected_tokens,
                    token_ratio=round(slot.injected_tokens / max(1, built_context.total_tokens), 6),
                    was_truncated=slot.was_truncated,
                    truncation_reason=slot.truncation_reason,
                    content_hash=slot.content_hash,
                    content_preview=self.governor.govern_text(slot.content, "context_snapshot"),
                    metadata_payload=self.governor.govern_payload(slot.metadata, "context_snapshot"),
                )
            )
        self.db.commit()
        self.db.refresh(snapshot)
        return snapshot

    def get_snapshot(self, snapshot_id: int) -> ContextSnapshot | None:
        """Return one context snapshot."""
        return self.db.get(ContextSnapshot, snapshot_id)

    def list_snapshots_for_run(self, agent_run_id: int) -> list[ContextSnapshot]:
        """Return context snapshots for an agent run."""
        stmt = select(ContextSnapshot).where(ContextSnapshot.agent_run_id == agent_run_id).order_by(ContextSnapshot.created_at.desc(), ContextSnapshot.id.desc())
        return list(self.db.execute(stmt).scalars().all())

