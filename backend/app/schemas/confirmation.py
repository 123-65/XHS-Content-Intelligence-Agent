from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.enums.confirmation import ConfirmationDecisionType, ConfirmationTaskStatus, ConfirmationType


class ConfirmationTaskCreate(BaseModel):
    """Request body for creating a human confirmation task."""

    confirmation_type: ConfirmationType
    target_id: int
    account_id: int | None = None
    target_type: str | None = None
    created_by: str | None = None
    extra_context: dict = Field(default_factory=dict)


class ConfirmationDecisionCreate(BaseModel):
    """Request body for submitting a human decision."""

    decision: ConfirmationDecisionType
    decided_by: str | None = None
    comment: str | None = None
    revision_request: dict = Field(default_factory=dict)


class ConfirmationAuditLogResponse(BaseModel):
    """Response model for a confirmation audit log."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    task_id: int
    event_type: str
    from_status: str | None
    to_status: str
    actor: str | None
    reason: str | None
    metadata_payload: dict
    created_at: datetime


class ConfirmationDecisionResponse(BaseModel):
    """Response model for a confirmation decision."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    task_id: int
    decision: str
    decided_by: str | None
    comment: str | None
    revision_request: dict
    created_at: datetime


class ConfirmationTaskResponse(BaseModel):
    """Response model for a human confirmation task."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    account_id: int
    confirmation_type: str
    target_type: str
    target_id: int
    target_version: int | None
    status: str
    summary: str
    recommendation: str
    risk_level: str
    risk_reason: str | None
    payload_snapshot: dict
    invalidated_reason: str | None
    created_by: str | None
    created_at: datetime
    updated_at: datetime
    decisions: list[ConfirmationDecisionResponse] = Field(default_factory=list)
    audit_logs: list[ConfirmationAuditLogResponse] = Field(default_factory=list)


class PendingConfirmationResponse(BaseModel):
    """Response model for pending confirmation tasks."""

    account_id: int | None
    count: int
    tasks: list[ConfirmationTaskResponse]
