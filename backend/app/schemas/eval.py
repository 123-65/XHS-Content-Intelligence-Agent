from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class EvalCaseCreate(BaseModel):
    """Data required to store an evaluation case."""

    suite_name: str
    case_key: str
    eval_type: str
    input_payload: dict = Field(default_factory=dict)
    expected_output: dict = Field(default_factory=dict)
    case_metadata: dict = Field(default_factory=dict)
    is_active: bool = True


class EvalRunCreate(BaseModel):
    """Data required to store an evaluation run."""

    eval_type: str
    dataset_path: str
    status: str = "SUCCESS"
    total_cases: int = 0
    passed_cases: int = 0
    failed_cases: int = 0
    pass_rate: Decimal = Decimal("0")
    failed_reasons: list[dict] = Field(default_factory=list)
    report_path: str | None = None


class EvalCaseResult(BaseModel):
    """Single evaluation case result."""

    case_id: str
    passed: bool
    reason: str | None = None
    actual_output: dict = Field(default_factory=dict)


class EvalReport(BaseModel):
    """Evaluation report payload."""

    eval_type: str
    dataset_path: str
    total_cases: int
    passed_cases: int
    failed_cases: int
    pass_rate: Decimal
    failed_reasons: list[dict] = Field(default_factory=list)
    case_results: list[EvalCaseResult] = Field(default_factory=list)
    report_path: str | None = None
    eval_run_id: int | None = None


class EvalRunResponse(BaseModel):
    """Response model for an evaluation run."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    eval_type: str
    dataset_path: str
    status: str
    total_cases: int
    passed_cases: int
    failed_cases: int
    pass_rate: Decimal
    failed_reasons: list[dict]
    report_path: str | None
    started_at: datetime
    finished_at: datetime | None
