from enum import StrEnum


class CommentDemandType(StrEnum):
    """评论需求分类。"""

    ROUTE = "ROUTE"
    RESOURCE = "RESOURCE"
    PROJECT = "PROJECT"
    SOURCE_CODE = "SOURCE_CODE"
    PRICE = "PRICE"
    COURSE = "COURSE"
    CONSULTATION = "CONSULTATION"
    ANXIETY = "ANXIETY"
    MARKETING_RESISTANCE = "MARKETING_RESISTANCE"
    UNKNOWN = "UNKNOWN"


class RiskLevel(StrEnum):
    """风险等级。"""

    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
