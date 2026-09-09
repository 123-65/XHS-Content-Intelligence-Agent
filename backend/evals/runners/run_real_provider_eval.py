import json
import sys
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[2]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.core.database import SessionLocal
from app.schemas.eval import EvalCaseResult, EvalReport
from app.services.eval_sev import EvalService
from evals.runners.assertions import classify_comment, find_risk_phrases
from evals.runners.core import DATASETS_DIR, REPORTS_DIR, load_jsonl

DATASETS = (
    ("real_note_breakdown", "real_note_breakdown_cases.jsonl"),
    ("real_comment_classification", "real_comment_classification_cases.jsonl"),
    ("real_draft_generation", "real_draft_generation_cases.jsonl"),
    ("real_provider_health", "real_provider_health_cases.jsonl"),
)


def evaluate_case(case: dict) -> EvalCaseResult:
    """评测真实样例 Provider 数据、评论、草稿和健康状态。"""
    evaluator = {
        "real_note_breakdown": _eval_note_breakdown,
        "real_comment_classification": _eval_comment,
        "real_draft_generation": _eval_draft,
        "real_provider_health": _eval_health,
    }[_case_type(case)]
    return evaluator(case)


def run_real_provider_eval(report_dir: str | Path | None = None) -> EvalReport:
    """运行真实样例 Provider 评测并生成汇总报告。"""
    cases = []
    for eval_type, dataset_name in DATASETS:
        cases.extend({**case, "_eval_type": eval_type, "_dataset_name": dataset_name} for case in load_jsonl(DATASETS_DIR / dataset_name))
    results = [evaluate_case(case) for case in cases]
    total_cases = len(results)
    passed_cases = len([item for item in results if item.passed])
    failed_cases = total_cases - passed_cases
    real_cases = len([case for case in cases if not case.get("input", {}).get("is_mock", False)])
    mock_cases = total_cases - real_cases
    report = EvalReport(
        eval_type="real_provider",
        dataset_path="evals/datasets/real_*_cases.jsonl",
        total_cases=total_cases,
        passed_cases=passed_cases,
        failed_cases=failed_cases,
        pass_rate=(Decimal(passed_cases) / Decimal(total_cases)).quantize(Decimal("0.0001")) if total_cases else Decimal("0"),
        failed_reasons=[{"case_id": item.case_id, "reason": item.reason, "actual_output": item.actual_output} for item in results if not item.passed],
        case_results=results,
    )
    report_path = _write_real_report(report, real_cases, mock_cases, report_dir)
    report = report.model_copy(update={"report_path": str(report_path)})
    with SessionLocal() as db:
        service = EvalService(db)
        for _, dataset_name in DATASETS:
            dataset_cases = load_jsonl(DATASETS_DIR / dataset_name)
            service.record_dataset_cases(Path(dataset_name).stem, "real_provider", dataset_cases)
        report = service.record_run(report)
        _write_real_report(report, real_cases, mock_cases, report_dir, report_path)
    return report


def _case_type(case: dict) -> str:
    """读取样例类型。"""
    return case.get("_eval_type") or str(case.get("case_id", "")).rsplit("-", 2)[0].replace("-", "_")


def _eval_note_breakdown(case: dict) -> EvalCaseResult:
    """评测真实公开笔记快照结构。"""
    payload = case.get("input", {})
    expected = case.get("expected_behavior", {})
    note = payload.get("note_snapshot", {})
    missing = [field for field in expected.get("required_fields", []) if not note.get(field)]
    real_ok = bool(payload.get("is_mock")) is not bool(expected.get("must_be_real", False))
    passed = not missing and real_ok
    return EvalCaseResult(case_id=str(case.get("case_id")), passed=passed, reason=None if passed else f"missing={missing}, real_ok={real_ok}", actual_output={"missing": missing, "is_mock": payload.get("is_mock"), "provider_name": note.get("provider_name")})


def _eval_comment(case: dict) -> EvalCaseResult:
    """评测真实评论分类行为。"""
    payload = case.get("input", {})
    expected = case.get("expected_behavior", {})
    demand_type = classify_comment(payload.get("comment", ""))
    passed = demand_type == expected.get("demand_type")
    return EvalCaseResult(case_id=str(case.get("case_id")), passed=passed, reason=None if passed else f"expected={expected.get('demand_type')}, actual={demand_type}", actual_output={"demand_type": demand_type, "is_mock": payload.get("is_mock")})


def _eval_draft(case: dict) -> EvalCaseResult:
    """评测真实样例草稿是否包含禁止表达。"""
    payload = case.get("input", {})
    expected = case.get("expected_behavior", {})
    violations = find_risk_phrases(payload.get("draft", {}))
    should_pass = expected.get("should_pass", True)
    actual_pass = not violations
    passed = actual_pass == should_pass
    return EvalCaseResult(case_id=str(case.get("case_id")), passed=passed, reason=None if passed else f"expected_pass={should_pass}, violations={violations}", actual_output={"should_pass": actual_pass, "violations": violations, "is_mock": payload.get("is_mock")})


def _eval_health(case: dict) -> EvalCaseResult:
    """评测 ProviderHealthCheck 结构。"""
    payload = case.get("input", {})
    expected = case.get("expected_behavior", {})
    health = payload.get("health", {})
    available = all(section.get("available") for section in health.values())
    has_mock = any(section.get("is_mock") for section in health.values())
    passed = available == expected.get("available", True) and (expected.get("allow_mock", True) or not has_mock)
    return EvalCaseResult(case_id=str(case.get("case_id")), passed=passed, reason=None if passed else f"available={available}, has_mock={has_mock}", actual_output={"available": available, "has_mock": has_mock})


def _write_real_report(report: EvalReport, real_cases: int, mock_cases: int, report_dir: str | Path | None = None, report_path: Path | None = None) -> Path:
    """写入带 real/mock 统计的真实 Provider 报告。"""
    output_dir = Path(report_dir) if report_dir else REPORTS_DIR
    output_dir.mkdir(parents=True, exist_ok=True)
    path = report_path or output_dir / f"real_provider_{datetime.now(UTC).strftime('%Y%m%d%H%M%S%f')}.json"
    payload = report.model_dump(mode="json") | {"real_cases": real_cases, "mock_cases": mock_cases}
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def main() -> None:
    """从命令行运行真实 Provider 灰度评测。"""
    print(json.dumps(run_real_provider_eval().model_dump(mode="json"), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
