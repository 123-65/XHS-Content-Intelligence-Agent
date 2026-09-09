from enum import StrEnum


class ConfirmationType(StrEnum):
    """Supported human confirmation task types."""

    EXPERIMENT_CONFIRM = "EXPERIMENT_CONFIRM"
    DRAFT_CONFIRM = "DRAFT_CONFIRM"
    REVIEW_CONFIRM = "REVIEW_CONFIRM"
    PUBLISH_CONFIRM = "PUBLISH_CONFIRM"
    HIGH_RISK_CONFIRM = "HIGH_RISK_CONFIRM"


class ConfirmationDecisionType(StrEnum):
    """Supported human decision types."""

    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    REVISION_REQUESTED = "REVISION_REQUESTED"
    REGENERATE_REQUESTED = "REGENERATE_REQUESTED"
    PAUSED = "PAUSED"
    CANCELLED = "CANCELLED"


class ConfirmationTaskStatus(StrEnum):
    """Human confirmation task status values."""

    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    REVISION_REQUESTED = "REVISION_REQUESTED"
    REGENERATE_REQUESTED = "REGENERATE_REQUESTED"
    PAUSED = "PAUSED"
    CANCELLED = "CANCELLED"
    INVALIDATED = "INVALIDATED"
