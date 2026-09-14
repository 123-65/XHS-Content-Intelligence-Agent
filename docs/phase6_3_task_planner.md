# 1. 本阶段目标

第 6.3 阶段只做 Task Planner。

目标是把已经校验过的 `AgentInput + RouterResult` 转换成结构化 `Plan`。Planner 回答“为了完成用户目标，需要哪些步骤、每一步是什么动作、需要哪些参数、依赖什么、输出什么、风险和确认要求是什么”。

本阶段不做 Executor，不调用业务 service / workflow，不查数据库，不写数据库，不生成真实草稿，不生成真实竞品报告，不写 StrategyMemory。

# 2. Task Planner 在 Agent 产品入口层的位置

Task Planner 位于 Router 之后、Executor 之前：

```text
AgentInput
+ RouterResult
→ Planner Prompt
→ LLMClient / Provider
→ JSON 解析
→ Plan Schema 校验
→ Action Registry 约束
→ validate_plan_result()
→ 安全 Plan
```

它只产出计划，不执行计划。

# 3. Router 和 Planner 的区别

Router 负责识别用户想做什么。

例如用户说“这个标题太普通”，Router 判断它是 `REFINE_OR_REJECT_RESULT`，目标可能是 `DRAFT`，反馈动作是 `REFINE`，偏好方向是“标题更有辨识度”。

Planner 负责把目标拆成步骤。

例如同样的输入，Planner 可以规划 `REFINE_DRAFT → CREATE_CANDIDATE_MEMORY`，但不会真的修改草稿，也不会真的写入长期记忆。

# 4. Planner 输入是什么

Planner 输入包括：

- `AgentInput`：原始用户输入、账号、当前目标、附件元信息；
- `RouterResult`：经过 `validate_router_result()` 后的意图、参数、目标和风险；
- `Action Registry` 摘要：每个 Action 的 required params、allowed effect、确认要求和风险；
- `Intent → Action` 映射：不同意图常见的计划动作序列；
- 当前能力边界：哪些动作允许规划，哪些动作必须阻断。

如果 RouterResult 已经不可继续，例如低置信、缺参数、目标歧义或需要澄清，Planner 不能强行继续生成执行链路，只能规划 `ASK_CLARIFICATION`。

# 5. Planner 输出 Plan 是什么

`Plan` 是执行前的结构化计划。

它包含：

- `intent`：计划对应的用户意图；
- `steps`：计划步骤；
- `required_params / missing_params`：计划整体参数要求和缺失参数；
- `risk_flags`：风险标记；
- `confirmation_requirement`：是否无需确认、需要澄清、需要确认或被阻断；
- `can_execute`：是否可以进入后续执行阶段；
- `summary_for_user / blocked_reason / next_action`：给前端确认卡片或阻断卡片使用。

`PlanStep` 包含 `action / description / inputs / required_params / input_params / depends_on / expected_output / allowed_effect / risk_flags / requires_confirmation / can_execute`。

# 6. 为什么 Planner 不能执行业务

Planner 是“想清楚怎么做”，不是“真的去做”。

如果 Planner 直接执行业务，会出现：

- 缺 `account_id` 仍然查数据；
- 缺 `draft_id` 仍然改草稿；
- 把用户一句负反馈直接写入长期 Memory；
- 把自动发布、自动评论、删除内容当成可执行任务；
- 跳过人工确认；
- 把评论或截图里的内容当成系统指令。

所以 Planner 只输出 Plan，Executor 以后只能执行通过 Validator 的 Plan。

# 7. 为什么 Planner 必须受 Action Registry 约束

LLM 可能会写出不存在的 action，或者把高风险动作写成低风险动作。

Action Registry 是当前系统的能力边界。每个 Action 声明：

- 必需参数；
- 可选参数；
- 影响范围；
- 默认确认要求；
- 当前阶段是否支持；
- 风险标记。

Planner 输出后必须用 Registry 覆盖 `allowed_effect`，补齐 `required_params`，检查缺失参数，并处理本地写入、外部写入和破坏性动作。

# 8. Intent 到 Plan 的典型映射

`GENERATE_CONTENT_OPPORTUNITY` 通常规划：

```text
QUERY_ACCOUNT_PROFILE
QUERY_COMPETITOR_EVIDENCE
QUERY_COMMENT_INSIGHT
QUERY_STRATEGY_MEMORY
GENERATE_CONTENT_OPPORTUNITY
```

`GENERATE_DRAFT` 通常规划：

