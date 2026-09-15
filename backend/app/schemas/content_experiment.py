from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


ExperimentStatus = Literal["DRAFT", "READY", "PUBLISHED", "METRICS_COLLECTED", "ANALYZED", "FAILED"]
ExperimentTargetMetric = Literal["like", "collect", "comment", "lead", "order", "engagement"]
ExperimentSourceType = Literal[
    "COMPETITOR_ANALYSIS",
    "USER_IDEA",
    "MANUAL_TOPIC",
    "STRATEGY_RECOMMENDATION",
    "OPERATION_RUN_RECOMMENDATION",
]


class ContentExperimentCreate(BaseModel):
    """创建内容实验请求。"""

    account_id: int
    analysis_report_id: int | None = None
    experiment_name: str = Field(min_length=1, max_length=128)
    hypothesis: str = Field(min_length=1)
    target_metric: ExperimentTargetMetric = "collect"
    expected_result: str | None = None
    topic_angle: str | None = Field(default=None, max_length=256)
    selected_topic: str | None = Field(default=None, max_length=256)
    target_values: dict = Field(default_factory=dict)
    source_type: ExperimentSourceType = "COMPETITOR_ANALYSIS"


class ContentExperimentUpdate(BaseModel):
    """更新内容实验请求。"""

    experiment_name: str | None = Field(default=None, min_length=1, max_length=128)
    hypothesis: str | None = Field(default=None, min_length=1)
    target_metric: ExperimentTargetMetric | None = None
    expected_result: str | None = None
    topic_angle: str | None = Field(default=None, max_length=256)
    selected_topic: str | None = Field(default=None, max_length=256)
    target_values: dict | None = None
    status: ExperimentStatus | None = None
    publish_url: str | None = Field(default=None, max_length=1024)
    published_at: datetime | None = None


class CreateExperimentFromAnalysisRequest(BaseModel):
    """基于竞品分析报告创建实验请求。"""

    account_id: int
    experiment_name: str | None = Field(default=None, max_length=128)
    selected_topic: str | None = Field(default=None, max_length=256)
    topic_angle: str | None = Field(default=None, max_length=256)
    target_metric: ExperimentTargetMetric = "collect"
    target_values: dict = Field(default_factory=lambda: {"collect_count": 100, "comment_count": 20, "lead_count": 5})


class ContentExperimentResponse(BaseModel):
    """内容实验响应。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    account_id: int
    analysis_report_id: int | None
    experiment_name: str
    hypothesis: str
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
