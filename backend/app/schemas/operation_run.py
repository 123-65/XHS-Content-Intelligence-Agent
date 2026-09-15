from datetime import date, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class OperationRunStatus(StrEnum):
    """Readonly operation analysis run status."""

    SUCCESS = "SUCCESS"
    PARTIAL = "PARTIAL"
    DATA_INSUFFICIENT = "DATA_INSUFFICIENT"
    FAILED = "FAILED"


class OperationRunCreate(BaseModel):
    """Create a readonly operation analysis run."""

    account_id: int = Field(gt=0)
    evidence_refresh_run_id: int | None = Field(default=None, gt=0)
    data_refresh_run_id: int | None = Field(default=None, gt=0)
    analysis_date: date | None = None


class OperationRunResponse(BaseModel):
    """Readonly operation analysis run response."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    account_id: int
    data_refresh_run_id: int | None
    evidence_refresh_run_id: int | None
    report_id: int | None
    trigger_type: str
    status: str
    analysis_date: date | None
    summary: str | None
    recommendations: list[dict[str, Any]]
    data_gaps: list[dict[str, Any]]
    next_actions: list[dict[str, Any]]
    stats: dict[str, Any]
    error_code: str | None
    error_message: str | None
    started_at: datetime | None
    finished_at: datetime | None
    created_at: datetime
    updated_at: datetime
