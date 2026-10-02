# 小红书增长智能体评估

该目录包含后端 MVP 的轻量级评估系统。它不依赖真实小红书数据，也不依赖真实 LLM key。Prompt schema 用例可以使用 `MockLLMClient`。

## 目录结构

- `datasets/`：JSONL 评估用例。
- `runners/`：独立 Python 运行器。
- `reports/`：生成的 JSON 报告。

## 评估类型

- `comment_classification`：检查确定性的评论需求分类。
- `experiment_generation`：检查实验卡片的必填字段、变量、指标和状态。
- `draft_safety`：检查被禁止的草稿风险短语。
- `prompt_schema`：根据草稿 JSON Schema 和 Pydantic 模型验证提示词/模型输出。
- `mcp_safety`：检查 MCP 边界规则，例如禁止自动点赞、自动评论、自动关注、自动私信、验证码绕过、账号池或代理池。
- `agent_trajectory`：检查 Agent 工具顺序、禁止的工具调用和人工确认门禁。
- `memory_usage`：检查选定的策略记忆是否被检索并使用。

## JSONL 用例格式

每一行是一个 JSON 对象：

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

保持 `case_id` 稳定。运行器会通过 `suite_name + case_id` 将每个用例 upsert 到 `eval_case`，然后为每次运行创建一条新的 `eval_run` 记录。

## 添加用例

1. 在 `datasets/` 下选择数据集文件。
2. 添加一个 JSON 对象作为新的一行。
3. 将原始输入放在 `input` 下。
4. 将断言放在 `expected` 下。
5. 对于有意拒绝或失败边界用例，使用 `metadata.risk = "negative"`。

示例草稿安全用例：

```json
{"case_id":"draft-risk-001","input":{"draft":{"body_text":"unsafe text"}},"expected":{"should_pass":false},"metadata":{"source":"seed","risk":"negative"}}
```

## 运行评估

从 `backend/` 下运行：

```bash
$env:DEBUG='true'
..\.venv\Scripts\python.exe -m alembic upgrade head
..\.venv\Scripts\python.exe -m evals.runners.comment_classification_runner
..\.venv\Scripts\python.exe -m evals.runners.experiment_generation_runner
..\.venv\Scripts\python.exe -m evals.runners.draft_safety_runner
..\.venv\Scripts\python.exe -m evals.runners.mcp_safety_runner
..\.venv\Scripts\python.exe -m evals.runners.agent_trajectory_runner
..\.venv\Scripts\python.exe -m evals.runners.memory_usage_runner
```

运行所有基线套件：

```bash
$env:DEBUG='true'
..\.venv\Scripts\python.exe -m evals.runners.run_all
```

使用自定义数据集：

```bash
..\.venv\Scripts\python.exe -m evals.runners.draft_safety_runner --dataset my_cases.jsonl
```

## 报告结构

每次运行都会写入一个 JSON 报告，包含：

- `total_cases`
- `passed_cases`
- `failed_cases`
- `pass_rate`
- `failed_reasons`
- `case_results`
- `eval_run_id`

示例：

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
