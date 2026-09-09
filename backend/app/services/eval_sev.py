from decimal import Decimal

from sqlalchemy.orm import Session

from app.repositories.eval_repo import EvalRepository
from app.schemas.eval import EvalCaseCreate, EvalReport, EvalRunCreate


class EvalService:
    """Service for persisting evaluation cases and run summaries."""

    def __init__(self, db: Session):
        """Initialize the evaluation service."""
        self.repo = EvalRepository(db)

    def record_dataset_cases(self, suite_name: str, eval_type: str, cases: list[dict]) -> None:
        """Persist JSONL cases so they can be audited later."""
        for index, case in enumerate(cases, start=1):
            case_key = str(case.get("case_id") or f"{suite_name}-{index}")
            self.repo.upsert_case(
                EvalCaseCreate(
                    suite_name=suite_name,
                    case_key=case_key,
                    eval_type=eval_type,
                    input_payload=case.get("input", {}),
                    expected_output=case.get("expected", {}),
                    case_metadata=case.get("metadata", {}),
                    is_active=case.get("is_active", True),
                )
            )

    def record_run(self, report: EvalReport) -> EvalReport:
        """Persist an EvalRun and return the report with eval_run_id."""
        run = self.repo.create_run(
            EvalRunCreate(
                eval_type=report.eval_type,
                dataset_path=report.dataset_path,
                status="SUCCESS" if report.failed_cases == 0 else "FAILED",
                total_cases=report.total_cases,
                passed_cases=report.passed_cases,
                failed_cases=report.failed_cases,
                pass_rate=Decimal(str(report.pass_rate)),
                failed_reasons=report.failed_reasons,
                report_path=report.report_path,
            )
        )
        return report.model_copy(update={"eval_run_id": run.id})
