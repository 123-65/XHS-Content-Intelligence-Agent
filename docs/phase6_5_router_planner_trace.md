# 1. 本阶段目标

第 6.5 阶段补 Agent 产品入口层 Trace。

它记录用户输入如何被 Router 理解、Planner 如何规划、Validator 为什么放行/追问/确认/阻断，以及最终前端为什么看到某张卡片。

Trace 不是为了炫技，而是为了以后排查：为什么 Agent 没有执行？为什么追问？为什么要求确认？为什么阻断？为什么 Router 识别错了？为什么 Planner 规划了某个步骤？

# 2. Router / Planner Trace 在 Agent 产品入口层的位置

入口层 Trace 记录的是执行前链路：

```text
AgentChatRequest / AgentInput
→ Router Prompt 摘要
→ RouterResult
→ Router Validation
→ Planner Prompt 摘要
→ Plan
→ ParamValidationResult
→ PlanValidationResult
→ ConfirmationCard
→ AgentChatResponse
```

它不记录真实工具调用，因为本阶段没有 Executor。

# 3. 它和第 1 阶段 Agent Trace 的关系

第 1 阶段的 Agent Trace 是执行层行车记录仪，围绕 `AgentRun / AgentStep` 记录 workflow、tool、input/output、fallback、error_code、latency_ms。

第 6.5 是入口层行车记录仪，围绕用户输入、路由、规划、校验和确认卡片记录“为什么还不能执行”。

两者是衔接关系：入口层 Trace 解释执行前决策，执行层 Trace 解释真正调用 service/workflow 之后发生了什么。

# 4. 为什么入口层也需要 Trace

没有入口层 Trace 时，开发者只能看到“没执行”或“需要确认”，但不知道原因。

用户说“这个不行”时，系统可能因为目标不明确而追问；也可能已经知道目标是草稿标题，可以规划 refine；也可能发现需要写候选记忆，所以要求确认。

入口层 Trace 要把这些判断过程记录下来。

# 5. 一次用户输入应该记录哪些节点

一次入口请求建议记录：

- `INPUT_RECEIVED`：用户输入摘要和附件元信息；
- `ROUTER_PROMPT_BUILT`：Router Prompt 长度和上下文字段；
- `ROUTER_RESULT_PARSED`：LLM 输出是否解析成 RouterResult；
- `ROUTER_VALIDATED`：RouterResult 经过 Validator 后的风险和缺参；
- `PLANNER_PROMPT_BUILT`：Planner Prompt 长度和上下文字段；
- `PLAN_PARSED`：LLM 输出是否解析成 Plan；
- `PLAN_REGISTRY_APPLIED`：Action Registry 约束后的计划；
- `PARAM_VALIDATED`：参数缺失、类型和来源问题；
- `PLAN_VALIDATED`：计划是否可执行、需确认或阻断；
- `CONFIRMATION_CARD_BUILT`：前端卡片类型；
- `RESPONSE_BUILT`：最终入口响应状态；
- `FAILED`：JSON 解析、Schema 校验或 LLM 调用失败。

# 6. Router Trace 记录什么

Router Trace 记录：

- 输入类型；
- Router Prompt 摘要；
- 识别出的 intent；
- confidence；
- target 类型和是否存在 target_id；
- missing_params；
- risk_flags；
- requires_clarification；
- requires_confirmation；
- can_execute；
- error_code / warning。

它不记录完整 Prompt，不记录完整外部评论或截图内容。

# 7. Planner Trace 记录什么

Planner Trace 记录：

- Planner Prompt 摘要；
- Plan steps 数量；
- 每一步 action；
- 每一步 allowed_effect；
- missing_params；
- risk_flags；
- confirmation_requirement；
- blocked_reason；
- Registry 约束后的计划状态；
- validate_plan_result 后的最终可执行状态。

Planner Trace 只记录计划，不记录真实业务结果。

# 8. Validator Trace 记录什么

Validator Trace 记录：