```text
QUERY_ACCOUNT_PROFILE
QUERY_STRATEGY_MEMORY
QUERY_COMPETITOR_EVIDENCE
QUERY_COMMENT_INSIGHT
CREATE_CONTENT_EXPERIMENT
GENERATE_DRAFT
REVIEW_DRAFT
```

用户说“我想写一篇 27 届双非本科做 Agent 求职的帖子”时，Router 只判断这是 `GENERATE_CONTENT_OPPORTUNITY` 或 `GENERATE_DRAFT`。Planner 才负责拆成：查账号画像 → 查竞品证据 → 查评论洞察 → 查策略记忆 → 生成内容机会 → 生成实验 → 生成草稿 → 审核。

但 Planner 本轮不会真的查，也不会真的生成，只是产出 Plan。

`REFINE_OR_REJECT_RESULT` 且目标是 Draft 时，通常规划：

```text
REFINE_DRAFT
CREATE_CANDIDATE_MEMORY
```

其中 `CREATE_CANDIDATE_MEMORY` 是本地写入，需要用户确认。

`ANALYZE_COMPETITOR` 通常规划：

```text
QUERY_COMPETITOR_EVIDENCE
ANALYZE_COMPETITOR
```

`ANALYZE_PUBLISHED_PERFORMANCE` 通常规划：

```text
QUERY_ANALYTICS
CREATE_CANDIDATE_MEMORY
```

`QUERY_STATUS / CONFIRM_ACTION / CANCEL_ACTION` 当前只规划 `NOOP`。真正确认执行属于后续 Conversation State + Executor。

# 9. 缺参数 / 目标歧义时如何规划 ASK_CLARIFICATION

如果 RouterResult 包含 `missing_params`，Planner 应规划 `ASK_CLARIFICATION`，而不是继续生成草稿或分析竞品。

如果用户说“这个不行”，但没有当前目标上下文，Router 会标记 `TARGET_AMBIGUOUS`。Planner 此时应该输出：

```text
steps = [ASK_CLARIFICATION]
confirmation_requirement = CLARIFICATION_REQUIRED
can_execute = false
```

这样系统会先追问“你说的是标题、草稿、选题还是计划”，而不是擅自修改错误对象。

# 10. 本地生成、本地写入、外部写入、破坏性动作如何处理

`READ_ONLY` 和 `LOCAL_GENERATION` 是低风险动作，但仍然需要参数完整。

`LOCAL_WRITE` 代表本地写入，例如创建候选记忆或本地分析报告。它不会写外部平台，但会影响系统后续状态，所以默认需要 `USER_CONFIRM_REQUIRED`。

`EXTERNAL_WRITE` 代表外部写入，例如自动发布小红书、自动回复评论、修改外部账号。当前阶段必须 `BLOCKED`。

`DESTRUCTIVE` 代表删除或破坏性修改，当前阶段必须 `BLOCKED`。

# 11. LLM 输出为什么必须经过 JSON 解析、Schema 校验、Registry 校验和 Validator

Planner LLM 输出有四层校验。

第一层是 JSON 解析：输出不是合法 JSON，就返回安全 Plan。

第二层是 Pydantic Schema 校验：输出不符合 `Plan`，就返回安全 Plan。

第三层是 Action Registry 约束：覆盖 `allowed_effect`，补齐 `required_params`，识别缺参、本地写入确认和高风险动作。

第四层是 `validate_plan_result()`：统一检查空步骤、缺参数、需确认、外部写入、破坏性动作和 unsupported action。

这四层共同保证 Planner 的输出只是受控计划，不会变成隐式执行命令。

# 12. 当前没有做 Executor 的原因

Executor 会调用真实 service / workflow。只要 Executor 接入，错误计划就可能变成真实业务动作。

当前阶段还没有完成 Param Validator + Plan Validator 的完整工程化，也没有前端确认卡片和 Conversation State 闭环，因此不能直接进入执行。

# 13. 第 6.4 如何继续做 Param Validator + Plan Validator

第 6.4 应该把 Validator 从雏形升级为更完整的入口层安全网。

建议方向：

- 基于 Action Registry 校验每个 step 的必需参数；
- 区分缺参数、类型错误、目标不存在、能力不支持；
- 输出结构化 `ValidationIssue`；
- 统一 `CLARIFICATION_REQUIRED / USER_CONFIRM_REQUIRED / BLOCKED`；
- 为前端 ConfirmationCard 生成稳定原因；
- 为后续 Executor 提供明确的可执行门槛。

6.4 仍然不应该直接调用业务 service，Executor 应放在 Validator 之后。
