# Phase 2.7B DEFECT-008 Evidence Report

## 一、Expected

Conversation 874 使用仅含 `opportunity_ref=3956` 的正式 Workspace Selection，并提交自然语言“用这个写一篇，语气自然一点。”。系统应解析 generated Opportunity 3956 的 Account ownership 与 Strategy 13 / Research 2862 lineage，然后进入 CONTENT_CREATE、READY Plan 与 `CONTENT_CREATION_V1`。

## 二、Actual

- AgentTurn：77
- Client Request：`phase27b-e2e003-20260923-01`
- HTTP：500
- Latency：349 ms
- Error：`'ContentOpportunity' object has no attribute 'account_id'`
- Run Ref：无

## 三、Failure Stage

`UnifiedAgentService.handle_turn -> _workspace -> RepositoryContextIdentityReader.get_identity`

错误发生在添加用户消息、真实 LLM、Semantic、Context Resolution、Planner 和 Workflow 之前。

## 四、Root Cause Evidence

`RepositoryContextIdentityReader` 对除 Account 外的对象统一读取 `item.account_id`。`ContentOpportunity` 的正式 schema 没有 `account_id`；其 ownership 需要沿 `report_id` 或 `strategy_artifact_id` 通过 canonical Repository 解析。该 adapter 把统一 IdentityRecord contract 错误实现成了统一 ORM 字段假设。

## 五、Partial Data

- FAILED AgentTurn idempotency record：1
- Conversation user/assistant message：0
- CONTENT_CREATION_V1 Run：0
- Draft Root：0
- Draft Version：0
- Operation Ledger：0
- Prompt evidence / LLM call：0
- Research / Strategy / XHS collection：0

## 六、Reuse Verification

前后计数保持：RESEARCH_V1 Run 954、CONTENT_STRATEGY_V1 Run 159、Research Artifact 2875、Strategy Artifact 13。失败窗口内 crawl task、competitor account/note/comment 新增均为 0。

## 七、Status

修复采用显式 type-specific ownership resolver：

- Generated Opportunity：`strategy_artifact_id -> ContentStrategyArtifact.account_id`
- Historical Opportunity：`report_id -> CompetitorAnalysisReport.account_id`
- 不信任客户端 `account_ref`，不新增冗余字段、Migration、Route 或第二套 Repository。

定向回归：首组 57 passed；Strategy/Research/Draft 扩展组 84 passed。完整回归：backend 588 passed / 3 skipped / 18 warnings；frontend 7/7；`vue-tsc --noEmit` PASS；production build PASS；Alembic current=head=`c7d8e9f0a1b2`；`git diff --check` 无 whitespace error，仅既有 CRLF 提示。

真实 Retry 使用新的 client request `phase27b-e2e003-defect008-retry-20260923-01`。Turn 84 成功越过 Workspace ownership，进入真实 Semantic 并得到 `CONTENT_CREATE`，证明 Opportunity 3956 canonical ownership path 已恢复；旧 Turn 77 原样保留。

`DEFECT-008 = FIXED / VERIFIED`

随后出现不同的 `DEFECT-009`：自然语言“这个”没有被可信 Workspace Opportunity 3956 消解，返回 `REFERENCE_CONTEXT_MISSING`。因此 `E2E-003 = FAILED / BLOCKED BY DEFECT-009`。

按 Stop Point 未继续修复、未执行 E2E-004、Allure 或 Schemathesis。
