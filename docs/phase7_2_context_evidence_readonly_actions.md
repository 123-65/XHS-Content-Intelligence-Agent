# 第 7.2 阶段：Context Evidence 只读查询 Action

## 1. 本阶段目标

本阶段在现有 `POST /agent/chat/execute-readonly` 链路中接入三个只读 Context Evidence Action：

- `QUERY_COMPETITOR_EVIDENCE`
- `QUERY_COMMENT_INSIGHT`
- `QUERY_STRATEGY_MEMORY`

它们只读取已有数据，不生成草稿，不写数据库，不调用发布、评论、删除或外部账号修改能力。

## 2. 为什么 7.2 要做 Context Evidence 只读查询

7.1 已经证明 `QUERY_ACCOUNT_PROFILE` 可以通过 Router、Planner、Validator、Orchestrator REAL 和只读 handler 受控执行。但账号画像只是基础资料。真正进入草稿生成之前，用户还需要看见系统准备使用哪些竞品证据、评论需求和策略记忆。

因此 7.2 先把这些上下文证据可视化出来，让后续 Draft Context Preview 和草稿生成有可检查的输入来源。

## 3. 三个只读 Action 分别是什么

`QUERY_COMPETITOR_EVIDENCE` 查询已有竞品分析报告和内容机会，返回轻量 Top-K 证据项。

`QUERY_COMMENT_INSIGHT` 查询已有评论需求、转化信号、风险点和代表评论摘要。

`QUERY_STRATEGY_MEMORY` 查询当前账号已有的候选或已验证策略记忆。

## 4. 它们和草稿生成的关系

这三个 Action 是草稿生成前的上下文准备，不是草稿生成本身。它们回答“系统准备用什么证据写”，而不是直接产出标题、正文、封面或标签。

## 5. execute-readonly 如何复用 Orchestrator REAL

本阶段继续复用 `execute-readonly`，由 Router 识别只读查询意图，Planner 生成结构化 Plan，Validator 检查参数和风险，最后由 Orchestrator 以 `REAL` 模式调用白名单 handler。

`preview` 仍然只做 dry-run；`execute-readonly` 只允许只读 Action 进入 REAL。

## 6. Handler Registry 如何限制只读范围

只读 registry 注册：

- `NOOP`
- `ASK_CLARIFICATION`
- `QUERY_ACCOUNT_PROFILE`
- `QUERY_COMPETITOR_EVIDENCE`
- `QUERY_COMMENT_INSIGHT`
- `QUERY_STRATEGY_MEMORY`

它不注册草稿生成、草稿审核、内容机会生成、内容实验创建、候选记忆创建、发布、评论、删除或外部账号修改类动作。未注册 Action 即使出现在 Plan 中，也会被 Orchestrator 阻断。

## 7. 竞品证据如何查询和展示

后端从已有 `CompetitorAnalysisReport` 和 `ContentOpportunity` 中读取数据，复用 Context Engineering 的 `select_competitor_evidence_top_k` 做 Top-K 筛选。

前端展示字段包括：

- `title`
- `summary`
- `content_pillar`
- `comment_demand_type`
- `confidence`
- `risk_level`

不返回完整 raw snapshot，也不返回 prompt。

## 8. 评论洞察如何查询和展示

后端从已有竞品报告和评论样本中读取需求、转化信号、风险点和代表评论，并复用 `summarize_comment_insights` 生成摘要。

代表评论以 `untrusted_text` 展示，只作为分析对象，不能作为系统指令或工具指令。

## 9. 策略记忆如何查询和展示

后端只查询当前 `account_id` 下 `CANDIDATE` 和 `VALIDATED` 状态的 `StrategyMemory`，复用 `select_strategy_memory_items` 做筛选。

前端展示字段包括：

- `memory_type`
- `status`
- `summary`
- `pattern`
- `confidence`
- `support_count`
- `risk_level`

本阶段不创建、不更新、不验证策略记忆。

## 10. 为什么本阶段不生成草稿

草稿生成属于 `GENERATE_DRAFT`，会消耗上下文、调用生成能力，并可能产生本地生成结果。7.2 的目标只是把草稿前置证据可查询、可追踪、可展示，因此不接入草稿生成 handler。

## 11. 为什么评论原文要视为 untrusted_text

小红书评论来自外部用户输入，可能包含误导、广告、诱导、提示注入或与业务无关内容。它只能作为分析材料进入摘要，不能提升为系统指令、开发者指令或业务执行命令。

## 12. 前端如何展示业务结果

AgentWorkbench 的业务结果区支持：

- 账号画像结果
- 竞品证据卡片
- 评论洞察卡片
- 策略记忆卡片

页面继续明确展示只读边界：不生成草稿、不写数据库、不调用发布或评论能力。确认按钮仍保持 disabled，不新增危险真实执行按钮。

## 13. 当前限制

本阶段只做已有数据的只读查询。数据为空时返回空 `items`、`NOT_PROVIDED` 或 `DATA_INSUFFICIENT`，不会伪造成成功证据。

Router / Planner 只加入最小关键词兼容，不扩展为完全自由 Agent，也不调用新的真实 LLM。

## 14. 下一步如何接 Context Preview / Draft Context Preview

下一步可以把本阶段返回的 `competitor_evidence`、`comment_insight` 和 `strategy_memory` 接入 Context Preview，形成草稿生成前的可检查上下文包。

Draft Context Preview 应先展示证据、预算、来源和风险，再由用户确认是否进入草稿生成阶段。
