# 1. 本阶段目标

第 6.6.0 阶段只做 Controlled Execution Orchestrator Skeleton。

目标是建立受控执行编排框架：通过校验的 Plan 进入 Orchestrator，由 Action Handler 白名单决定哪些 step 可以 dry-run 或真实执行，并把执行结果写回入口层 Trace。

本轮不直接接全部旧业务 service，不生成真实草稿，不查数据库，不写 StrategyMemory。

# 2. Execution Orchestrator 在 Agent 产品入口层的位置

入口层链路变成：

```text
用户输入
→ Router
→ Planner
→ Validator
→ ConfirmationCard
→ Execution Orchestrator
→ StepExecutionResult / PlanExecutionResult
→ Trace
→ AgentChatResponse
```

用户说“生成一篇草稿”以后，Router 只识别意图，Planner 只生成 Plan，Validator 判断能不能执行，Orchestrator 只在 Plan 完全通过校验且无需确认时执行。

# 3. 为什么 Executor 不能猜意图、不能改 Plan

Executor 的职责不是理解用户，也不是临时补计划。

如果 Executor 自己猜意图或改 Plan，就会绕过 Router、Planner 和 Validator 的安全边界。例如缺 `account_id` 时继续执行、把用户一句“这个不行”直接改草稿、或者跳过确认写入候选记忆。

所以 Executor 只能执行已经通过校验的 Plan，不能补意图，不能改步骤，不能跳过确认。

# 4. 为什么本轮先做 Orchestrator Skeleton，不直接接全部业务 service

当前旧业务 service / workflow 的入参、返回值、数据来源还需要逐步审计。

如果 6.6 直接接所有业务能力，很容易出现：

- 绕过 Validator；
- 把 mock 结果当真实业务结果；
- 跳过前端确认；
- 把外部写入或破坏性动作误接为可执行；
- Trace 无法解释实际调用链。

因此本轮先证明受控执行框架是安全的，再逐步接入只读和本地生成类 action。

# 5. ExecutionMode / ExecutionStatus 说明

`ExecutionMode`：

```text
DRY_RUN：只验证会执行什么，不调用 handler
REAL：允许调用已注册、已确认、已通过校验的 handler
```

`ExecutionStatus`：

```text
NOT_STARTED
SKIPPED
SUCCESS
FAILED
BLOCKED
WAITING_CONFIRMATION
NEED_CLARIFICATION
```

本轮默认优先使用 `DRY_RUN`，因为它不会产生业务副作用。

# 6. Action Handler Registry 是什么

`ActionHandlerRegistry` 是执行白名单。

每个 Action 只有注册了 handler，才可能进入 REAL 执行。默认只注册：

```text
NOOP
ASK_CLARIFICATION
```

其他 action 可以在测试里用 Fake Handler 验证框架，但生产默认不接真实业务 service。

# 7. 为什么只有白名单 handler 才能执行

Planner 输出的 Action 只是计划，不代表系统真的具备执行能力。

白名单 handler 的作用是防止 LLM 或 Planner 规划出一个看似合理但当前没有适配器的动作。未注册 handler 的 Action 不能假装成功，必须 BLOCKED。

# 8. dry-run 是什么，为什么重要

dry-run 用于回答“如果真实执行，会执行哪些 step”。

DRY_RUN 模式下：

- 不调用 handler；
- 不调用 service/workflow；
- 不产生业务 output；
- 每个 step 只返回 SKIPPED 或预演状态；
- 仍然经过执行前硬性检查。

这让前端和开发者可以先看到执行计划，而不会产生副作用。

# 9. Plan 执行前有哪些硬性检查

Orchestrator 执行前必须检查：

- `plan.confirmation_requirement == NONE`；
- `plan.can_execute == true`；
- `plan_validation.valid == true`；
- `plan_validation.confirmation_requirement == NONE`；
- 所有 `step.can_execute == true`；
- 所有 `step.requires_confirmation == false`；
- 所有 `step.allowed_effect` 不是 `EXTERNAL_WRITE / DESTRUCTIVE`；
- 所有 `step.action` 在 Action Registry 支持范围内；
- 所有 `step.action` 有注册 handler；
- `depends_on` 引用的 step 必须存在。

任何一项不满足，都不能执行任何 step。

# 10. confirmation_requirement 如何影响执行

`USER_CONFIRM_REQUIRED`：返回 `WAITING_CONFIRMATION`，等待用户确认。

`CLARIFICATION_REQUIRED`：返回 `NEED_CLARIFICATION`，需要补充信息。

`BLOCKED`：返回 `BLOCKED`，当前阶段不可执行。

只有 `NONE` 才可能继续执行。

# 11. allowed_effect 如何影响执行

`READ_ONLY / LOCAL_GENERATION` 可以在注册 handler 后进入执行。

`LOCAL_WRITE` 需要在 Validator 阶段先确认，未确认不能执行。

`EXTERNAL_WRITE / DESTRUCTIVE` 当前阶段必须阻断，不能通过 handler 注册绕过。

# 12. depends_on 如何处理

本轮不做复杂 DAG 引擎，只做顺序遍历：

```text
按 step_order 升序执行
检查 depends_on 是否存在
检查依赖 step 是否 SUCCESS
依赖失败则当前 step SKIPPED
```

如果 `depends_on` 引用不存在的 step，整体 BLOCKED。

# 13. 执行结果如何进入 Trace

Orchestrator 记录：

- `EXECUTION_STARTED`；
- `STEP_EXECUTION_STARTED`；
- `STEP_EXECUTION_FINISHED`；
- `EXECUTION_FINISHED`；
- `EXECUTION_BLOCKED`；
- `FAILED`。

Trace 只记录轻量结果、状态、action、风险和错误码，不记录敏感信息或大段 output。

# 14. AgentChatResponse 如何衔接执行结果

本轮新增 `build_response_from_execution()`。

映射规则：

- `SUCCESS` → `READY_TO_EXECUTE`；
- `WAITING_CONFIRMATION` → `WAITING_CONFIRMATION`；
- `NEED_CLARIFICATION` → `NEED_CLARIFICATION`；
- `BLOCKED` → `BLOCKED`；
- `FAILED` → `FAILED`。

当前 `AgentResponseStatus` 没有 `EXECUTED`，所以本轮不新增状态。后续如需要可以再扩展。

# 15. 当前仍未接入真实业务 service 的原因

本阶段目标是安全骨架，不是业务执行覆盖率。

真实业务接入需要先确认每个 service 的输入、输出、错误码、Trace、幂等性、权限和数据来源。否则很容易绕过前面几阶段建立的 Router / Planner / Validator / Trace 防线。

# 16. 第 6.6.1 如何逐步接入只读 / 本地生成类业务 action

6.6.1 可以从低风险 action 开始：

- `QUERY_ACCOUNT_PROFILE`；
- `QUERY_STRATEGY_MEMORY`；
- `QUERY_COMPETITOR_EVIDENCE`；
- `QUERY_COMMENT_INSIGHT`；
- `GENERATE_CONTENT_OPPORTUNITY`；
- `REVIEW_DRAFT`。

接入原则：

- 每个 action 单独 adapter；
- 每个 adapter 明确输入输出；
- 每个 adapter 走 Orchestrator 白名单；
- 每个 adapter 输出轻量可追踪结果；
- 不接外部写入；
- 不接破坏性动作；
- 不跳过 ConfirmationCard。
