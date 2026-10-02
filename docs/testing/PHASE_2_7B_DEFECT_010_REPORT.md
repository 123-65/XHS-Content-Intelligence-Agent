# Phase 2.7B DEFECT-010 Fix / Verification Report

## 一、历史失败

- Conversation / Turn：874 / 91
- Run：`wfr_02c20c262f3c40a68e1fc94705b1741b`
- Error：`VALIDATION_ERROR / Opportunity Evidence 类型不可检索: content_opportunity`
- `evidence_retrieval=FAILED`；Draft generation/persistence/review 均 NOT_STARTED；Draft、Version、Ledger 为 0。

## 二、Frozen RCA

`RCA = ACCEPTED / FROZEN / Classification B`。

- Business Context：Strategy 13、Generated Opportunity 3956。
- Lineage / Grounding：Research 2862、Source Opportunity 3923。
- Retrievable Evidence：NOTE、COMMENT、ACCOUNT。

`content_opportunity:3923` 是合法的 lineage/grounding reference，不是 `retrieve_research_evidence` 的可检索事实证据。第一次合同不一致位于 `CONTENT_CREATION_V1` Evidence input assembly：旧实现把宽 Strategy EvidenceRef 合同整体当成窄 retrieval 合同。

## 三、Minimal Fix

- `ContentOpportunityArtifactView` 增加现有 Research Artifact 的 typed `retrievable_evidence_refs` projection。
- projection 复用 `CompetitorAnalysisReport.competitor_account_ids / competitor_note_ids` 与 `CompetitorReportRepository.list_comments_for_notes()`，没有新增 Repository、数据模型、字段、Route 或 Migration。
- Workflow 显式 partition：`research_report`、`content_opportunity` 保留为 grounding refs；只有 Research projection 中的 ACCOUNT、NOTE、COMMENT 进入 retrieval。
- Opportunity 声明的 competitor note 必须属于当前 Research projection；跨 Research 拒绝。真正未知类型 fail fast，不 silent skip。
- 空 factual projection 按既有 `GenerateDraftInput` 非空 EvidenceBundle 合同正式失败。

## 四、Regression

- 定向：122 passed。
- Backend full：600 passed / 3 skipped / 18 warnings。
- Frontend：7/7；`vue-tsc --noEmit` PASS；production build PASS。
- `git diff --check` PASS。
- Alembic current / heads：`c7d8e9f0a1b2`。
- Migration = 0；New Route = 0。

覆盖混合 refs、Generated/Source Opportunity identity、NOTE/COMMENT/ACCOUNT retrieval、unknown ref、DEFECT-007 grounding、cross Research、cross Account、empty evidence、DEFECT-008 ownership 与 DEFECT-009 deictic resolution。

## 五、真实 E2E-003 Retry

- Client Request：`phase27b-e2e003-defect010-retry-20260923-01`
- Conversation / Turn：874 / 95
- Run：`wfr_466d50889d364b74a098013a0256a4a0`
- Latency：71,908 ms
- Semantic / Planner：`CONTENT_CREATE / EXECUTE_PLAN`
- Workflow：`CONTENT_CREATION_V1 / SUCCESS`
- Constraint：语气自然一点
- Business Context：Strategy 13、Generated Opportunity 3956
- Lineage / Grounding：Research 2862、`content_opportunity:3923`
- Retrieval：`ACCOUNT:2914`、`NOTE:10998`、`NOTE:10999`、`NOTE:11000`
- `content_opportunity:3923` 未进入 retrieval tool。

## 六、Draft / Review

- Draft Root：2625
- Draft Version：2082 / V1
- Account：8456
- Strategy lineage：13
- Selected Opportunity lineage：3956
- Version parent：null
- Created from：GENERATED
- Title length：22；Body length：626
- Product Read：PASS
- Operation Ledger：167 / success
- Review：PASS

## 七、LLM Attempts / Reuse

- Control Semantic：attempt 1 / 15,917 ms
- Draft Generation：attempt 1 / 14,279 ms
- Draft Review：attempt 1 / 41,365 ms
- Provider / Model：qwen / deepseek-v4-flash-0731；`is_mock=false`
- Research Artifact count=1、Strategy Artifact count=1、crawl task count=0；没有重新 Research、Strategy 或采集 XHS。

## 八、Final Status

`DEFECT-010 = FIXED / VERIFIED / FROZEN`

`E2E-003 = PASS`

未执行 E2E-004、Testing Track、Allure 或 Schemathesis。
