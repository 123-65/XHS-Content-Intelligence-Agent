# Phase 2.7B DEFECT-007 Root Cause Evidence Report

## 一、DEFECT-007 Root Cause

OBS-001 后 Root Cause 已由 turn 69 真实复现确认：模型输出通过 Provider/Pydantic schema，并合法引用 canonical `content_opportunity:3923`；Service 的 authorized evidence set 只包含顶层 `research_report:2862`，没有纳入同一输入 historical opportunities 中的 3923，导致 post-parse business validation 拒绝。

已确定边界：

- Run `wfr_f780fb64e168446786896cf4ccbb5b36` 在 `strategy_generation` 失败。
- `growth_context`、Research 2862 Query 均成功；`strategy_artifact_creation=NOT_STARTED`。
- Provider `_parse()` 的 JSON/Pydantic failure 抛出 `LLMSchemaValidationError`，Semantic Tool 会映射为 `INTERNAL_ERROR`。
- 真实 Run 的 code 是 `VALIDATION_ERROR`，因此异常更可能来自 Provider parse 之后的 `ValueError` 边界，例如 deterministic evidence allowlist；但原输出缺失，不能确认具体 ref。

## 二、真实 LLM Output 与 Expected Schema

Expected Schema 为 `GeneratedContentStrategy`：strategy goal、target audience、至少一个 content direction、rationale、至少一个 evidence ref、constraints 和至少一个 opportunity；Opportunity 必须包含正整数 `source_opportunity_id`、goal、why-now、hook、至少一个 EvidenceRef 和 constraints。

Turn 65 的实际输出未被保存，无法列出原始 actual value/type 或具体 field。

一次受控诊断复用相同 Run 上下文，真实模型首轮返回合法结构：canonical `source_opportunity_id=3923`、Research evidence `research_report:2862`，最终 SUCCESS。该输出只证明失败不是确定性输入/Schema 冲突，不能替代 turn 65 的失败样本，未作为失败 fixture 提交。

## 三、Structured Retry 行为

- 配置：`llm_max_retries=2`。
- Provider 使用 Tenacity 对整个 `generate_structured()` 重试。
- schema failure 会触发重试，但第二次 prompt 与第一次相同，不包含 validation feedback。
- turn 65 每次 attempt category 与 attempt count 未持久化，无法恢复。
- 受控诊断 attempt count=1，首轮成功。
- retry exhausted 后会抛 formal exception，不存在 Mock 或 silent fallback。

## 四、Failure Data Flow

`Research 2862 -> Query Growth Context PASS -> Query Artifact PASS（Opportunity 3923） -> GenerateContentStrategyInput -> LLM structured generation -> 未保留的 ValueError/validation detail -> Semantic Tool VALIDATION_ERROR -> Workflow FAILED`

## 五、Minimal Fix

未实施。缺少原始 failing output 与具体 validation detail，任何 Prompt、adapter 或 service 修改都会是试错式修复。

## 六、Recorded Regression Fixture

未创建失败 fixture。真实失败输出不可恢复；受控诊断得到的是成功样本，不应伪装成 DEFECT-007 fixture。

## 七、Regression Tests

未新增 DEFECT-007 修复测试，因为无法构造与真实失败等价的最小 fixture。此前基线保持：backend 579 passed / 3 skipped；frontend 7 passed；typecheck/build PASS。

## 八、E2E-002 Retry

未再次执行。Root Cause 未确认，禁止继续真实 Retry。

## 九、Strategy Artifact / Opportunity

Turn 65：Strategy Artifact 0、Derived Opportunity 0、Operation Ledger 0。没有 partial data。

## 十、Research Reuse Verification

失败 Run 明确使用 Research 2862 与 canonical Opportunity 3923；没有重跑 Research 或重新采集 XHS URL。

## 十一、Full Regression

本轮未修改产品代码，因此未重复完整回归。沿用进入 DEFECT-007 前已完成的 579 passed / 3 skipped、frontend 7 passed、typecheck/build PASS、Alembic current=head。

## 十二、面试资产沉淀

无新增高价值 Q&A。当前不能确认 DEFECT-007 属于 schema violation、evidence validation 还是其他 ValueError；在根因未证实时不写结论型面试答案。

## 十三、Phase 2.7B 当前状态

`BLOCKED / NOT ACCEPTED`。DEFECT-007 保持 `OPEN / RCA CONFIRMED / NOT FIXED`。

## 十四、下一步

需要先获得一次失败时的最小安全诊断证据：attempt number、validation layer、Pydantic/ValueError details，以及脱敏后的 structured output。完成证据采集后才能建立 recorded fixture 和最小修复。

## 十五、Git

没有新增 Migration、Route、依赖或产品代码修改。临时诊断脚本已移除；仅新增本报告并更新阶段状态。

## 十六、最终只读验收（Turn 76）

本节为最终状态续记；以上 Turn 65 / Turn 69、OBS-001 与 Root Cause 历史证据原样保留。

- Run `wfr_2193edf65ec14dcfba2f224df3642406`：`CONTENT_STRATEGY_V1 / SUCCESS`，Account 8456，`error_snapshot=null`，Research 输入与 resolved state 均为 2862。
- Strategy 13：Account 8456，`research_artifact_id=2862`，内容、方向、rationale、constraints 与 EvidenceRefs 已持久化。
- Opportunity 3956：`strategy_artifact_id=13`、`report_id=2862`、`source_opportunity_id=3923`；EvidenceRefs 仅为 Research 2862 与 Opportunity 3923。
- Authorized scope：正式输入中的 `research_report:2862` 与 `content_opportunity:3923` 均通过。修复仅从当前 `historical_opportunities` 提取 canonical 正整数 ID；既有回归接受当前输入 200，并拒绝未授权 300、400、999，未扩权为任意数据库 ID。
- OBS-001：Control 与 Strategy 各一条 SUCCESS evidence；两次调用各首轮成功，实际 attempt count 均为 1。`attempt_total=2` 表示最大尝试配置而非已执行两次。记录为 `is_mock=false`，raw prompt/output 为空，字符串内容 hash 脱敏，无 Secret 泄露。
- Research reuse：`08:49:19`—`08:50:55` 窗口内 RESEARCH_V1 Run、Research Artifact、crawl task、refresh run、competitor account/note/comment 新增均为 0；Research 2862 创建于 `03:28:27`。
- Operation Ledger：唯一记录 `create_content_strategy_artifact:singleton` 成功，结果指向 Strategy 13 与 Opportunity 3956；两项业务对象各一份。
- Product Read：正式 GET 返回 Strategy 13、Research 2862 与 Opportunity 3956，contract 不含 raw response、secret 或 trace；Strategy Account Boundary 已由 Phase 2.7A 既有 PASS 回归覆盖。

最终判定：`DEFECT-007 = FIXED / VERIFIED`；`E2E-002 = PASS`。未发现 DEFECT-008，未执行 E2E-003。
