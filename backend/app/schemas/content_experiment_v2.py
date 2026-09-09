from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


ExperimentV2Status = Literal[
    "CANDIDATE",
    "APPROVED",
    "DRAFTING",
    "REVIEWING",
    "READY_TO_PUBLISH",
    "PUBLISHED",
    "METRICS_PENDING",
    "ANALYZED",
    "PAUSED",
    "FAILED",
]


class GenerateExperimentsRequest(BaseModel):
    """生成候选内容实验请求。"""

    account_id: int
    report_id: int | None = None
    limit: int = Field(default=3, ge=3, le=5)


class ExperimentVariableCreate(BaseModel):
    """创建实验变量数据。"""

    experiment_id: int = 0
    variable_name: str = Field(min_length=1, max_length=128)
    variable_type: str = Field(min_length=1, max_length=32)
    variable_value: dict = Field(default_factory=dict)
    description: str | None = None


class ExperimentMetricTargetCreate(BaseModel):
    """创建实验指标目标数据。"""

    experiment_id: int = 0
    metric_name: str = Field(min_length=1, max_length=64)
    metric_type: str = Field(min_length=1, max_length=32)
    target_value: Decimal = Field(default=0, ge=0)
    comparison_operator: str = Field(default=">=", max_length=16)
    description: str | None = None


class ExperimentCardCreate(BaseModel):
    """创建 V2 实验卡数据。"""

    account_id: int
    analysis_report_id: int | None = None
    content_opportunity_id: int | None = None
    experiment_name: str
    hypothesis: str
    content_pillar: str
    content_format: str
    main_variable: str
    control_variables: list[dict] = Field(default_factory=list)
    primary_metric: str
    secondary_metrics: list[str] = Field(default_factory=list)
    success_criteria: dict = Field(default_factory=dict)
    failure_criteria: dict = Field(default_factory=dict)
    fallback_strategy: str | None = None
    risk_level: str = "LOW"
    target_metric: str
    expected_result: str | None = None
    topic_angle: str | None = None
    selected_topic: str | None = None
    target_values: dict = Field(default_factory=dict)
    source_type: str = "CONTENT_OPPORTUNITY"
    status: ExperimentV2Status = "CANDIDATE"
    variables: list[ExperimentVariableCreate] = Field(default_factory=list)
    metric_targets: list[ExperimentMetricTargetCreate] = Field(default_factory=list)


class ExperimentVariableResponse(BaseModel):
    """实验变量响应。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    experiment_id: int
    variable_name: str
    variable_type: str
    variable_value: dict
    description: str | None
    created_at: datetime


class ExperimentMetricTargetResponse(BaseModel):
    """实验指标目标响应。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    experiment_id: int
    metric_name: str
    metric_type: str
    target_value: Decimal
    comparison_operator: str
    description: str | None
    created_at: datetime


class ExperimentCardResponse(BaseModel):
    """实验卡响应。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    account_id: int
    analysis_report_id: int | None
    content_opportunity_id: int | None
    experiment_name: str
    hypothesis: str
    content_pillar: str
    content_format: str
    main_variable: str | None
    control_variables: list[dict]
    primary_metric: str
    secondary_metrics: list[str]
    success_criteria: dict
    failure_criteria: dict
    fallback_strategy: str | None
    risk_level: str
    target_metric: str
    expected_result: str | None
    topic_angle: str | None
    selected_topic: str | None
    target_values: dict
    source_type: str
    status: str
    publish_url: str | None
    published_at: datetime | None
    created_at: datetime
    updated_at: datetime
    variables: list[ExperimentVariableResponse] = Field(default_factory=list)
    metric_targets: list[ExperimentMetricTargetResponse] = Field(default_factory=list)


class GenerateExperimentsResponse(BaseModel):
    """生成候选实验响应。"""

    account_id: int
    count: int
    experiments: list[ExperimentCardResponse]