- 参数校验是否通过；
- 缺少哪些参数；
- 哪些参数类型不对；
- 哪些 ID 来源不可信；
- 是否存在 `TARGET_EXISTENCE_UNCHECKED`；
- 是否触发 `LOCAL_WRITE` 确认；
- 是否触发 `EXTERNAL_WRITE / DESTRUCTIVE` 阻断。

这能回答“系统为什么说不能继续”。

# 9. ConfirmationCard Trace 记录什么

ConfirmationCard Trace 记录：

- 是否生成卡片；
- 卡片标题；
- 卡片 action_type；
- requires_confirmation；
- confirmation_requirement；
- params_preview 的字段名；
- 风险标记。

它不记录完整大文本，只记录前端展示所需的轻量摘要。

# 10. 为什么不能记录完整 Prompt 和敏感信息

Prompt 可能包含用户原文、上下文摘要、附件信息和模型策略。完整记录会带来隐私和安全风险。

Trace 必须脱敏：

- `sk-` 开头 API Key；
- Bearer token；
- `api_key`；
- `access_token`；
- `refresh_token`；
- `authorization`；
- `password`；
- `secret`。

Trace 可以记录 prompt 长度、字段组成、附件元信息，但不要默认记录完整 Prompt、图片原始内容或大段外部评论。

# 11. 为什么本阶段先不落库 / 或如何复用已有 Trace

现有 Agent Trace 已经服务于执行层 `AgentRun / AgentStep`，需要数据库和 workflow/tool 概念。

入口层 Trace 现在还没有 AgentChatService、Conversation State 和 Executor。如果本阶段强行落库，会提前绑定还没稳定的产品入口结构。

因此 6.5 先做 `AgentEntryTrace`、`AgentEntryTraceEvent` 和 `AgentEntryTraceRecorder`，以内存 payload 组织事件，并提供 `to_agent_trace_payload()`，后续可以接到已有 Agent Trace 或新增入口层持久化。

# 12. 典型案例：用户说“这个不行”时 Trace 如何记录

如果用户说“这个不行”，且当前没有 target：

```text
INPUT_RECEIVED：记录用户输入摘要
ROUTER_RESULT_PARSED：intent=REFINE_OR_REJECT_RESULT
ROUTER_VALIDATED：risk_flags=TARGET_AMBIGUOUS，missing_params=target
PLAN_VALIDATED：steps=[ASK_CLARIFICATION]
CONFIRMATION_CARD_BUILT：title=需要补充信息
RESPONSE_BUILT：status=NEED_CLARIFICATION
```

Trace 会说明系统不是不工作，而是不知道“这个”指哪一个对象。

# 13. 典型案例：用户要求自动发布时 Trace 如何记录

如果用户说“直接帮我发布到小红书”：

```text
ROUTER_VALIDATED：识别外部写入风险
PLAN_REGISTRY_APPLIED：发现当前阶段没有外部发布能力
PLAN_VALIDATED：confirmation_requirement=BLOCKED
CONFIRMATION_CARD_BUILT：title=当前无法执行
RESPONSE_BUILT：status=BLOCKED
```

Trace 会说明阻断原因是外部写入能力越界，而不是模型失败。

# 14. 当前没有做 Executor 的原因

Executor 会调用真实 service/workflow，可能生成草稿、查询竞品、写入记忆或触发业务动作。

6.5 的目标只是把入口层决策过程记录清楚，不把 Trace 写成执行链路。只有当 Router、Planner、Validator、Trace 都稳定后，才能进入 6.6 的受控执行编排。

# 15. 第 6.6 如何继续做 Execution Orchestrator

第 6.6 可以开始设计 Execution Orchestrator。

建议原则：

- 只接收 `validate_plan_result()` 后可执行的 Plan；
- 仍然检查 confirmation_requirement；
- 根据 Action Registry 映射到已有 service/workflow；
- 每一步执行都接入第 1 阶段 Agent Trace；
- 入口层 Trace 和执行层 Trace 通过 trace_id / agent_run_id 关联；
- 高风险动作仍然阻断或要求确认。

6.6 才开始考虑“通过校验的 Plan 怎么受控调用已有 service/workflow”。
