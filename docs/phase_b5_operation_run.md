# Phase B5 Operation Run / 今日运营分析 V0

## 1. B5 目标

B5 实现用户手动触发的“今日运营分析”。系统读取当前账号已有的 AccountProfile、DataSourceConfig、最近 DataRefreshRun、最近 EvidenceRefreshRun，以及 EvidenceRefreshRun 关联的 report / opportunities / breakdowns，生成只读运营建议摘要。

本阶段回答的是：

- 当前数据状态怎么样；
- 当前证据是否足够；
- 今天优先关注哪些方向；
- 推荐进入哪些内容机会；
- 为什么推荐；
- 下一步应该做什么。

## 2. OperationRun 和 DataRefreshRun / EvidenceRefreshRun 的区别

- B3 DataRefreshRun：记录用户手动触发的数据刷新请求。当前没有真实 Provider 时只记录状态，不伪造采集结果。
- B4 EvidenceRefreshRun：基于已经入库的真实竞品数据生成证据结构，复用 CompetitorReportService，产出 report / breakdown / opportunity。
- B5 OperationRun：只读取 B4 已有证据结果，生成运营建议摘要，不重新生成 evidence。

## 3. 为什么 B5 不重新刷新 Evidence

今日运营分析应该是“读证据并给建议”，不是再次分析竞品数据。如果 B5 重新调用 CompetitorReportService.create_report()，会导致一次按钮点击重复创建 report、breakdown 和 opportunity，也会模糊 B4 与 B5 的职责。

因此 B5 的正确链路是：

AccountProfile + DataSourceConfig + latest DataRefreshRun + latest EvidenceRefreshRun + existing report / opportunities / breakdowns -> OperationRun。

## 4. 后端新增内容

新增 `account_operation_run` 表，用于持久化一次只读运营分析运行记录。

新增文件：

- `backend/app/models/account_operation_run.py`
- `backend/app/schemas/operation_run.py`
- `backend/app/repositories/operation_run_repo.py`
- `backend/app/services/operation_run_sev.py`
- `backend/app/api/operation_run.py`
- `backend/alembic/versions/b5c6d7e8f9a0_add_account_operation_run.py`
- `backend/tests/test_operation_run_api.py`

API：

- `POST /agent/operation-runs`
- `GET /agent/operation-runs?account_id=1&limit=20`
- `GET /agent/operation-runs/{run_id}`

## 5. 前端新增内容

AgentWorkbench 增加“今日运营分析 / Operation Run V0”区域。

新增文件：

- `frontend/src/api/operationRun.ts`
- `frontend/src/types/operationRun.ts`

页面中可以：

- 查看当前选中的 account_id；
- 点击生成今日运营分析；
- 查看最近 OperationRun 列表；
- 展示 summary、recommendations、data_gaps、next_actions。

## 6. 推荐逻辑

B5 只使用工程排序规则，不新增内容理解规则：

- opportunity_score 高优先；
- 同分时 risk_level LOW 优先；
- 有 evidence_summary / comment_demand_type 时作为推荐原因字段展示；
- evidence status 为 PARTIAL 或 data_quality 非 READY 时降低 confidence；
- note_count / comment_count 不足时写入 data_gaps。

recommendations 最多返回 3 条。

## 7. 数据不足处理

数据不足不是系统错误，API 返回 HTTP 200，业务状态为 `DATA_INSUFFICIENT`。

典型情况：

- 没有 EvidenceRefreshRun：提示先执行证据刷新；
- EvidenceRefreshRun 为 DATA_INSUFFICIENT / FAILED：继承其 error_code 和 error_message；
- EvidenceRefreshRun 没有 report_id：提示重新执行证据刷新；
- 有 report 但没有 ContentOpportunity：提示没有可用内容机会；
- 样本不足：返回 PARTIAL 或写入低置信 data_gaps。

## 8. 为什么本阶段不调用 LLM

B5 是证据读取和运营建议摘要层，所有输入已经由 B4 结构化沉淀。此时使用固定工程排序更可控，也能避免模型把 untrusted input 当成指令。

后续如果需要 LLM 解释层，也应该通过统一 LLMClient / Provider Adapter 接入，并由 Validator 控制风险。

## 9. 为什么本阶段不生成草稿

OperationRun 只负责告诉用户“今天应该优先看什么、为什么、下一步做什么”。草稿生成属于后续阶段，需要额外的人工确认、上下文校验和生成链路。

B5 不创建 ContentExperiment，也不创建 ContentDraft。

## 10. 测试结果

本阶段测试覆盖：

- 无 EvidenceRefreshRun 返回 DATA_INSUFFICIENT；
- EvidenceRefreshRun 不可用时 OperationRun 同样 DATA_INSUFFICIENT；
- 有 report 但无 opportunity 时不伪造成成功；
- opportunities 最多生成 3 条 recommendations；
- recommendations 按 opportunity_score 排序；
- 同分时 high risk 不排在 low risk 前；
- PARTIAL evidence 生成 PARTIAL operation run；
- 成功后写入 AccountOperationRun；
- GET list/detail 可用；
- 不调用 LLM；
- 不访问外部链接；
- 不调用 CompetitorReportService.create_report；
- 不创建 report；
- 不创建 ContentOpportunity；
- B3/B4 回归测试继续通过。

## 11. 本阶段没有做什么

- 没有调用 LLM / SDK；
- 没有访问外部小红书或外部链接；
- 没有真实爬虫；
- 没有重新生成 Evidence；
- 没有创建假 report；
- 没有创建假 opportunity；
- 没有生成草稿；
- 没有审核草稿；
- 没有自动发布；
- 没有自动评论；
- 没有创建 ContentExperiment；
- 没有引入 LangChain / LangGraph / Mem0 / Langfuse。

## 12. 下一步 B6 计划

B6 可以在 B5 的 OperationRun 基础上进入“内容实验创建 V0”。建议仍然保持受控链路：

1. 用户从 OperationRun recommendation 中选择一个方向；
2. 系统生成实验创建预览；
3. Validator 检查 account_id、opportunity_id、风险和人工确认；
4. 用户确认后再创建 ContentExperiment；
5. 仍然不直接生成草稿、不自动发布。
