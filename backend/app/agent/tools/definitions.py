from enum import StrEnum
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field

from app.agent.schemas.execution import ArtifactRef


class ToolName(StrEnum):
    """冻结的十七个 Core Tool 名称。"""

    QUERY_GROWTH_CONTEXT = "query_growth_context"
    QUERY_ARTIFACT = "query_artifact"
    RETRIEVE_RESEARCH_EVIDENCE = "retrieve_research_evidence"
    QUERY_POST_PUBLISH_METRICS = "query_post_publish_metrics"
    COLLECT_XHS_NOTES = "collect_xhs_notes"
    COLLECT_XHS_ACCOUNTS = "collect_xhs_accounts"
    ANALYZE_RESEARCH = "analyze_research"
    GENERATE_CONTENT_STRATEGY = "generate_content_strategy"
    GENERATE_DRAFT = "generate_draft"
    REVIEW_DRAFT = "review_draft"
    REVISE_DRAFT = "revise_draft"
    ANALYZE_POST_PUBLISH_REVIEW = "analyze_post_publish_review"
    CREATE_RESEARCH_ARTIFACT = "create_research_artifact"
    CREATE_CONTENT_STRATEGY_ARTIFACT = "create_content_strategy_artifact"
    CREATE_DRAFT_VERSION = "create_draft_version"
    CREATE_POST_PUBLISH_REVIEW_ARTIFACT = "create_post_publish_review_artifact"
    CREATE_STRATEGY_CANDIDATE = "create_strategy_candidate"


class ToolEffect(StrEnum):
    """Tool 可能声明的完整 Effect 集合。"""

    PURE = "PURE"
    READ_INTERNAL = "READ_INTERNAL"
    COLLECT_PUBLIC = "COLLECT_PUBLIC"
    CREATE_DERIVED = "CREATE_DERIVED"
    UPDATE_USER_STATE = "UPDATE_USER_STATE"
    EXTERNAL_WRITE = "EXTERNAL_WRITE"
    DESTRUCTIVE = "DESTRUCTIVE"


class CoreToolInput(BaseModel):
    """Phase 2.1 Core Tool 的通用输入边界，具体字段由 Phase 2.2 专门化。"""

    model_config = ConfigDict(extra="forbid")

    account_ref: int | None = Field(default=None, gt=0)
    artifact_refs: list[ArtifactRef] = Field(default_factory=list)
    parameters: dict[str, Any] = Field(default_factory=dict)


class CoreToolOutput(BaseModel):
    """Phase 2.1 Core Tool 的通用输出边界。"""

    model_config = ConfigDict(extra="forbid")

    artifacts: list[ArtifactRef] = Field(default_factory=list)
    payload: dict[str, Any] = Field(default_factory=dict)


class ToolDefinition(BaseModel):
    """不包含 handler、Service 或 Provider 的静态 Tool 定义。"""

    model_config = ConfigDict(extra="forbid", frozen=True, arbitrary_types_allowed=True)

    name: ToolName
    description: str = Field(min_length=1)
    input_model: type[BaseModel]
    output_model: type[BaseModel]
    effect: ToolEffect
    version: str = Field(pattern=r"^v\d+$")


class ToolError(BaseModel):
    """Tool 失败时的统一、安全错误合同。"""

    model_config = ConfigDict(extra="forbid")

    code: str = Field(min_length=1)
    category: str = Field(min_length=1)
    retryable: bool
    user_action: str | None = None
    safe_message: str = Field(min_length=1)


ToolData = TypeVar("ToolData")


class ToolResult(BaseModel, Generic[ToolData]):
    """Tool 的统一执行结果；失败时禁止携带伪业务数据。"""

    model_config = ConfigDict(extra="forbid")

    success: bool
    data: ToolData | None = None
    warnings: list[str] = Field(default_factory=list)
    error: ToolError | None = None
    trace_ref: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    def model_post_init(self, __context: Any) -> None:
        """校验成功与失败结果之间的数据和错误互斥关系。"""
        if self.success and self.error is not None:
            raise ValueError("成功 ToolResult 不得包含 error")
        if not self.success and self.data is not None:
            raise ValueError("失败 ToolResult 不得包含伪业务 data")
        if not self.success and self.error is None:
            raise ValueError("失败 ToolResult 必须包含 error")
