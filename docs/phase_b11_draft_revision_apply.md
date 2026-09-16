# B11 Draft Revision Apply V0

## 目标

B11 在 B10 已生成 `DraftRevisionPlan` 后，允许用户确认“按修改计划生成新版本”。系统读取原 `ContentDraft`、`DraftRevisionPlan`、`ReviewReport`、`ContentExperiment`，通过统一 `LLMClient` 生成修改后的草稿，并保存为新的 `ContentDraft` 记录。

B11 会调用模型，也会创建新草稿版本，但不会覆盖原稿。

## B10 和 B11 的关系

B10 只生成结构化修改计划，记录用户反馈、计划操作、保留项、禁改项和风险修复项。

B11 只接受 `status=READY` 的 RevisionPlan。服务根据 plan 中的 `draft_id` 找到 source draft，并把 RevisionPlan 的 operations、preserve、must_not_change、risk_fixes 作为改稿约束。

## 为什么不覆盖原稿

原稿是 B8/B9 之后的可审计产物。直接覆盖会破坏“用户反馈前后的内容差异”和风险审计链路。B11 创建新的 `ContentDraft` 记录，source draft 保持原样。

## 新版本如何追溯原稿

本轮没有大改 `content_draft` 表，也没有新增 apply_run 表。追溯信息写入新草稿的 `generation_context` JSON：

- `source = draft_revision_apply_b11`
- `source_draft_id`
- `revised_from_draft_id`
- `revision_plan_id`
- `review_report_id`
- `account_id`
- `plan_snapshot`
- `review_report_summary`
- `source_draft_updated_at`

新草稿 `status=REVISED`，`version=source_draft.version + 1`，并创建一条 `ContentDraftVersion` 快照。

## Stale Plan 校验

B10 创建计划时记录 `base_draft_updated_at`。B11 apply 时如果 source draft 的 `updated_at` 大于这个时间，返回：

- `status=STALE_PLAN`
- 不调用 LLM
- 不创建新草稿

用户需要重新生成修改计划。

## LLM 调用边界

API 层只调用 `DraftRevisionApplyService`。服务通过统一 `LLMClient.generate_structured` 调用 provider，不直接 import Qwen、DeepSeek、OpenAI 等 SDK。

LLM 必须输出结构化 JSON：

- `title`
- `content`
- `tags`
- `cta`
- `change_summary`
- `applied_operations`

## Provider 不可用处理

provider 未配置或不可用时返回：

- `status=PROVIDER_NOT_CONFIGURED`
- `revised_draft_id=null`

不会 fallback mock，也不会创建假草稿。

## 失败时为什么不创建假草稿

LLM parse/schema 失败时没有可信的新草稿内容。此时返回 `FAILED`，不创建空草稿、不拼接伪内容，也不修改原稿。

## 前端展示

Agent Workbench 在 B10 RevisionPlan 展示区后新增“应用修改计划”：

- 展示 `plan_id`、`source_draft_id`、plan summary
- 支持用户补充修改要求
- 点击“确认并生成新版本”
- 成功后展示 `revised_draft_id`、title、content、tags、cta、change_summary 和 applied operations
- `STALE_PLAN` 时提示原草稿已变化，需要重新生成修改计划

页面明确提示：

- 会调用模型
- 会创建新草稿版本
- 不覆盖原稿
- 不发布到小红书
- 不自动评论
- 不写长期记忆

## 测试结果

新增测试文件：`backend/tests/test_draft_revision_apply_api.py`

覆盖：

- `confirmed=false` 不调用 LLM、不创建新 draft
- plan 不存在
- plan.status != READY
- account_id 不匹配
- source_draft_id 和 plan.draft_id 不一致
- stale plan 返回 `STALE_PLAN`
- provider 未配置
- FakeLLMClient 成功生成新草稿
- 成功后创建新的 `ContentDraft`
- 原草稿内容不变
- 新草稿通过 `generation_context` 追溯 source draft / plan / review report
- LLM 非 JSON 返回 `FAILED`
- LLM schema 错误返回 `FAILED`
- 不创建 StrategyMemory
- 不自动发布
- 不自动评论
- 不重新生成 Evidence
- 不调用 CompetitorReportService.create_report

## 本轮没有做什么

- 不覆盖原草稿
- 不直接 update 原 draft title/body/tags/cta
- 不删除原草稿
- 不自动发布
- 不自动评论
- 不写 StrategyMemory
- 不写 CandidateMemory
- 不重新生成 Evidence
- 不重新运行 OperationRun
- 不创建 ContentExperiment
- 不创建 ContentOpportunity
- 不访问外部链接
- 不引入 LangChain / LangGraph / Mem0 / Langfuse

## B12 计划

B12 可以继续做：

- 新旧草稿差异对比
- 修改后再次触发受控 Review
- 用户选择 revised draft 进入发布准备
- 将 apply 历史升级为独立表，仅在需要查询完整 apply run 历史时再做
- 发布后再考虑把验证过的反馈沉淀为 StrategyMemory
