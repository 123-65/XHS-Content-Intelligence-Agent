# Phase 2.7B DEFECT-012 Fix / E2E-004 Verification Report

## Expected

Turn 103 应使用正式 Workspace `draft_ref=2625`，解析到 Draft Root 2625 / V1 2082，并启动 `CONTENT_REFINEMENT_V1` 验证 DEFECT-011 修复。

## Actual

- Account / Conversation：8456 / 874
- Turn：103
- Client Request：`phase27b-e2e004-defect011-retry-20260924-01`
- Semantic：`CONTENT_REFINE`
- Action / Status：`CLARIFY / WAITING_USER`
- Missing：`draft_ref`
- Run：null

## Evidence

`agent_turn.request_payload` 明确保存：

```json
{"workspace_selection":{"draft_ref":2625}}
```

但 `result_payload` 仍要求 `draft_ref`。因此客户端没有漏传，缺陷位于 Workspace → Context Resolution / Planner required input 的正式链路。由于没有 Run，DEFECT-011 的真实 Evidence Retrieval 路径未被执行。

## Frozen RCA

`Classification B = Semantic nondeterminism exposed Context Resolver dependency gap`。Turn 96 的真实 Semantic 包含 `ACTIVE_DRAFT / 这个开头`，Turn 103 在相同文本和 Workspace 下得到 `references=[]`。旧 Resolver 只遍历 Semantic references，因而没有消费已经过 canonical ownership 校验的 Workspace Draft。

## Minimal Fix

- 仅修改 `ContextResolver`，复用既有 `EXPECTED_CONTEXT_TYPE`。
- required type 尚未解析且不存在 unresolved/ambiguous 冲突时，只检查 `explicit → workspace`。
- 唯一同类型 canonical candidate 才投影到 `ResolvedContext`。
- explicit invalid/cross-account 继续阻断；explicit valid 优先；多候选 ambiguous；错误类型不替代 required type。
- 不读取 pending/active/recent/history，不修改 Prompt、Schema、Planner、Input Builder、Workflow、Repository、Runtime、API、数据库或 Migration。

## Regression

- Context Resolver：39 passed。
- 定向回归：127 passed / 1 warning。
- Backend full：611 passed / 3 skipped / 18 warnings。
- Frontend：7/7；typecheck PASS；production build PASS。
- `git diff --check` PASS（仅既有 CRLF 提示）。
- Alembic current/heads：`c7d8e9f0a1b2`；Migration=0；New Route=0。
- 覆盖 Turn 96 `ACTIVE_DRAFT` 与 Turn 103 `references=[]` 对同一 Workspace 均解析 Draft 2625，以及类型隔离、多候选、显式优先、非法显式、跨账号和 DEFECT-009 deictic regression。

## Real E2E-004 Retry

- Turn：110
- Client Request：`phase27b-e2e004-defect012-retry-20260924-01`
- Run：`wfr_d87115e85b3243d19986790c15a53848`
- Latency：约 40,588 ms
- Intent / Planner：`CONTENT_REFINE / EXECUTE_PLAN`
- Workflow：`CONTENT_REFINEMENT_V1 / SUCCESS`
- Draft resolution、Opportunity resolution、Evidence retrieval、Revision、Persistence：全部 SUCCESS。
- 本次真实 Semantic 恰好再次输出 `ACTIVE_DRAFT / 这个开头`；空-reference 分支由确定性 parity regression 覆盖。

## Evidence / Version / Product Read

- Grounding：`content_opportunity:3923`、`research_report:2862`。
- Retrieval：ACCOUNT 2914、NOTE 10998/10999/11000、COMMENT 11721..11742；不含 `content_opportunity:3923`。
- Root：2625。
- V1：2082 / version 1 / parent null / GENERATED；body MD5 仍为 `4004ba8f766c34feffa900b8e38af716`。
- V2：2087 / version 2 / parent 2082 / USER_REVISION；body length 621，MD5 `21634f608c2eadeac9cd31ce6a1ca077`。
- Ledger：仅 1 条 `create_draft_version:singleton` success，operation 186。
- Product Read：status=REVISED，latest=2087/V2；versions 同时返回 V1 2082 与 V2 2087，Exact Parent=2082。
- LLM：Control Semantic attempt 1 / 23,589 ms；Draft Revision attempt 1 / 16,860 ms；qwen/deepseek-v4-flash-0731，非 Mock。

## Partial Data

- 新增 Refinement Run：0
- 新增 Operation Ledger：0
- Revision / Persistence：NOT_STARTED
- Draft Root 2625：仍只有 Version 2082 / V1
- V1 body MD5：`4004ba8f766c34feffa900b8e38af716`
- V2：0
- Research / Strategy / Creation / XHS rerun：0

## Status

`DEFECT-012 = FIXED / VERIFIED / FROZEN`

`DEFECT-011 = FIXED / VERIFIED / FROZEN`

`E2E-004 = PASS`

下一步：`E2E-005 Pending Resume`。本轮未执行 E2E-005、Testing Track、Allure 或 Schemathesis。
