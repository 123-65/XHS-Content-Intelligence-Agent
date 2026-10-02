from enum import StrEnum

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, field_validator


class Intent(StrEnum):
    """冻结的十二种顶层用户意图。"""

    GENERAL_CHAT = "GENERAL_CHAT"
    RESEARCH = "RESEARCH"
    CONTENT_STRATEGY = "CONTENT_STRATEGY"
    CONTENT_CREATE = "CONTENT_CREATE"
    CONTENT_REFINE = "CONTENT_REFINE"
    POST_PUBLISH_REVIEW = "POST_PUBLISH_REVIEW"
    QUERY_PROFILE = "QUERY_PROFILE"
    UPDATE_PROFILE = "UPDATE_PROFILE"
    QUERY_HISTORY = "QUERY_HISTORY"
    UPDATE_STRATEGY = "UPDATE_STRATEGY"
    CANCEL_TASK = "CANCEL_TASK"
    UNKNOWN = "UNKNOWN"


class SemanticReferenceType(StrEnum):
    """Semantic Layer 与 Resolver 共用的小型引用词汇。"""

    RECENT_RESEARCH = "RECENT_RESEARCH"
    ACTIVE_RESEARCH = "ACTIVE_RESEARCH"
    ORDINAL_OPPORTUNITY = "ORDINAL_OPPORTUNITY"
    ACTIVE_STRATEGY = "ACTIVE_STRATEGY"
    ACTIVE_DRAFT = "ACTIVE_DRAFT"
    RECENT_DRAFT = "RECENT_DRAFT"
    TEMPORAL_PUBLISHED_NOTE = "TEMPORAL_PUBLISHED_NOTE"
    ACTIVE_PUBLISHED_NOTE = "ACTIVE_PUBLISHED_NOTE"
    LATEST_PUBLISHED_NOTE = "LATEST_PUBLISHED_NOTE"
    RECENT_RUN = "RECENT_RUN"
    PROFILE = "PROFILE"
    ACCOUNT = "ACCOUNT"
    UNKNOWN = "UNKNOWN"


class SemanticReference(BaseModel):
    """尚未解析身份的自然语言引用；绝不承载数据库 ID。"""

    model_config = ConfigDict(extra="forbid")

    type: SemanticReferenceType
    raw_text: str = Field(min_length=1)
    ordinal: int | None = Field(default=None, gt=0)
    temporal_hint: str | None = None


class TaskSemanticFrame(BaseModel):
    """Router 对一轮用户输入形成的纯语义合同，不解析数据库标识。"""

    model_config = ConfigDict(extra="forbid")

    primary_intent: Intent
    primary_goal: str | None = None
    sub_goals: list[Intent] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list)
    references: list[SemanticReference] = Field(default_factory=list)
    scope_limits: list[str] = Field(default_factory=list)
    expected_deliverable: str | None = None
    note_urls: list[str] = Field(default_factory=list)
    profile_urls: list[str] = Field(default_factory=list)
    refresh_public_metrics: bool = False
    missing_info: list[str] = Field(
        default_factory=list,
        validation_alias=AliasChoices("missing_info", "missing_information"),
    )
    conflicts: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0, le=1)

    @field_validator("references", mode="before")
    @classmethod
    def accept_legacy_reference_strings(cls, value):
        """兼容 2.5A 早期字符串引用；无法可靠分类时明确标记 UNKNOWN。"""
        if not isinstance(value, list):
            return value
        return [
            {"type": SemanticReferenceType.UNKNOWN, "raw_text": item}
            if isinstance(item, str)
            else item
            for item in value
        ]

    @property
    def missing_information(self) -> list[str]:
        """兼容 Phase 2.1 早期字段名；正式输出字段为 missing_info。"""
        return self.missing_info
