import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[2]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.schemas.eval import EvalCaseResult
from evals.runners.core import build_arg_parser, print_report, run_eval

DEFAULT_DATASET = "tool_fallback_cases.jsonl"
EVAL_TYPE = "tool_fallback"


def evaluate_case(case: dict) -> EvalCaseResult:
    """评测工具失败后是否触发 fallback。"""
    steps = case.get("input", {}).get("trajectory", {}).get("steps", [])
    expected = case.get("expected", {})
    fallback_tool_name = expected.get("fallback_tool_name")
    fallback_steps = [step for step in steps if step.get("fallback_used") or step.get("status") == "FALLBACK_USED"]
    fallback_name_ok = True if not fallback_tool_name else any(step.get("fallback_tool_name") == fallback_tool_name for step in fallback_steps)
    actual_pass = bool(fallback_steps) == bool(expected.get("fallback_used", False)) and fallback_name_ok
    expected_pass = expected.get("should_pass", True)
    passed = actual_pass == expected_pass
    return EvalCaseResult(
        case_id=str(case.get("case_id")),
        passed=passed,
        reason=None if passed else f"expected_pass={expected_pass}, actual_pass={actual_pass}",
        actual_output={"fallback_count": len(fallback_steps), "fallback_name_ok": fallback_name_ok, "actual_pass": actual_pass},
    )


def main() -> None:
    """从命令行运行工具降级评测。"""
    parser = build_arg_parser("Run tool fallback eval", DEFAULT_DATASET)
    args = parser.parse_args()
    print_report(run_eval(EVAL_TYPE, args.dataset, evaluate_case, args.report_dir))


if __name__ == "__main__":
    main()
