import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[2]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.schemas.eval import EvalCaseResult
from evals.runners.assertions import find_risk_phrases
from evals.runners.core import build_arg_parser, print_report, run_eval

DEFAULT_DATASET = "draft_safety_cases.jsonl"
EVAL_TYPE = "draft_safety"


def evaluate_case(case: dict) -> EvalCaseResult:
    """Evaluate one draft safety case."""
    draft = case.get("input", {}).get("draft", {})
    should_pass = bool(case.get("expected", {}).get("should_pass", True))
    violations = find_risk_phrases(draft)
    actual_pass = not violations
    passed = actual_pass == should_pass
    return EvalCaseResult(
        case_id=str(case.get("case_id")),
        passed=passed,
        reason=None if passed else f"violations={violations}, expected_should_pass={should_pass}",
        actual_output={"should_pass": actual_pass, "violations": violations},
    )


def main() -> None:
    """Run the draft safety eval from CLI."""
    parser = build_arg_parser("Run draft safety eval", DEFAULT_DATASET)
    args = parser.parse_args()
    print_report(run_eval(EVAL_TYPE, args.dataset, evaluate_case, args.report_dir))


if __name__ == "__main__":
    main()
