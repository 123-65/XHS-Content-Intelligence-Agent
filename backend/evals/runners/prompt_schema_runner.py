import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[2]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from pydantic import ValidationError

from app.schemas.content_draft_v2 import DraftGenerateV2Result
from app.schemas.eval import EvalCaseResult
from evals.fakes import FakeEvalLLMClient
from evals.runners.assertions import validate_min_json_schema
from evals.runners.core import build_arg_parser, print_report, run_eval

DEFAULT_DATASET = "prompt_schema_cases.jsonl"
EVAL_TYPE = "prompt_schema"
SCHEMA_MODELS = {"DraftGenerateV2Result": DraftGenerateV2Result}


def evaluate_case(case: dict) -> EvalCaseResult:
    """Evaluate one prompt output schema case."""
    input_payload = case.get("input", {})
    schema_name = input_payload.get("schema_model", "DraftGenerateV2Result")
    schema_model = SCHEMA_MODELS[schema_name]
    output = _resolve_output(input_payload, schema_model)
    should_pass = bool(case.get("expected", {}).get("should_pass", True))

    schema_errors = validate_min_json_schema(output, schema_model.model_json_schema())
    pydantic_errors = _pydantic_errors(output, schema_model)
    errors = [*schema_errors, *pydantic_errors]
    actual_pass = not errors
    passed = actual_pass == should_pass
    return EvalCaseResult(
        case_id=str(case.get("case_id")),
        passed=passed,
        reason=None if passed else "; ".join(errors) or f"expected_should_pass={should_pass}",
        actual_output={"should_pass": actual_pass, "error_count": len(errors)},
    )


def _resolve_output(input_payload: dict, schema_model):
    """Resolve case output from static payload or the eval-only fake client."""
    if input_payload.get("use_mock_llm"):
        return FakeEvalLLMClient().generate_structured("schema eval", schema_model).data.model_dump()
    return input_payload.get("output", {})


def _pydantic_errors(output: dict, schema_model) -> list[str]:
    """Validate output with the Pydantic model too."""
    try:
        schema_model.model_validate(output)
        return []
    except ValidationError as exc:
        return [error["msg"] for error in exc.errors()]


def main() -> None:
    """Run the prompt schema eval from CLI."""
    parser = build_arg_parser("Run prompt schema eval", DEFAULT_DATASET)
    args = parser.parse_args()
    print_report(run_eval(EVAL_TYPE, args.dataset, evaluate_case, args.report_dir))


if __name__ == "__main__":
    main()
