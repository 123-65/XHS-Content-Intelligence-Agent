from enum import StrEnum


class MetricSnapshotWindow(StrEnum):
    """Supported post-publish metric windows."""

    H24 = "24h"
    H48 = "48h"
    H72 = "72h"
    D7 = "7d"


class ReviewResultStatus(StrEnum):
    """Post-publish experiment review result."""

    SUCCESS = "SUCCESS"
    PARTIAL_SUCCESS = "PARTIAL_SUCCESS"
    FAILED = "FAILED"
    INCONCLUSIVE = "INCONCLUSIVE"
    RISKY_SUCCESS = "RISKY_SUCCESS"


class StrategyMemoryType(StrEnum):
    """Strategy memory types."""

    TOPIC_MEMORY = "TOPIC_MEMORY"
    TITLE_MEMORY = "TITLE_MEMORY"
    COVER_MEMORY = "COVER_MEMORY"
    STRUCTURE_MEMORY = "STRUCTURE_MEMORY"
    CTA_MEMORY = "CTA_MEMORY"
    AUDIENCE_MEMORY = "AUDIENCE_MEMORY"
    RISK_MEMORY = "RISK_MEMORY"
    NEGATIVE_MEMORY = "NEGATIVE_MEMORY"


class StrategyMemoryStatus(StrEnum):
    """Strategy memory validation status."""

    CANDIDATE = "CANDIDATE"
    VALIDATED = "VALIDATED"
    REJECTED = "REJECTED"
    ARCHIVED = "ARCHIVED"


class OptimizationPlanType(StrEnum):
    """Next-round content optimization plan types."""

    SCALE = "SCALE"
    REPAIR = "REPAIR"
    EXPLORE = "EXPLORE"
    CONVERT = "CONVERT"
    PAUSE = "PAUSE"
    REFRESH = "REFRESH"
