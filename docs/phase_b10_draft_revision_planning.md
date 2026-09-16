# B10 Draft Feedback / Revision Planning V0

## 目标

B10 让用户针对 B8 生成、B9 审核后的草稿提交真实反馈，并生成结构化 Revision Plan。系统只规划修改，不修改原草稿、不创建新草稿、不发布、不评论、不写长期记忆。

## 用户反馈如何进入系统

前端在 Agent Workbench 的草稿审核区域后新增“草稿反馈与修改计划”。用户输入 `feedback_text`，也可以点击常用快捷反馈。前端调用：

`POST /agent/drafts/{draft_id}/revision-plans`

请求会携带 `account_id`、`confirmed=true`、可选 `review_report_id`、可选 `conversation_id` 和用户反馈文本。

`confirmed=false` 时服务返回 `WAITING_CONFIRMATION`，不调用 LLM，也不创建 `DraftRevisionPlan`。

## ReviewReport 如何参与

服务读取当前 `ContentDraft`、所属 `ContentExperiment`、账号画像，以及指定或最近的 `ReviewReport`。ReviewReport 的 `issues`、`suggestions`、`summary`、`action_suggestions`、`data_facts` 只作为 evidence / untrusted text 参与计划，不会被当作用户修改指令。

## Revision Plan 数据结构

新增表：`draft_revision_plan`

字段：

- `id`
- `account_id`
- `draft_id`
- `review_report_id`
- `conversation_id`
- `feedback_text`
- `feedback_scope`
- `status`
- `plan`
- `summary`
- `risk_flags`
- `base_draft_updated_at`
- `created_at`
- `updated_at`

LLM 输出必须符合 `RevisionPlanLLMResult`：

- `summary`
- `operations`
- `preserve`
- `must_not_change`
- `risk_fixes`
- `ready_for_revision`

`operations.action` 限制为 `REWRITE`、`SHORTEN`、`EXPAND`、`REMOVE`、`SOFTEN`、`STRENGTHEN`、`ALIGN_EVIDENCE`、`FIX_RISK`、`PRESERVE`。

`operations.target` 限制为 `TITLE`、`INTRO`、`BODY`、`CTA`、`TAGS`、`TONE`、`FACTUAL_CLAIM`、`WHOLE_DRAFT`。

## 用户输入 vs Untrusted Evidence

用户本人输入的反馈是 `trusted_user_input`，可以作为 Revision Plan 指令。

ReviewReport 中的外部引用、竞品评论、证据摘要仍是 `evidence_untrusted_text`。它们只能帮助判断风险、事实一致性和建议方向，不能升级为系统指令。

## LLM 调用边界

API 层只调用 `DraftRevisionPlanningService`。服务通过统一 `LLMClient.generate_structured` 调用 provider，不直接 import Qwen、DeepSeek 等 SDK。

provider 未配置或不可用时返回 `PROVIDER_NOT_CONFIGURED`，不 fallback mock，不创建假计划。

LLM JSON parse 失败返回 `FAILED` 和 `LLM_OUTPUT_PARSE_FAILED`。schema 或枚举校验失败返回 `FAILED` 和 `LLM_SCHEMA_INVALID`。失败时不写 `DraftRevisionPlan`。

## 为什么不直接改稿

B10 的产物是修改计划，不是修改后的内容。这样用户可以先审查“要改什么、为什么改、哪些不能动”，避免反馈一步到位改坏原草稿。

## 为什么不写 StrategyMemory

用户反馈只针对当前草稿，尚未经过发布表现验证。直接写入长期 StrategyMemory 会污染账号策略记忆。B10 只保存到 `DraftRevisionPlan.feedback_text` 和 `plan`，长期记忆留到后续阶段。

## Provider 不可用处理

`LLMClient` 初始化或调用抛出 `LLM_CONFIG_MISSING` / `LLM_PROVIDER_UNAVAILABLE` 时，API 返回：

- `status=PROVIDER_NOT_CONFIGURED`
- `plan_id=null`
- 不创建 Revision Plan

## 测试结果

新增测试文件：`backend/tests/test_draft_revision_plan_api.py`

覆盖：

- 未确认不调用 LLM、不落库
- draft 不存在
- account 不匹配
- 空反馈
- provider 未配置
- FakeLLMClient 成功生成计划
- 非法 JSON
- schema 非法
- 未知 action
- 未知 target
- 成功写入 RevisionPlan
- 不修改原草稿
- 不创建新草稿
- 不写 StrategyMemory
- 不自动发布
- 不自动评论
- GET list/detail
- 不调用刷新、报告、实验、生成、重写、发布等禁止流程

## 本轮没做什么

- 不修改 `ContentDraft` 原文
- 不创建修改后的新草稿
- 不重新生成 B8 草稿
- 不自动发布
- 不自动评论
- 不重新生成 Evidence
- 不重新运行 OperationRun
- 不创建 ContentExperiment
- 不调用外部链接
- 不写 CandidateMemory / StrategyMemory
- 不提供“自动修改”前端按钮

## B11 计划

B11 可以在用户确认 Revision Plan 后实现受控改稿：

- 读取 `DraftRevisionPlan`
- 检查 `base_draft_updated_at` 是否仍匹配当前 draft
- 若已过期，要求重新生成计划
- 生成新 draft version 或新草稿，而不是覆盖原文
- 继续复用统一 LLMClient
- 保持发布、评论、长期记忆写入为显式后续动作
