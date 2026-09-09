import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[2]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.agent.policies.guardrail import GuardrailPolicy
from app.schemas.eval import EvalCaseResult
from evals.runners.core import build_arg_parser, print_report, run_eval

DEFAULT_DATASET = "guardrail_cases.jsonl"
EVAL_TYPE = "guardrail"


def evaluate_case(case: dict) -> EvalCaseResult:
    """评测高风险动作是否被安全护栏拦截。"""
    payload = case.get("input", {})
    expected = case.get("expected", {})
    decision = GuardrailPolicy().inspect(payload.get("tool_name", ""), payload.get("payload", {}))
    blocked = not decision.allowed
    expected_codes = set(expected.get("codes", []))
    code_ok = expected_codes <= set(decision.codes)
    actual_pass = blocked == expected.get("blocked", False) and code_ok
    return EvalCaseResult(
        case_id=str(case.get("case_id")),
        passed=actual_pass,
        reason=None if actual_pass else f"expected_blocked={expected.get('blocked')}, actual_blocked={blocked}, codes={decision.codes}",
        actual_output={"blocked": blocked, "codes": decision.codes, "reason": decision.reason},
    )


def main() -> None:
    """从命令行运行安全护栏评测。"""
    parser = build_arg_parser("Run guardrail eval", DEFAULT_DATASET)
    args = parser.parse_args()
    print_report(run_eval(EVAL_TYPE, args.dataset, evaluate_case, args.report_dir))


if __name__ == "__main__":
    main()
