# Phase 2.7B DEFECT-006 修复与 E2E-002 验证报告

## 一、DEFECT-006 Root Cause

Planner 原先把 `TaskSemanticFrame.missing_info` 与 `ResolvedContext.blocking_missing_info` 无条件合并。Turn 61 虽已解析 canonical Research 2862，Semantic 提出的“选题数量、偏好、更细范围”仍被 Planner 重新升级为 blocker，导致 Workflow Input Builder 执行前返回 `CLARIFY / WAITING_USER`。

## 二、Semantic Missing vs Blocking Missing

- Semantic missing：保留 LLM 对可补充信息的语义建议，继续可观察、可测试。
- Blocking missing：只表示 canonical reference unresolved/ambiguous，或 typed Workflow Input 无法构建。
- 数量、方向偏好、风格和更细范围有合法默认行为时属于 non-blocking preference。

## 三、Requiredness Rule

Requiredness 来自确定性 Workflow Contract 与 Input Builder。`CONTENT_STRATEGY_V1` 启动要求唯一 Research identity、account、可构建的 strategy goal；constraints 可为空，goal 有合法默认值。缺少 Research、Research 多候选或显式非法引用仍然阻塞。

## 四、Minimal Fix

- Resolver 不再把原始 semantic `missing_info` 自动复制为 `blocking_missing_info`，仍保留 unresolved/ambiguous reference blocker。
- Planner 不再重新合并 semantic `missing_info`，让 typed Input Builder 验证真正 required input。
- 未修改 Semantic Layer、Workflow、Runtime、Tool、数据库、Migration 或 Route。

## 五、Regression Tests

- A：Research R100 + 数量/偏好 missing -> READY。
- B：未提供数量 -> 不 CLARIFY。
- C：无 Research -> `research_artifact_ref` missing。
- D：多个 Research 候选 -> ambiguous / CLARIFY。
- E：显式非法 Research -> unresolved / CLARIFY。
- F：canonical Research 已解析时冗余 semantic missing 不阻塞。
- 修复前新增核心用例：3 failed、2 passed。
- 修复后定向回归：66 passed。

## 六、DEFECT-004 Regression

`test_resolved_recent_research_satisfies_redundant_strategy_missing_info` 通过；DEFECT-004 行为未回退。

## 七、E2E-002 Retry

- Conversation：874
- Turn：65
- client_request_id：`phase27b-e2e002-defect006-retry-20260923-01`
- Latency：28634 ms
- Intent：`CONTENT_STRATEGY`
- Action：`EXECUTE_PLAN`
- Workflow：`CONTENT_STRATEGY_V1`
- Run：`wfr_f780fb64e168446786896cf4ccbb5b36`
- Resolved Research：2862
- Run status：`FAILED`
- Failure step：`strategy_generation`
- Error：`VALIDATION_ERROR` / “语义处理失败，输入上下文或结果未通过校验。”

真实 Retry 证明 DEFECT-006 已越过：Planner 已 READY、Run 已创建、正确输入 Research 2862。新的 semantic validation failure 登记为 DEFECT-007 后停止。

## 八、Strategy / Opportunity Result

DEFECT-007 发生在 `strategy_generation`，`strategy_artifact_creation=NOT_STARTED`。Strategy Artifact 0、Derived Opportunity 0、Operation Ledger 0；没有可供 Product Read 的新 Strategy/Opportunity。

## 九、Research Reuse Verification

Run input 与 state 均为 Research 2862，Research Query 内容包含 canonical Opportunity 3923。未创建 RESEARCH Run，未重新采集 URL，未调用 XHS collection。

## 十、Full Regression

- Backend：579 passed，3 skipped，18 warnings。
- Frontend tests：7 passed。
- Typecheck：`npx vue-tsc --noEmit` PASS；仓库没有独立 `typecheck` npm script。
- Production build：PASS（保留现有 chunk-size warning）。
- `git diff --check`：PASS；仅现有 LF/CRLF 提示。
- Alembic current/head：`c7d8e9f0a1b2`。
- Migration = 0；New Route = 0。

## 十一、Phase 2.7B 当前状态

`BLOCKED / NOT ACCEPTED`。DEFECT-005 `FIXED / VERIFIED`；DEFECT-006 `FIXED / VERIFIED`；DEFECT-007 `OPEN`。

## 十二、面试资产沉淀

- 新增 Q&A：为什么 LLM 返回 missing_info 不应直接触发追问。
- 同一 canonical 文件同时沉淀 DEFECT-005 的 deterministic identity boundary Q&A。
- 修改文件：`docs/interview/INTERVIEW_QA.md`。

## 十三、下一步

只对 DEFECT-007 做独立 Root Cause Analysis；不得连续静默修复。E2E-002 尚未整体 PASS，不继续下一 Acceptance Case，不进入 Testing Track。

## 十四、Git

保留既有脏工作区。本轮产品代码仅修改 Resolver 与 Planner，并增加 A–F 回归和文档；没有 Migration、Route 或依赖变更。
