from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

ExperimentCreateStatus = Literal["WAITING_CONFIRMATION", "CREATED", "DATA_INSUFFICIENT", "FAILED"]


class OperationExperimentRequest(BaseModel):
    """Request for creating a local content experiment from an operation recommendation."""

    account_id: int = Field(gt=0)
    confirmed: bool = False
    experiment_name: str | None = Field(default=None, max_length=128)
    target_metric: Literal["like", "collect", "comment", "lead", "order", "engagement"] = "collect"
    notes: str | None = Field(default=None, max_length=512)


class OperationExperimentResponse(BaseModel):
    """Preview or creation result for a recommendation-backed content experiment."""

    model_config = ConfigDict(from_attributes=True)

    status: ExperimentCreateStatus
    run_id: int
    rank: int
    account_id: int | None = None
    opportunity_id: int | None = None
    experiment_id: int | None = None
    preview: dict[str, Any] = Field(default_factory=dict)
    confirmation: dict[str, Any] = Field(default_factory=dict)
    error_code: str | None = None
    error_message: str | None = None
