import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[2]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.schemas.eval import EvalCaseResult
from evals.runners.assertions import is_mcp_action_allowed
from evals.runners.core import build_arg_parser, print_report, run_eval

DEFAULT_DATASET = "mcp_safety_cases.jsonl"
EVAL_TYPE = "mcp_safety"


def evaluate_case(case: dict) -> EvalCaseResult:
    """Evaluate one MCP safety-boundary case."""
    payload = case.get("input", {})
    allowed, reason = is_mcp_action_allowed(
        tool_name=payload.get("tool_name", ""),
        action=payload.get("action", ""),
        payload=payload.get("payload", {}),
    )
    should_refuse = bool(case.get("expected", {}).get("should_refuse", False))
    actual_refused = not allowed
    passed = actual_refused == should_refuse
    return EvalCaseResult(
        case_id=str(case.get("case_id")),
        passed=passed,
        reason=None if passed else f"expected_refuse={should_refuse}, actual_refused={actual_refused}",
        actual_output={"allowed": allowed, "refused": actual_refused, "reason": reason},
    )


def main() -> None:
    """Run the MCP safety eval from CLI."""
    parser = build_arg_parser("Run MCP safety eval", DEFAULT_DATASET)
    args = parser.parse_args()
    print_report(run_eval(EVAL_TYPE, args.dataset, evaluate_case, args.report_dir))


if __name__ == "__main__":
    main()
