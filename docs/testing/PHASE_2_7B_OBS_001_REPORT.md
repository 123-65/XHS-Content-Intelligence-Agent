# Phase 2.7B OBS-001 可测试性补强报告

## 一、OBS-001 Root Cause

`prompt_run_log` 原先只有 ORM 模型和读取端，仓库内没有任何写入入口。`LLMClient.generate_structured()` 只补成功结果元数据，Provider 的 Tenacity decorator 隐藏了中间 attempts；异常映射最终只剩统一 safe error。因此 Turn 65 不是因事务回滚丢日志，而是成功、失败和 retry 从未被记录。

## 二、原失败路径为什么没有证据

- Provider parse/Pydantic detail 被压缩成异常字符串。
- 中间 invalid attempt 没有事件出口。
- Service post-parse `ValueError` 被 Semantic Tool 统一映射为 `VALIDATION_ERROR`。
- `prompt_run_log` 无 writer，所以对应时间窗口为 0。

## 三、Failure Evidence Contract

每个 structured attempt 现在记录 provider、model、prompt key/version、attempt number/total、attempt status、failure stage、validation layer/path、expected constraint、actual type、sanitized value/candidate、retryable、retry exhausted、final error code 与 latency。

Validation layer 区分：`PROVIDER_PARSE`、`PYDANTIC_SCHEMA`、`POST_PARSE_BUSINESS_VALIDATION`；Service transformation 可使用同一 recorder 标记 `SERVICE_TRANSFORMATION`。

## 四、安全与脱敏

- 不保存 system prompt、conversation、XHS 原文或完整 provider raw response。
- 不保存 API key、Authorization、Cookie、Secret、DB password、execution/lease token。
- 字符串内容仅保存长度与 SHA-256 短摘要；结构、数字 ID、类型和 validation path 保留。
- 日志以独立短事务写入现有 `prompt_run_log`，不随业务事务回滚。

## 五、Structured Retry Evidence

重试次数保持 `llm_max_retries=2`。显式 attempt 循环保存每次 `SUCCESS / VALIDATION_FAILED / PROVIDER_FAILED`；第一轮 invalid、第二轮 valid 会留下两条证据。没有 Mock 或 silent fallback，也未增加调用次数。

## 六、Minimal Fix

- 新增 `app/llm/evidence.py`：脱敏、validation summary、独立 PromptRun evidence writer。
- Provider structured generation 暴露逐次 attempt evidence，同时保持原 retry 上限和指数等待。
- LLMClient 写入 attempts，并提供 post-parse business validation evidence API。
- Content Strategy Service 仅为既有 evidence allowlist rejection 增加具体 path/actual evidence；未改变允许集合或校验结果。
- Migration 0，New Route 0。

## 七、Regression

- OBS-001 覆盖：首轮 Pydantic invalid、invalid→valid、全部 invalid、provider parse/provider failure、business ValueError、secret redaction。
- 初次定向：31 passed；Strategy/DEFECT-005/006：79 passed。
- 最终定向：47 passed。
- 完整后端：584 passed，3 skipped，18 warnings。
- `git diff --check` PASS（仅既有 LF/CRLF 提示）。
- Alembic current/head：`c7d8e9f0a1b2`。

## 八、真实复现结果

第 1 次即失败，按规则停止：

- Conversation：874
- Turn：69
- Run：`wfr_c143bd276777414f97187b00986f1569`
- Latency：15976 ms
- Intent/Action：`CONTENT_STRATEGY / EXECUTE_PLAN`
- Research：2862
- Opportunity：3923
- Workflow：`CONTENT_STRATEGY_V1`
- Status：FAILED at `strategy_generation`

捕获到两条独立 evidence：Provider/Pydantic attempt 1 `SUCCESS`（9400 ms），随后 post-parse business validation `VALIDATION_FAILED`。

## 九、DEFECT-007 当前状态

`OPEN / RCA CONFIRMED / NOT FIXED`。

确切根因：真实模型返回了结构合法且 identity 正确的 `content_opportunity:3923` EvidenceRef；`ContentStrategyService.generate_semantic()` 的 allowed set 只由顶层 `payload.evidence_refs` 构建，其中只有 `research_report:2862`，没有纳入同一输入 `historical_opportunities` 中的 canonical Opportunity 3923。于是 `_validate_evidence_refs()` 在 post-parse business validation 正确按当前代码拒绝该 ref。

这属于 Prompt/Input 与 deterministic evidence allowlist 的合同缺口，不是 Pydantic Schema failure，也不是模型伪造 ID。本轮按要求不修 DEFECT-007。

## 十、面试资产沉淀

- 新增 Q&A：3。
- 更新 Q&A：0。
- 文件：`docs/interview/INTERVIEW_QA.md`。

## 十一、下一步

下一任务可基于已捕获 fixture 独立处理 DEFECT-007：明确 historical canonical opportunity 是否应进入 authorized evidence set，再做合同级最小修复。本轮不执行 E2E-003，不进入 Testing Track。

## 十二、Git

保留原 dirty worktree；本轮新增 observability 代码、测试和文档。无 Migration、Route 或 LLM provider 架构变更。
