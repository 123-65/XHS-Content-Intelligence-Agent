import argparse
import json
import sys
from collections.abc import Callable
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[2]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.core.database import SessionLocal
from app.schemas.eval import EvalCaseResult, EvalReport
from app.services.eval_sev import EvalService

EVAL_ROOT = Path(__file__).resolve().parents[1]
DATASETS_DIR = EVAL_ROOT / "datasets"
REPORTS_DIR = EVAL_ROOT / "reports"

Evaluator = Callable[[dict], EvalCaseResult]


def load_jsonl(path: Path) -> list[dict]:
    """Load evaluation cases from a JSONL file."""
    cases = []
    with path.open("r", encoding="utf-8") as file:
        for line_number, line in enumerate(file, start=1):
            stripped = line.strip()
            if stripped:
                try:
                    cases.append(json.loads(stripped))
                except json.JSONDecodeError as exc:
                    raise ValueError(f"Invalid JSONL at {path}:{line_number}: {exc}") from exc
    return cases


def resolve_dataset_path(dataset_name: str | Path) -> Path:
    """Resolve a dataset file name or path."""
    path = Path(dataset_name)
    return path if path.is_absolute() else DATASETS_DIR / path


def run_eval(eval_type: str, dataset_name: str, evaluator: Evaluator, report_dir: str | Path | None = None) -> EvalReport:
    """Run one eval dataset and persist the EvalRun record."""
    dataset_path = resolve_dataset_path(dataset_name)
    dataset_label = str(_display_path(dataset_path))
    cases = load_jsonl(dataset_path)
    results = [evaluator(case) for case in cases]
    failed_reasons = [
        {"case_id": result.case_id, "reason": result.reason, "actual_output": result.actual_output}
        for result in results
        if not result.passed
    ]
    total_cases = len(results)
    passed_cases = len([result for result in results if result.passed])
    failed_cases = total_cases - passed_cases
    pass_rate = Decimal("0") if total_cases == 0 else Decimal(passed_cases) / Decimal(total_cases)
    report = EvalReport(
        eval_type=eval_type,
        dataset_path=dataset_label,
        total_cases=total_cases,
        passed_cases=passed_cases,
        failed_cases=failed_cases,
        pass_rate=pass_rate.quantize(Decimal("0.0001")),
        failed_reasons=failed_reasons,
        case_results=results,
    )
    report = report.model_copy(update={"report_path": str(write_report(report, report_dir))})

    with SessionLocal() as db:
        service = EvalService(db)
        service.record_dataset_cases(dataset_path.stem, eval_type, cases)
        report = service.record_run(report)
        rewrite_report(report)
    return report


def write_report(report: EvalReport, report_dir: str | Path | None = None) -> Path:
    """Write an evaluation report JSON file."""
    output_dir = Path(report_dir) if report_dir else REPORTS_DIR
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(UTC).strftime("%Y%m%d%H%M%S%f")
    report_path = output_dir / f"{report.eval_type}_{timestamp}.json"
    report_path.write_text(json.dumps(report.model_dump(mode="json"), ensure_ascii=False, indent=2), encoding="utf-8")
    return _display_path(report_path)


def rewrite_report(report: EvalReport) -> None:
    """Rewrite a report after EvalRun persistence adds eval_run_id."""
    if report.report_path:
        Path(report.report_path).write_text(json.dumps(report.model_dump(mode="json"), ensure_ascii=False, indent=2), encoding="utf-8")


def _display_path(path: Path) -> Path:
    """Return a stable relative path for files inside backend."""
    resolved = path.resolve()
    try:
        return resolved.relative_to(BACKEND_ROOT)
    except ValueError:
        return resolved


def build_arg_parser(description: str, default_dataset: str) -> argparse.ArgumentParser:
    """Build a common CLI parser for standalone runners."""
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument("--dataset", default=default_dataset, help="JSONL dataset file name or path")
    parser.add_argument("--report-dir", default=None, help="Directory for JSON reports")
    return parser


def print_report(report: EvalReport) -> None:
    """Print a compact report summary to stdout."""
    print(json.dumps(report.model_dump(mode="json"), ensure_ascii=False, indent=2))
