# 1. 本阶段目标

第 6.6.2 阶段的目标，是把第 6.6.1 已经打通的 Agent Entry Preview Pipeline 包装成后端 API。

本阶段新增 `POST /agent/chat/preview`，输入是 `AgentChatRequest`，输出是 `AgentChatResponse`。它让前端后续可以通过一个统一入口，把用户自然语言输入送入 Router、Planner、Validator、ConfirmationCard 和 Orchestrator dry-run 链路。

# 2. 为什么 6.6.1 后要先做 Agent Chat API

6.6.1 仍然是 Python Pipeline 和 demo 脚本，适合工程验证，但不适合产品演示。

6.6.2 先做 API，是为了让入口链路具备产品形态：前端以后只需要提交一段用户输入，就能拿到结构化意图、计划、确认卡片、阻断原因和 Trace。这样工程价值不再停留在测试里，而是可以被真实页面消费。

# 3. POST /agent/chat/preview 是什么

`POST /agent/chat/preview` 不是普通聊天接口。

它是受控 Agent 工作台的统一入口。用户输入不会直接触发业务动作，而是先被结构化理解，再被规划、校验、确认或阻断，最后只进入 dry-run 预演。

当前阶段接口路径是：

```text
POST /agent/chat/preview
```

# 4. 请求 AgentChatRequest 字段说明

典型请求如下：

```json
{
  "session_id": "demo-topic",
  "account_id": null,
  "text": "我想写一篇 27 届双非本科做 Agent 求职的帖子",
  "input_type": "TEXT",
  "attachments": [],
  "context": {}
}
```

核心字段：

- `session_id`：当前会话 ID，用于串联入口 Trace。
- `account_id`：当前选中的账号 ID，可以为空；为空时 Pipeline 不会补造。
- `text`：用户在输入框里的自然语言需求。
- `input_type`：输入类型，例如 `TEXT`、`IMAGE`、`URL`、`MIXED`。
- `attachments`：附件元信息，本阶段不读取真实文件内容。
- `context`：前端传入的轻量上下文。
- `current_target_type` / `current_target_id`：用于表达“这个标题”“这篇草稿”等指代对象。

# 5. 响应 AgentChatResponse 字段说明

接口直接返回 `AgentChatResponse`，不再包一层 `code/message/data`。

核心字段：

- `status`：入口处理状态，例如 `NEED_CLARIFICATION`、`WAITING_CONFIRMATION`、`BLOCKED`、`READY_TO_EXECUTE`、`FAILED`。
- `router_result`：Router 对用户输入的结构化理解。
- `plan`：Planner 生成的任务计划。
- `param_validation`：参数完整性和参数来源校验结果。
- `plan_validation`：计划层最终校验结果。
- `confirmation_card`：前端可渲染的澄清、确认或阻断卡片。
- `can_execute`：是否通过预演链路的可执行校验。
- `requires_confirmation`：是否需要用户确认。
- `trace_id`：本次入口 Trace ID。
- `metadata.execution`：Orchestrator dry-run 结果。
- `metadata.entry_trace`：完整入口链路 Trace。

# 6. 接口内部如何串联 Pipeline

API 层只做三件事：

- 接收并校验 `AgentChatRequest`。
- 通过依赖注入拿到 `AgentChatPreviewService`。
- 调用 `service.preview(request)` 并返回 `AgentChatResponse`。

`AgentChatPreviewService` 也保持很薄，只封装 `AgentEntryPreviewPipeline.preview()`。它不自己理解用户意图，不查数据库，不写数据库，也不调用业务 service。

# 7. 为什么本接口只 dry-run，不真实执行

这个接口用于入口预览，不是业务执行接口。

即使 Plan 参数完整、校验通过，当前阶段也只允许 `ExecutionMode.DRY_RUN`。这样前端可以看到系统打算做什么，但不会真的生成草稿、写候选记忆、生成竞品报告或触发外部平台动作。

# 8. 为什么 API 层不能直接依赖 OpenAI / Qwen SDK

API 层不能直接 import OpenAI、Qwen 或 DeepSeek SDK，因为接口层应该只表达产品协议和依赖注入边界。

真实模型提供方只允许隐藏在已有 `LLMClient` 和 Provider Adapter 内。这样可以保证后续切换模型、处理配置缺失、禁止 mock fallback、统一错误码时，不需要改 API 层。

# 9. 四类典型响应：澄清、确认、阻断、dry-run 预览

澄清：新选题缺少 `account_id`，或者用户说“这个不行”但没有当前目标对象时，返回 `NEED_CLARIFICATION` 和“需要补充信息”卡片。

确认：用户要求优化当前草稿标题，并且计划包含 `CREATE_CANDIDATE_MEMORY` 等候选写入动作时，返回 `WAITING_CONFIRMATION` 和“请确认执行计划”卡片。

阻断：用户要求“直接帮我发布到小红书”时，返回 `BLOCKED`，风险标记包含 `EXTERNAL_WRITE` 和 `CAPABILITY_BOUNDARY_EXCEEDED`。

dry-run 预览：参数完整、无确认、无阻断时，返回 `READY_TO_EXECUTE`，但 `metadata.execution.mode` 仍然是 `DRY_RUN`，message 会说明本阶段仅预演，不执行业务。

# 10. Trace 如何返回给前端

接口返回的 `metadata.entry_trace` 是轻量 Trace payload，包含：

- `trace_id`
- `session_id`
- `agent_type`
- `workflow_name`
- `final_status`
- `final_intent`
- `final_confirmation_requirement`
- `final_can_execute`
- `events`

前端后续可以用它做开发者 Trace 面板，让用户或面试官看到自然语言输入如何一步步进入 Router、Planner、Validator、ConfirmationCard 和 Orchestrator dry-run。

# 11. 当前没有接真实业务 service 的原因

当前目标是把入口层工程价值产品化，而不是提前制造业务副作用。

如果此时直接接草稿生成、竞品报告、StrategyMemory 或外部平台发布，接口演示会变成复杂业务链路调试。6.6.2 先保持 dry-run，可以让边界更清楚：哪些动作需要补参数，哪些动作需要确认，哪些动作必须被阻断。

# 12. 下一步如何做最小前端输入框和确认卡片

下一步可以做最小前端页面：

- 一个输入框，提交 `AgentChatRequest`。
- 一个响应区域，展示 `status`、`message` 和 `can_execute`。
- 一个 ConfirmationCard 区域，展示补充信息、确认计划或阻断原因。
- 一个 Trace 折叠面板，展示 `metadata.entry_trace.events`。

这样就能把 Agent 工作台入口从后端 API 变成完整可演示产品界面。
