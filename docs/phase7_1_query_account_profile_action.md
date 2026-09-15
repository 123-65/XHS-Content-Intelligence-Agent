# 1. 本阶段目标

第 7.1 阶段接入第一个真实只读 Action：`QUERY_ACCOUNT_PROFILE`。

目标是证明通过 Router / Planner / Validator 校验后的 Plan，可以由 Execution Orchestrator 在 `REAL` 模式下受控调用业务 handler，并把账号画像摘要返回给前端和 Trace。

# 2. 为什么第一个真实 Action 选择 QUERY_ACCOUNT_PROFILE

`QUERY_ACCOUNT_PROFILE` 是低风险只读动作。它只读取本地 `AccountProfile`，不调用 LLM，不写数据库，不访问外部平台，也不会发布、评论、删除或修改外部账号。

账号画像还是后续内容机会、实验、草稿、审核和复盘链路的基础上下文，所以适合作为第一个真实 Action 验证 Handler Registry + Orchestrator REAL 模式。

# 3. 它和 preview dry-run 的区别

`POST /agent/chat/preview` 永远只做 dry-run：展示 Router、Plan、Validator、Confirmation、Execution dry-run 和 Trace，不调用业务 handler。

`POST /agent/chat/execute-readonly` 会先走同样的 Router / Planner / Validator 链路，通过后才用 Orchestrator 的 `REAL` 模式执行白名单只读 handler。

# 4. execute-readonly API 设计

新增接口：

`POST /agent/chat/execute-readonly`

输入：`AgentChatRequest`

输出：`AgentChatResponse`

当前只允许 `QUERY_ACCOUNT_PROFILE` 真实执行。缺少 `account_id` 返回 `NEED_CLARIFICATION`；需要确认返回 `WAITING_CONFIRMATION`；高风险或未注册 Action 返回 `BLOCKED`；账号不存在或 handler 失败返回 `FAILED`。

# 5. Handler Registry 如何限制真实执行范围

只读执行服务使用 `build_readonly_action_handler_registry(db)` 构建白名单 registry。

当前只包含：

- `NOOP`
- `ASK_CLARIFICATION`
- `QUERY_ACCOUNT_PROFILE`

没有注册 `GENERATE_DRAFT`、`REVIEW_DRAFT`、`GENERATE_CONTENT_OPPORTUNITY`、`CREATE_CONTENT_EXPERIMENT` 或任何写库、发布、评论、删除类动作。未注册 Action 即使 Plan 通过基础校验，也会被 Orchestrator 阻断。

# 6. QUERY_ACCOUNT_PROFILE handler 如何读取账号画像

`query_account_profile_handler(step, context)` 从 `step.input_params`、`step.inputs` 或 `context` 中读取 `account_id`，再复用现有 `AccountProfileService.get_account()` 查询账号。

返回结果只包含轻量账号画像摘要字段：

- `account_id`
- `account_name`
- `platform`
- `content_domain`
- `positioning`
- `target_audience`
- `persona`
- `tone_preference`
- `risk_preference`
- `account_stage`
- `primary_goal`
- `summary`

handler 不返回 raw secret，不写数据库，不调用 LLM。

# 7. 为什么不直接在 API 层查数据库

API 层只负责接收请求、注入依赖和统一兜底错误。

真实业务读取必须通过 Orchestrator + Handler Registry，原因是：

- 保证所有真实执行都先经过 Validator；
- 保证 Action 是否允许执行由白名单控制；
- 保证执行过程能进入统一 Trace；
- 避免每个 API 自己绕过计划校验直接访问业务服务。

# 8. 为什么本阶段不接草稿生成 / 发布 / 写库动作

草稿生成、内容机会、实验生成、策略记忆写入和发布评论等动作，要么需要 LLM，要么会产生本地写入或外部平台风险。

第 7.1 阶段只验证安全只读闭环，不扩大到 `GENERATE_DRAFT`、`REVIEW_DRAFT`、`GENERATE_CONTENT_OPPORTUNITY`、`GENERATE_CONTENT_EXPERIMENT` 或任何写库、外部写入、破坏性动作。

# 9. 前端如何触发只读查询

Agent 工作台保留原有“发送预览”按钮，新增“执行只读查询”按钮。

该按钮只调用：

`POST /agent/chat/execute-readonly`

按钮旁明确提示：当前只支持 `QUERY_ACCOUNT_PROFILE`，只读，不写数据库。

# 10. Trace 如何记录真实只读执行

只读执行链路继续使用 Agent Entry Trace。

成功执行时 Trace 包含：

- `INPUT_RECEIVED`
- `ROUTER_VALIDATED`
- `PLAN_VALIDATED`
- `PARAM_VALIDATED`
- `CONFIRMATION_CARD_BUILT`
- `EXECUTION_STARTED`
- `STEP_EXECUTION_STARTED`
- `STEP_EXECUTION_FINISHED`
- `EXECUTION_FINISHED`
- `RESPONSE_BUILT`

前端仍展示 Trace Timeline，业务结果放在 `metadata.business_result`。

# 11. 当前限制

当前只真实执行 `QUERY_ACCOUNT_PROFILE`。

账号画像关键词采用最小确定性兼容，命中“查看账号画像 / 当前账号画像 / 账号信息 / 账号定位 / 查询账号”时生成账号画像查询 plan。其它任务不因为本阶段而获得真实执行能力。

# 12. 下一步如何接 Context Evidence 只读查询

下一步可以沿用本阶段模式接入 Context Evidence 只读查询：

- 新增只读 handler；
- 扩展只读 registry 白名单；
- 保持 Param Validator 和 Plan Validator 前置；
- Orchestrator 仍使用 `REAL` 模式；
- Trace 记录每个只读 step；
- 前端只展示结果，不提供写入或外部执行入口。
