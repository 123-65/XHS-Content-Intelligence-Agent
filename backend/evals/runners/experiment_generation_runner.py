import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[2]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.schemas.eval import EvalCaseResult
from evals.runners.core import build_arg_parser, print_report, run_eval

DEFAULT_DATASET = "experiment_generation_cases.jsonl"
EVAL_TYPE = "experiment_generation"


def evaluate_case(case: dict) -> EvalCaseResult:
    """Evaluate one experiment-card structure case."""
    experiment = case.get("input", {}).get("experiment", {})
    expected = case.get("expected", {})
    failures = [
        f"missing field: {field}"
        for field in expected.get("required_fields", [])
        if not experiment.get(field)
    ]

    allowed_statuses = set(expected.get("allowed_statuses", []))
    if allowed_statuses and experiment.get("status") not in allowed_statuses:
        failures.append(f"status {experiment.get('status')} not allowed")

    min_variables = int(expected.get("min_variables", 0))
    variables = experiment.get("variables", [])
    if len(variables) < min_variables:
        failures.append(f"variables count {len(variables)} < {min_variables}")

    min_metric_targets = int(expected.get("min_metric_targets", 0))
    metric_targets = experiment.get("metric_targets", [])
    if len(metric_targets) < min_metric_targets:
        failures.append(f"metric target count {len(metric_targets)} < {min_metric_targets}")

    required_variable_names = set(expected.get("required_variable_names", []))
    actual_variable_names = {item.get("variable_name") for item in variables}
    missing_variable_names = sorted(required_variable_names - actual_variable_names)
    failures.extend(f"missing variable: {name}" for name in missing_variable_names)

    primary_metric = experiment.get("primary_metric")
    if primary_metric and primary_metric not in {item.get("metric_name") for item in metric_targets}:
        failures.append("primary metric is not represented in metric_targets")

    actual_pass = not failures
    expected_pass = bool(expected.get("should_pass", True))
    passed = actual_pass == expected_pass
    return EvalCaseResult(
        case_id=str(case.get("case_id")),
        passed=passed,
        reason=None if passed else "; ".join(failures) or f"expected_should_pass={expected_pass}",
        actual_output={
            "should_pass": actual_pass,
            "field_count": len([key for key, value in experiment.items() if value]),
            "variable_count": len(variables),
            "metric_target_count": len(metric_targets),
            "status": experiment.get("status"),
        },
    )


def main() -> None:
    """Run the experiment generation eval from CLI."""
    parser = build_arg_parser("Run experiment generation eval", DEFAULT_DATASET)
    args = parser.parse_args()
    print_report(run_eval(EVAL_TYPE, args.dataset, evaluate_case, args.report_dir))


if __name__ == "__main__":
    main()
