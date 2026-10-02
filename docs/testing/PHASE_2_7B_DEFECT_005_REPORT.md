# Phase 2.7B DEFECT-005 修复与 E2E-002 验证报告

## 一、DEFECT-005 Root Cause

- failing field：`ContentStrategyResult.opportunities[].source_opportunity_id`。
- expected：Research 2862 下 canonical `ContentOpportunity.id=3923`（正整数 DB identity）。
- actual：Strategy LLM 输出并进入 Workflow State 的整数 `1`。
- 数据来源：`QueryArtifactTool` 的 Research 投影只返回报告摘要，遗漏 Research Opportunity；`CONTENT_STRATEGY_V1` 因而向 `generate_content_strategy` 传入空 `historical_opportunities`，LLM 在缺少 canonical identity 时生成 `1`。
- 首次非法层：Semantic Tool 输出。其输入没有可选择的 canonical opportunity ref，输出虽通过 Pydantic `gt=0` 类型校验，却不满足持久化 lineage。
- 最终拒绝层：`ContentStrategyRepository.create_strategy_bundle()`，错误为 `Source Opportunity 不存在: 1`。
- 自动测试漏检原因：Workflow 测试的 Fake semantic 直接返回固定 `source_opportunity_id=41`，Query Artifact 测试未断言 Research 投影包含 opportunity identity，两个合同之间没有闭环覆盖。
- partial data：无。失败 Run 下 `workflow_operation=0`；`content_strategy_artifact=0`；派生 `content_opportunity=0`。Artifact Tool 的事务已回滚。

## 二、Failure Data Flow

`Research 2862 / Opportunity 3923 -> QueryArtifact Research projection（identity 丢失） -> Workflow historical_opportunities=[] -> Semantic source_opportunity_id=1 -> Artifact Tool Input -> Repository 拒绝不存在的 Source Opportunity`

失败 Run：`wfr_51700d8be09b4e1cb04341be2afbbf17`，`FAILED`，checkpoint 3，error `VALIDATION_ERROR`。

## 三、Minimal Fix

仅修改 `backend/app/agent/tools/query_tools.py`：Research Artifact 投影复用现有 `ContentStrategyRepository.list_opportunities()`，把 canonical opportunity ID 与必要事实写入 `content_opportunities`，供现有 Workflow 的 `historical_opportunities` 使用。

未修改 Repository/Service owner、Workflow 结构、Runtime、Operation Ledger、数据库 Schema、Migration、Route、Pydantic 强度或 Expected Result。

## 四、Regression Test

- 新增回归：`test_research_query_exposes_canonical_opportunity_ids_for_strategy_lineage`。
- 修复前：FAIL，`KeyError: content_opportunities`。
- 修复后：相关 Query / Strategy Workflow / Strategy Persistence / Artifact Tool / Operation Ledger：`38 passed`。

## 五、E2E-002 Retry

- Conversation：874
- Turn：61
- client_request_id：`phase27b-e2e002-defect005-retry-20260923-01`
- Intent：`CONTENT_STRATEGY`
- Actual：`CLARIFY / WAITING_USER`
- Run：未创建
- Latency：15370 ms
- Clarification：`未明确选题的具体范围、数量或偏好`
- Result：未达到 E2E-002 成功标准，登记 `DEFECT-006` 后停止。

## 六、Strategy Artifact

本次 Retry 未进入 Workflow，未创建 Strategy Artifact。DEFECT-005 原失败事务也无 partial Strategy Artifact。

## 七、Opportunity

Research 2862 的 canonical source opportunity 为 3923。本次 Retry 未创建派生 Opportunity。

## 八、Research Reuse Verification

仍使用 conversation 874 的 Research 2862；没有重跑 Research，没有重新采集 URL，没有显式传入 `research_ref`。

## 九、Regression

DEFECT-005 定向回归通过。由于 DEFECT-006 是新的真实产品缺陷，按 Stop Point 规则未继续完整回归、Frontend、E2E-003 或后续 Case。

## 十、Phase 2.7B 当前状态

`BLOCKED / NOT ACCEPTED`。DEFECT-005 `FIXED / VERIFIED`；后续 DEFECT-006 已修复并由真实 Run 创建验证，当前由 DEFECT-007 阻塞。

## 十一、下一步

先对 DEFECT-006 单独执行 Root Cause Analysis，保留 Expected / Actual / Root Cause / Fix / Regression Case / Verification，再决定是否最小修复。

## 十二、Git

工作区已有大量用户修改，均保留。DEFECT-005 本轮仅改 Query Artifact Research 投影、新增其回归测试及验收文档；Migration = 0，New Route = 0。
