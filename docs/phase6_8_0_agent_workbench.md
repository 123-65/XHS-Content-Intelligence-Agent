# 1. 本阶段目标

第 6.8.0 阶段做最小前端 Agent 工作台，把第 6 阶段的入口链路从后端 JSON 变成可演示页面。

页面路径是 `/agent/workbench`。用户输入一句自然语言后，前端调用 `POST /agent/chat/preview`，展示 `AgentChatResponse` 中的 RouterResult、Plan、Validation、ConfirmationCard、Execution dry-run 和 Entry Trace。

# 2. 为什么现在做前端工作台

6.1 到 6.6.2 已经完成了后端入口链路，但工程价值仍然藏在测试、脚本和 JSON 里。

最小前端工作台的价值，是让用户和面试官直接看到：一句自然语言输入进入系统后，如何被理解成意图，如何被拆成任务步骤，为什么需要补参数、确认或阻断，以及为什么当前只做 dry-run。

# 3. 页面不是完整产品 UI

本页面不是完整 Agent Chat 产品，也不是发布后台。

它只是一张入口链路预览页，用来展示受控 Agent 工作台的核心协议。真实业务执行、正式确认流、草稿生成、竞品报告生成和外部平台动作，都不在本阶段接入。

# 4. 页面串联了哪些内容

页面展示链路：

```text
用户自由输入
-> RouterResult
-> Plan
-> Param / Plan Validation
-> ConfirmationCard
-> Execution dry-run
-> Entry Trace
```

前端新增了：

- `frontend/src/types/agentChat.ts`
- `frontend/src/api/agentChat.ts`
- `frontend/src/mock/agentChatDemo.ts`
- `frontend/src/views/AgentWorkbench.vue`

同时在 `frontend/src/router/index.ts` 增加 `/agent/workbench`，在侧边栏增加“Agent 工作台”入口。

# 5. API 调用方式

页面通过现有 `apiClient` 调用：

```text
POST /agent/chat/preview
```

请求体是 `AgentChatRequest`，响应体是 `AgentChatResponse`。前端不直接调用 OpenAI、Qwen、DeepSeek SDK，也不保存 API Key。

# 6. 示例输入和本地 Demo 数据

页面提供四个示例输入：

- 新选题
- 这个不行
- 标题太 AI
- 自动发布

这些按钮只填充输入框，点击“发送预览”时才会请求后端接口。

页面还提供“加载本地 Demo 数据”按钮。它会展示本地 fixture，并在页面上明确提示“当前展示本地演示数据，未调用接口”，不会把 Demo 数据伪装成真实接口结果。

# 7. ConfirmationCard 如何展示

当后端返回 `confirmation_card` 时，页面会展示卡片标题、说明、风险标记和参数预览。

本阶段不会提供真实执行入口。卡片底部按钮始终 disabled，固定提示：

```text
真实执行将在后续阶段接入
```

即使后端返回 `can_execute=true`，前端也不会提供真实执行按钮。

# 8. Execution dry-run 如何展示

页面读取 `response.metadata.execution`，展示：

- `mode`
- `status`
- `can_execute`
- `message`

当前阶段期望 `mode` 始终为 `DRY_RUN`。

# 9. Entry Trace 如何展示

页面读取 `response.metadata.entry_trace.events`，用时间线展示入口链路事件。

这能让演示者看到输入、Router、Planner、Validator、ConfirmationCard、Orchestrator 和 Response 的完整流转。

# 10. 本阶段没有做什么

本阶段没有接真实业务 service。

本阶段没有调用旧 workflow。

本阶段没有新增数据库表或 migration。

本阶段没有实现真实执行按钮。

本阶段没有发布、评论、删除或修改外部账号。

本阶段没有在前端调用 OpenAI / Qwen / DeepSeek SDK。

# 11. 下一步建议

下一步可以做两件事：

- 给 `/agent/chat/preview` 增加更稳定的前端错误态和后端配置提示。
- 做正式 ConfirmationCard 交互协议，但仍然先保持人工确认和 dry-run 边界，再接入真实 handler。
