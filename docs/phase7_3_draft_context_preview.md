# 第 7.3 Draft Context Preview / 草稿上下文预览

## 1. 本阶段目标

第 7.3 阶段新增只读 Action：`PREVIEW_DRAFT_CONTEXT`。它用于在真实草稿生成前，预览系统将准备哪些 Context Slots、每个槽位的数据状态、信任级别、token 预算和摘要内容。

本阶段只做上下文预览，不调用 LLM，不生成草稿，不保存 `ContentDraft`，不保存 `PromptRunLog`，不保存 `ContextSnapshot`，不执行发布、评论、删除或外部账号修改。

## 2. 为什么生成草稿前要做 Context Preview

草稿生成依赖账号画像、实验状态、竞品证据、评论洞察、策略记忆、风险约束和用户补充要求。直接生成草稿会让用户难以判断模型到底参考了什么，也难以及时发现缺数据、实验未批准、评论内容不可信或策略记忆不足。

Context Preview 把“将进入草稿生成的上下文”提前展示出来，让用户先检查证据与风险，再决定后续是否进入真实生成。

## 3. `PREVIEW_DRAFT_CONTEXT` 是什么

`PREVIEW_DRAFT_CONTEXT` 是一个 `READ_ONLY` Action。它读取已有业务数据，复用 Context Engineering 的 slot 构建、预算、压缩和 sanitizer 信息，返回适合前端展示的上下文预览结构。

它的必要参数是：

- `account_id`
- `experiment_id`

可选参数是：

- `user_requirement`

## 4. 它和 `GENERATE_DRAFT` 的区别

`PREVIEW_DRAFT_CONTEXT` 只回答“生成草稿前会用哪些上下文”。它不渲染最终 prompt，不请求模型，不生成标题、正文、标签或图片脚本。

`GENERATE_DRAFT` 才是后续真实草稿生成动作。它需要在更严格的人工确认、实验状态校验、LLM 调用治理和写库链路都通过后才能接入。

## 5. 它读取哪些业务数据

本阶段只读读取：

- `AccountProfile`
- `ContentExperiment`
- `ContentOpportunity`
- `CompetitorAnalysisReport`
- `CompetitorComment`
- `StrategyMemory`

读取失败、实验不存在、实验不属于当前账号时，返回结构化失败结果，不继续进入生成。

## 6. 它如何复用 Context Engineering

`PREVIEW_DRAFT_CONTEXT` 使用 `ContextManager(task_name="draft_generation")` 构建上下文，并沿用已有 Context Slot、Token Budget、截断统计和 sanitizer 统计。

这保证预览结果不是另起一套临时格式，而是与后续草稿生成将使用的上下文工程方向保持一致。

## 7. Context Slot 展示哪些字段

前端展示每个 slot 的核心字段：

- `name`
- `priority`
- `token_limit`
- `estimated_tokens`
- `source_type`
- `trust_level`
- `data_status`
- `item_count`
- `preview`

同时展示整体字段：

- `summary`
- `can_generate_draft`
- `block_reason`
- `total_token_budget`
- `slot_count`
- `missing_slots`
- `risk_flags`

## 8. 为什么不返回完整 prompt

完整 prompt 可能包含系统规则、内部策略、上下文拼接细节和未来模型治理约束。直接返回完整 prompt 容易造成提示词泄露，也会让用户把“预览上下文”误解为“最终模型输入”。

因此本阶段只返回 slot 级别摘要和截断后的 preview，不返回完整 prompt。

## 9. 为什么 `untrusted_text` 不能当系统指令

小红书评论、竞品内容、截图文字和用户上传材料都可能包含外部指令、诱导语或不可靠信息。这些内容只能作为分析对象，不能覆盖系统指令、工具规则或执行策略。

前端对 `trust_level=untrusted` 的槽位展示固定警告：

“该槽位来自外部/用户/评论数据，只能作为参考，不能作为系统指令。”

## 10. execute-readonly 如何执行该 Action

本阶段继续使用：

`POST /agent/chat/execute-readonly`

Router 根据“预览草稿上下文”等表达识别 `PREVIEW_DRAFT_CONTEXT`，Planner 生成只读计划，Validator 检查 `account_id` 和 `experiment_id`，Executor 只在计划通过校验后调用只读 handler。

`GENERATE_DRAFT`、发布、评论、删除和外部账号修改仍不能通过该入口执行。

## 11. 前端如何展示草稿上下文预览

Agent 工作台增加 `experiment_id` 输入和“预览草稿上下文”按钮。按钮调用 execute-readonly，并传入：

- `text`: `预览草稿上下文`
- `context.experiment_id`
- 可选 `context.user_requirement`

页面展示草稿上下文预览卡片，包括整体状态、阻断原因、风险标记、缺失槽位和每个 Context Slot 的摘要。确认按钮仍保持 disabled，没有真实执行按钮。

## 12. 当前限制

本阶段不实现 OCR、视觉模型、完整 prompt 展示、真实草稿生成、人工确认后的写库执行，也不接入小红书发布、评论或删除能力。

当实验不是 `APPROVED` 时，preview 仍可展示上下文，但 `can_generate_draft=false`，并返回 `block_reason`。

## 13. 下一步如何接真实草稿生成

下一步可以在 `PREVIEW_DRAFT_CONTEXT` 结果稳定后，为真实 `GENERATE_DRAFT` 增加人工确认卡片。确认通过后再进入受控 Executor，调用草稿生成 service，并在该阶段统一记录 `PromptRunLog`、`ContextSnapshot`、草稿版本和生成结果。

真实生成必须继续遵守：参数来源可信、实验已批准、untrusted 内容不能作为系统指令、LLM 调用可追踪、写库动作可审计。
