# 1. 本阶段目标

第 6.4 阶段把 Validator 从雏形升级为可解释、可测试、可给前端确认卡片使用的工程化校验层。

LLM Router / Planner 只是提出“理解”和“计划”，不能直接决定能否执行。真正能不能执行，要看 Validator。Validator 要从参数、来源、风险、能力边界、确认要求几个角度做最后把关。

# 2. Validator 在 Agent 产品入口层的位置

Validator 位于 Router / Planner 之后、Executor 之前：

```text
AgentInput + RouterResult + Plan
→ ParamValidationResult
→ PlanValidationResult
→ ConfirmationCard / ClarificationCard / BlockedCard
→ 后续 Executor
```

本阶段仍然不接 Executor，不调用业务 service，不查数据库，不写数据库。

# 3. Param Validator 和 Plan Validator 的区别

Param Validator 关注参数：是否缺失、是否为空、类型是否合理、来源是否可信。

Plan Validator 关注计划：步骤是否为空、Action 是否受支持、`allowed_effect` 是否越界、是否需要确认、是否必须阻断。

两者结合后，前端才能知道应该展示澄清卡片、确认卡片、阻断卡片，还是可执行状态。

# 4. 为什么不能相信 LLM 自己说 can_execute=true

LLM 可能会把缺参数的计划标成 `can_execute=true`，也可能把本地写入、高风险动作或不支持能力误判为可执行。

因此 `can_execute` 只能由 Validator 重新计算。LLM 输出里的 `can_execute` 只是模型建议，不能作为执行依据。

# 5. 参数完整性怎么校验

6.4 新增 `ParamSpec` 和 `ACTION_PARAM_SPECS`。

每个 Action 都声明必填参数和可选参数。例如：

- `QUERY_ACCOUNT_PROFILE` 需要 `account_id`；
- `GENERATE_DRAFT` 需要 `account_id`，可选 `experiment_id / topic / angle / target_audience`；
- `REFINE_DRAFT` 需要 `account_id / feedback`，并且需要 `draft_id` 或 `draft_text`；
- `CREATE_CANDIDATE_MEMORY` 需要 `account_id / memory_content / source`。

`validate_action_params()` 校验单个动作，`validate_plan_params()` 汇总整个计划的缺参。

# 6. 参数类型怎么校验

6.4 新增 `ParamType`：

```text
STRING / INT / FLOAT / BOOL / ID / TEXT / URL / DATETIME / LIST / DICT / ANY
```

本阶段只做轻量类型校验。例如：

- `ID` 可以是 int 或非空字符串；
- `URL` 需要以 `http://` 或 `https://` 开头；
- `LIST` 必须是 list；
- `DICT` 必须是 dict；
- 空字符串视为缺参。

本阶段不做复杂格式校验，也不查业务表。

# 7. 参数来源怎么校验，为什么要防止 LLM 编造 ID

LLM 不能编造 `account_id / draft_id / report_id / experiment_id`。

`validate_param_sources()` 会检查敏感 ID 是否来自可信输入：

- `AgentInput.account_id`；
- `AgentInput.current_target_id`；
- `RouterResult.target_id`；
- `RouterResult.extracted_params`。

如果某个 `draft_id` 只出现在 `PlanStep.input_params` 中，而入口输入和 RouterResult 都没有提供，Validator 会标记 `PARAM_SOURCE_UNVERIFIED`。这表示 ID 可能是 LLM 自己编的，不能直接执行。

# 8. 为什么本阶段不查数据库，只标记 TARGET_EXISTENCE_UNCHECKED

6.4 是产品入口层 Validator，不是业务执行层。

它不连接数据库，不查询草稿、报告或实验是否真实存在。因此当某个 ID 来源可疑或需要后续确认时，只标记 `TARGET_EXISTENCE_UNCHECKED`。

真正的存在性检查应该放在后续 Executor 或业务 service 的执行前校验中。

# 9. allowed_effect 为什么必须以 Action Registry 为准

LLM 可能会把 `LOCAL_WRITE` 写成 `READ_ONLY`，也可能把不支持的外部写入描述成普通动作。

所以 `allowed_effect` 必须以 Action Registry 为准。Validator 会用 Registry 覆盖 LLM 自己填的影响范围，并重新计算风险和确认要求。

# 10. LOCAL_WRITE 为什么需要用户确认

`LOCAL_WRITE` 虽然不写外部平台，但会改变系统本地状态，例如生成本地分析报告或创建候选记忆。

特别是用户偏好和策略记忆，不能因为一句“这个不行”就直接长期沉淀。因此 `LOCAL_WRITE` 和 `CREATE_CANDIDATE_MEMORY` 默认需要 `USER_CONFIRM_REQUIRED`。

# 11. EXTERNAL_WRITE / DESTRUCTIVE 为什么必须阻断

`EXTERNAL_WRITE` 包括自动发布小红书、自动回复评论、修改外部账号等。

`DESTRUCTIVE` 包括删除内容或破坏性修改。

当前阶段没有外部写入能力，也没有破坏性动作执行能力。因此这两类动作必须 `BLOCKED`，不能通过确认绕过。

# 12. ConfirmationCard / ClarificationCard / BlockedCard 怎么生成

6.4 新增 `build_confirmation_card()`。

当计划可执行且无需确认时，返回 `None`。

当 `confirmation_requirement=CLARIFICATION_REQUIRED` 时，生成“需要补充信息”卡片，展示缺少哪些参数或需要回答什么。

当 `confirmation_requirement=USER_CONFIRM_REQUIRED` 时，生成“请确认执行计划”卡片，展示将要执行的步骤和写入动作。

当 `confirmation_requirement=BLOCKED` 时，生成“当前无法执行”卡片，展示阻断原因和风险。

本阶段只构造卡片数据，不接前端。

# 13. OpenAI / Qwen SDK 后续应该放在哪一层

后续真实接模型时，可以使用 OpenAI Python SDK、Qwen / 阿里云百炼 OpenAI-compatible SDK、DeepSeek 等兼容接口。

但 Router / Planner / Validator 不应该直接依赖具体厂商 SDK。

正确结构是：

```text
LLMUserInputRouter / LLMTaskPlanner
→ 统一 LLMClient 或 Provider Adapter
→ OpenAI SDK / Qwen SDK / DeepSeek SDK
```

6.4 不接 SDK，不调用真实模型。

# 14. 当前没有做 Executor 的原因

Executor 会调用真实 service / workflow。只要接入 Executor，错误计划就可能变成真实业务动作。

当前阶段只把执行前校验做扎实：参数、来源、能力边界、确认要求都要能解释、能测试、能展示给前端。Executor 应该在 Validator 和 Trace 更完整之后再接入。

# 15. 第 6.5 如何继续做 Router / Planner Trace

第 6.5 应该记录 Router / Planner / Validator 的关键过程：

- 原始用户输入摘要；
- RouterResult；
- Plan；
- ParamValidationResult；
- PlanValidationResult；
- ConfirmationCard；
- 风险标记和阻断原因；
- LLM 输出解析失败、Schema 失败和 Validator 失败原因。

Trace 的目标不是执行，而是让后续调试、前端展示和复盘都能知道“系统为什么这么判断”。
