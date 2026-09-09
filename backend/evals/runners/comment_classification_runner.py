import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[2]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.schemas.eval import EvalCaseResult
from evals.runners.assertions import classify_comment
from evals.runners.core import build_arg_parser, print_report, run_eval

DEFAULT_DATASET = "comment_classification_cases.jsonl"
EVAL_TYPE = "comment_classification"


def evaluate_case(case: dict) -> EvalCaseResult:
    """Evaluate one comment classification case."""
    comment = case.get("input", {}).get("comment", "")
    expected = case.get("expected", {}).get("demand_type", "UNKNOWN")
    actual = classify_comment(comment)
    passed = actual == expected
    return EvalCaseResult(
        case_id=str(case.get("case_id")),
        passed=passed,
        reason=None if passed else f"expected {expected}, got {actual}",
        actual_output={"demand_type": actual},
    )


def main() -> None:
    """Run the comment classification eval from CLI."""
    parser = build_arg_parser("Run comment classification eval", DEFAULT_DATASET)
    args = parser.parse_args()
    print_report(run_eval(EVAL_TYPE, args.dataset, evaluate_case, args.report_dir))


if __name__ == "__main__":
    main()
