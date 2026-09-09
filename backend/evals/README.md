# XHS Growth Intelligence Agent Evals

This directory contains a lightweight eval system for the backend MVP. It does
not depend on real Xiaohongshu data or a real LLM key. Prompt schema cases can
use `MockLLMClient`.

## Directory

- `datasets/`: JSONL eval cases.
- `runners/`: standalone Python runners.
- `reports/`: generated JSON reports.

## Eval Types

- `comment_classification`: checks deterministic comment-demand classification.
- `experiment_generation`: checks required fields, variables, metrics, and status of experiment cards.
- `draft_safety`: checks prohibited draft-risk phrases.
- `prompt_schema`: validates prompt/model outputs against the draft JSON Schema and Pydantic model.
- `mcp_safety`: checks MCP boundary rules such as no auto-like, auto-comment, auto-follow, auto-DM, captcha bypass, account pools, or proxy pools.
- `agent_trajectory`: checks Agent tool order, forbidden tool calls, and human confirmation gates.
- `tool_fallback`: checks whether failed tool paths use the expected fallback tool.
- `guardrail`: checks whether high-risk actions are blocked by `GuardrailPolicy`.
- `memory_usage`: checks whether selected strategy memories are retrieved and used.

## JSONL Case Format

Each line is one JSON object:

```json
{
  "case_id": "stable-case-id",
  "input": {},
  "expected": {},
  "metadata": {
    "source": "seed",
    "risk": "low"
  }
}
```

Keep `case_id` stable. The runner upserts each case into `eval_case` by
`suite_name + case_id`, then creates a new `eval_run` record for every run.

## Add A Case

1. Choose the dataset file under `datasets/`.
2. Add one JSON object as a new line.
3. Put raw input under `input`.
4. Put assertions under `expected`.
5. Use `metadata.risk = "negative"` for intentional refusal or failure-boundary cases.

Example draft safety case:

```json
{"case_id":"draft-risk-001","input":{"draft":{"body_text":"unsafe text"}},"expected":{"should_pass":false},"metadata":{"source":"seed","risk":"negative"}}
```

## Run Evals

From `backend/`:

```bash
$env:DEBUG='true'
..\.venv\Scripts\python.exe -m alembic upgrade head
..\.venv\Scripts\python.exe -m evals.runners.comment_classification_runner
..\.venv\Scripts\python.exe -m evals.runners.experiment_generation_runner
..\.venv\Scripts\python.exe -m evals.runners.draft_safety_runner
..\.venv\Scripts\python.exe -m evals.runners.prompt_schema_runner
..\.venv\Scripts\python.exe -m evals.runners.mcp_safety_runner
..\.venv\Scripts\python.exe -m evals.runners.agent_trajectory_runner
..\.venv\Scripts\python.exe -m evals.runners.tool_fallback_runner
..\.venv\Scripts\python.exe -m evals.runners.guardrail_runner
..\.venv\Scripts\python.exe -m evals.runners.memory_usage_runner
```

Run all baseline suites:

```bash
$env:DEBUG='true'
..\.venv\Scripts\python.exe -m evals.runners.run_all
```

Use a custom dataset:

```bash
..\.venv\Scripts\python.exe -m evals.runners.draft_safety_runner --dataset my_cases.jsonl
```

## Report Shape

Each run writes a JSON report with:

- `total_cases`
- `passed_cases`
- `failed_cases`
- `pass_rate`
- `failed_reasons`
- `case_results`
- `eval_run_id`

Example:

```json
{
  "eval_type": "draft_safety",
  "total_cases": 3,
  "passed_cases": 3,
  "failed_cases": 0,
  "pass_rate": "1.0000",
  "failed_reasons": []
}
```
