import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[2]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.schemas.eval import EvalCaseResult
from evals.runners.core import build_arg_parser, print_report, run_eval

DEFAULT_DATASET = "memory_usage_cases.jsonl"
EVAL_TYPE = "memory_usage"


def evaluate_case(case: dict) -> EvalCaseResult:
    """评测策略记忆是否被正确检索和使用。"""
    payload = case.get("input", {})
    expected = case.get("expected", {})
    memories = {item["id"]: item for item in payload.get("memories", [])}
    usage_records = payload.get("usage_records", [])
    used_memories = [memories.get(item.get("memory_id")) for item in usage_records if item.get("memory_id") in memories]
    required_types = set(expected.get("required_memory_types", []))
    allowed_statuses = set(expected.get("allowed_statuses", []))

    count_ok = len(usage_records) >= int(expected.get("min_usage_count", 0))
    type_ok = required_types <= {memory.get("memory_type") for memory in used_memories if memory}
    status_ok = all(memory.get("status") in allowed_statuses for memory in used_memories if memory) if allowed_statuses else True
    actual_pass = count_ok and type_ok and status_ok
    expected_pass = expected.get("should_pass", True)
    passed = actual_pass == expected_pass
    return EvalCaseResult(
        case_id=str(case.get("case_id")),
        passed=passed,
        reason=None if passed else f"expected_pass={expected_pass}, actual_pass={actual_pass}",
        actual_output={
            "usage_count": len(usage_records),
            "used_memory_types": [memory.get("memory_type") for memory in used_memories if memory],
            "count_ok": count_ok,
            "type_ok": type_ok,
            "status_ok": status_ok,
            "actual_pass": actual_pass,
        },
    )


def main() -> None:
    """从命令行运行策略记忆使用评测。"""
    parser = build_arg_parser("Run memory usage eval", DEFAULT_DATASET)
    args = parser.parse_args()
    print_report(run_eval(EVAL_TYPE, args.dataset, evaluate_case, args.report_dir))


if __name__ == "__main__":
    main()
