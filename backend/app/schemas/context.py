from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ContextSlotLogResponse(BaseModel):
    """Per-slot context log response."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    context_snapshot_id: int
    slot_name: str
    role: str
    source_type: str
    trust_level: str
    priority: int
    original_tokens: int
    injected_tokens: int
    token_ratio: Decimal
    was_truncated: bool
    truncation_reason: str | None
    content_hash: str | None
    content_preview: str | None
    metadata_payload: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime


class ContextSnapshotResponse(BaseModel):
    """Context snapshot response."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    agent_run_id: int | None
    agent_step_id: int | None
    prompt_run_log_id: int | None
    task_name: str
    model: str | None
    provider: str | None
    token_budget: int
    total_tokens: int
    system_tokens: int
    user_tokens: int
    memory_count: int
    memory_tokens: int
    slot_count: int
    truncated: bool
    injected_slot_names: list[str]
    slot_token_breakdown: list[dict[str, Any]]
    truncation_summary: dict[str, Any]
    sanitizer_summary: dict[str, Any]
    memory_usage_summary: dict[str, Any]
    prompt_hash: str
    prompt_preview: str | None
    created_at: datetime
    slot_logs: list[ContextSlotLogResponse] = Field(default_factory=list)


class AgentRunContextResponse(BaseModel):
    """All context snapshots for an agent run."""

    agent_run_id: int
    snapshots: list[ContextSnapshotResponse] = Field(default_factory=list)


class TraceRetentionPolicyResponse(BaseModel):
    """Public trace retention policy response."""

    log_table: str
    retention_days: int
    max_raw_chars: int
    summary_chars: int
    raw_payload_policy: str
    hash_algorithm: str
    redact_sensitive: bool
    sensitive_fields: list[str]
    redact_patterns: list[str]

