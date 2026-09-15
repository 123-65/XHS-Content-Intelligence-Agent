# 1. 本阶段目标

B1 阶段把 Agent Chat 从单次请求入口升级为可连续对话的产品入口。最低目标是创建会话、保存用户消息、保存 Agent 回复、保存与读取 Current State，并在第二轮请求中重新加载历史消息和状态。

本阶段的 Current State 只保存 V0 必需字段，不引入复杂状态机。

# 2. 为什么先做 Conversation，而不是继续接草稿生成

当前 Agent 已经具备 preview dry-run、execute-readonly、账号画像查询、上下文证据查询和草稿上下文预览能力，但这些能力仍偏单次请求。

如果用户连续表达“看看方向”“第二个不错”“写出来看看”，系统需要知道上一轮返回了什么、当前活跃账号是什么、当前目标对象是什么、是否存在待确认动作。没有 Conversation 和 Current State，直接接草稿生成会让后续指代解析和人工确认缺少基础。

# 3. Conversation / Message / Current State 设计

本阶段新增 `agent_conversation` 表和 `agent_conversation_message` 表。

Conversation 保存：

- `id`
- `account_id`
- `title`
- `status`
- `current_state`
- `created_at`
- `updated_at`
- `last_message_at`

Message 保存：

- `id`
- `conversation_id`
- `role`
- `content`
- `message_type`
- `metadata_payload`
- `trace_id`
- `created_at`

Current State 使用 Conversation 的 JSONB 字段保存：

- `current_goal`
- `active_account_id`
- `active_opportunity_id`
- `active_experiment_id`
- `active_draft_id`
- `current_target_type`
- `current_target_id`
- `last_action`
- `last_artifacts`
- `pending_confirmation`
- `conversation_constraints`

# 4. AgentChatRequest / Response 如何扩展

`AgentChatRequest` 新增：

- `conversation_id: int | None`

`AgentChatResponse` 新增：

- `conversation_id: int | None`

不传 `conversation_id` 时，preview 和 execute-readonly 保持原有单次请求行为。

# 5. preview / execute-readonly 如何保存消息

当请求带 `conversation_id` 时，Agent Chat Service 会：

1. 加载 Conversation；
2. 加载 Current State；
3. 加载最近消息；
4. 合并状态到请求上下文；
5. 保存 USER 消息；
6. 执行原有 preview 或 execute-readonly 链路；
7. 保存 ASSISTANT 消息；
8. 回写 Current State。

消息只保存轻量摘要，不保存完整 prompt、API Key 或超大 raw payload。

# 6. Current State 如何更新

V0 更新规则：

- request.account_id 存在时更新 `active_account_id`
- 只读业务结果有 account_id 时更新 `active_account_id`
- request.current_target_type / current_target_id 存在时更新当前目标
- request.context 中显式的 opportunity / experiment / draft ID 会更新 active 对象
- plan 最后一个 action 写入 `last_action`
- response 轻量摘要写入 `last_artifacts`，最多保留 5 条
- response.requires_confirmation 为 true 时写入 `pending_confirmation`
- response.requires_confirmation 为 false 时清空 `pending_confirmation`
- request.context.conversation_constraints 会合并进约束

# 7. 第二轮请求如何加载历史消息和状态

第二轮带 `conversation_id` 时，服务会把最近消息和 Current State 注入 `request.context.conversation`。

如果 request.account_id 为空，但 Current State 里有 `active_account_id`，系统会把它作为本轮 account_id 兜底。当前目标同理，只使用 state 中已有明确 ID，不编造业务 ID。

B1 不要求完美理解“第二个”，只要求历史消息和当前状态能被保存、读取并提供给下一轮 Agent。

# 8. 前端 AgentWorkbench 如何展示会话

AgentWorkbench 增加：

- `conversation_id` 输入
- 创建新会话
- 加载会话
- 刷新消息
- 当前会话 ID / title / status
- 消息历史列表
- Current State 展示

preview、execute-readonly 和草稿上下文预览都会携带当前 `conversation_id`。没有会话 ID 时仍允许发送，并提示不会保存历史。

# 9. 本阶段没有做什么

本阶段没有做：

- 复杂 Agent Core Loop
- Reference Resolver
- 完美理解“第二个 / 这个”
- 草稿生成
- 发布 / 评论 / 删除 / 修改外部账号
- Mem0
- LangChain / LangGraph
- Langfuse 完整接入
- LLM Provider 迁移
- 重写 Router / Planner / Validator / Orchestrator

# 10. 下一阶段：Draft Context Preview

B1 之后，Conversation 和 Current State 已经能承接多轮上下文。下一阶段可以继续沿用这些状态基础，把 Draft Context Preview 或真实草稿生成前确认接进多轮工作流。

真实生成仍必须经过参数校验、人工确认、上下文预览、LLM 调用治理和写库审计。
