from enum import StrEnum


class KeywordCategory(StrEnum):
    """关键词分类。"""

    USER_DEMAND = "USER_DEMAND"
    MEDIA_EXPRESSION = "MEDIA_EXPRESSION"
    CONVERSION_SIGNAL = "CONVERSION_SIGNAL"
    PEER_IDENTITY = "PEER_IDENTITY"
