from enum import StrEnum


class AgentRunStatus(StrEnum):
    """AgentRun 状态枚举。"""

    RUNNING = "RUNNING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    STOPPED = "STOPPED"
    REQUIRES_CONFIRMATION = "REQUIRES_CONFIRMATION"
    RISK_BLOCKED = "RISK_BLOCKED"


class AgentStepStatus(StrEnum):
    """AgentStep 状态枚举。"""

    RUNNING = "RUNNING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    FALLBACK_USED = "FALLBACK_USED"
    SKIPPED = "SKIPPED"
    RISK_BLOCKED = "RISK_BLOCKED"
    REQUIRES_CONFIRMATION = "REQUIRES_CONFIRMATION"


class ToolType(StrEnum):
    """工具类型枚举。"""

    LOCAL = "LOCAL"
    MCP = "MCP"
    FALLBACK = "FALLBACK"


class ToolRiskLevel(StrEnum):
    """工具风险等级枚举。"""

    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
