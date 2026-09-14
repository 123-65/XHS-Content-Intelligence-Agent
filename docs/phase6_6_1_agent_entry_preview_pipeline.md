# 1. 本阶段目标

第 6.6.1 阶段的目标，是把 6.1 到 6.6 已经完成的 Router、Planner、Validator、ConfirmationCard 和 Controlled Execution Orchestrator 串成一条可演示的 Agent 入口链路。

这条链路不负责真实生成草稿、不写业务数据、不调用工作流，也不连接前端。它只回答一个工程问题：一条自然语言输入进入系统后，如何被理解、规划、校验、要求确认、阻断，或者进入 dry-run 预演。

# 2. 为什么 6.6 后不直接接复杂业务 service

6.6 已经具备受控执行编排的雏形，但如果此时直接连接真实业务 service，入口层的工程价值会被业务副作用淹没：一次演示可能同时涉及数据库、LLM、草稿生成、报告生成、外部平台能力和权限边界。

本阶段先做 Agent Entry Preview Pipeline，是为了把隐藏在后端代码里的工程价值可视化，让用户和面试官看到：一句自然语言输入如何被理解、规划、校验、确认或阻断。

# 3. Agent Entry Preview Pipeline 是什么

`AgentEntryPreviewPipeline` 是一个入口预览编排器。它接收 `AgentChatRequest`，转换成 `AgentInput`，然后依次调用 Router、Planner、Validator、ConfirmationCard 和 Orchestrator 的 dry-run 模式，最后返回统一的 `AgentChatResponse`。

它是产品入口层的“预演链路”，不是业务执行链路。

# 4. 它串联了哪些已有模块

本阶段复用了这些已有模块：

- `LLMUserInputRouter`：识别用户意图、目标对象、参数和风险。
- `LLMTaskPlanner`：把 RouterResult 规划成结构化 Plan。
- `validate_plan_params`：检查 PlanStep 参数完整性和类型。
- `validate_param_sources`：检查敏感 ID 是否来自可信上下文。
- `validate_plan_result`：统一收敛 Plan 的执行资格、确认要求和阻断原因。
- `build_confirmation_card`：构造澄清、确认或阻断卡片。
- `ExecutionOrchestrator`：仅以 `ExecutionMode.DRY_RUN` 预演执行链路。
- `AgentEntryTraceRecorder`：记录输入、路由、规划、校验、卡片、执行和响应事件。

# 5. 为什么本阶段只 dry-run

入口预览阶段必须保证没有业务副作用。即使 Plan 通过校验，Pipeline 也只允许调用 `ExecutionMode.DRY_RUN`。

这样可以展示“如果进入执行，会发生什么”，但不会真的调用 handler、不会生成草稿、不会写 StrategyMemory、不会发布小红书，也不会修改任何外部账号。

# 6. 四类典型响应：澄清、确认、阻断、dry-run 预览

澄清：当用户说“这个不行”但没有 `current_target` 时，Router 会识别到反馈意图，但 Validator 会标记目标不明确，最终返回 `NEED_CLARIFICATION` 和“需要补充信息”卡片。

确认：当计划包含 `CREATE_CANDIDATE_MEMORY` 或 `LOCAL_WRITE` 时，系统不会直接执行，而是返回 `WAITING_CONFIRMATION` 和“请确认执行计划”卡片。

阻断：当用户要求“直接帮我发布到小红书”时，计划会被识别为外部写入风险，返回 `BLOCKED`，风险标记包含 `EXTERNAL_WRITE` 和 `CAPABILITY_BOUNDARY_EXCEEDED`。

dry-run 预览：当参数齐全、无确认、无阻断时，Pipeline 仍然只返回 dry-run 结果，message 会明确说明“计划已通过校验，本阶段仅预演，不执行业务。”

# 7. Trace 如何展示完整入口链路

Pipeline 会创建 `AgentEntryTraceRecorder`，并把完整 trace 的轻量 payload 放入 `response.metadata["entry_trace"]`。

Trace 中能看到这些关键阶段：

- `INPUT_RECEIVED`
- `ROUTER_PROMPT_BUILT`
- `ROUTER_RESULT_PARSED`
- `ROUTER_VALIDATED`
- `PLANNER_PROMPT_BUILT`
- `PLAN_PARSED`
- `PLAN_REGISTRY_APPLIED`
- `PARAM_VALIDATED`
- `PLAN_VALIDATED`
- `CONFIRMATION_CARD_BUILT`
- `EXECUTION_STARTED`
- `EXECUTION_FINISHED` 或 `EXECUTION_BLOCKED`
- `RESPONSE_BUILT`

# 8. Demo 案例说明

Demo 脚本是 `backend/scripts/agent_entry_preview_demo.py`，结果保存到 `docs/demo_agent_entry_preview_result.json`。

脚本内置四个案例：

- “我想写一篇 27 届双非本科做 Agent 求职的帖子”：Router 识别生成内容机会意图，Planner 规划内容机会步骤，Validator 发现缺少 `account_id`，返回澄清卡片。
- “这个不行”：没有当前目标对象，返回 `NEED_CLARIFICATION`。
- “这个标题太 AI 了，换自然一点”：带 `current_target_type=DRAFT`、`current_target_id=123`，Planner 规划 `REFINE_DRAFT`，并因候选记忆步骤进入确认态。
- “直接帮我发布到小红书”：被阻断为外部写入风险，返回 `BLOCKED`。

Demo 使用 `FakeLLMClient`，不调用真实 LLM，不消耗真实模型额度。

# 9. 当前仍未做什么

本阶段没有接入 Agent Chat API。

本阶段没有做最小前端。

本阶段没有调用真实 LLM、OpenAI SDK、Qwen SDK 或 DeepSeek SDK。

本阶段没有调用业务 service、workflow、数据库读写或外部平台写入能力。

本阶段没有真正生成草稿、竞品报告或 StrategyMemory。

# 10. 下一步如何做 Agent Chat API 和最小前端

下一步可以先做 Agent Chat API，把 `AgentChatRequest` 到 `AgentChatResponse` 暴露为后端接口，并继续保持 dry-run 和无副作用边界。

再下一步可以做最小前端：一个输入框、一个响应区、一个 ConfirmationCard 区域、一个 Trace 展开区。这样面试展示时就能从自然语言输入一路看到 Router、Planner、Validator、Confirmation 和 dry-run Trace。
