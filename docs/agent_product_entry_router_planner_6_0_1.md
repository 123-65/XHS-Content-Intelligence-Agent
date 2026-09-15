# 第 6.0.1 Agent 产品入口与 Router / Planner 架构修正

## 1. 为什么需要架构修正

当前项目不是废了。

前面第 1 到第 5 阶段已经做出了很重要的后端工程底座，包括 Agent Trace、Mock / Seed 治理、Provider 状态码、LLM Schema、Context Engineering、ContextSnapshot 指标统计等能力。

但从产品形态看，它现在更像一个 Agent 后端工程底座，还不是完整用户可用的 Agent 产品。

真正的 Agent 产品不能只靠后端服务和固定接口拼起来。用户需要一个可以自然表达想法、反馈、否定、补充材料、要求修改和确认动作的入口层。系统也需要理解用户输入、识别意图、规划任务、校验参数、等待确认、编排执行、记录会话状态，并把用户反馈逐步沉淀成偏好或策略。

因此，第 6 阶段需要从“后端能力建设”转向“Agent 产品入口层建设”。这不是推翻已有系统，而是在已有底座上补齐用户可用闭环。

## 2. 当前已有能力

当前项目已经具备以下基础能力：

- Agent Trace
- Mock / Seed 治理
- Provider 状态码
- 真实 LLM 配置检查
- LLM 结构化输出 Schema
- `content_draft_v2`
- Context Slot
- Token Budget
- `COMPETITOR_EVIDENCE` Top-K
- `STRATEGY_MEMORY` 筛选
- `COMMENT_INSIGHT` 摘要
- ContextSnapshot 指标统计

这些能力说明项目已经有了比较完整的后端工程基础，尤其是上下文治理、结构化输出、证据筛选、策略记忆和指标追踪方向已经具备可扩展空间。

但这些能力目前主要分布在后端内部链路中，还没有被组织成一个面向用户输入、确认、反馈和多轮迭代的 Agent 产品入口。

## 3. 当前缺失能力

当前项目还缺少完整的 Agent 产品入口层，主要包括：

- 用户自由输入框
- Input Understanding
- Intent Router
- Task Planner
- Param Validator
- Plan Validator
- Human Confirmation
- Execution Orchestrator
- Conversation State
- Feedback Handler
- 用户偏好候选记忆
- 前端确认卡片

这些缺失能力决定了用户现在还不能像使用一个真正的 Agent 工作台那样连续表达需求、修正结果、确认动作和推动工作流。

## 4. 为什么固定工具按钮不够

固定工具按钮适合触发明确动作，例如生成草稿、查看竞品报告、刷新状态、打开某个详情页。

但用户真实输入不会总是这么规整。用户经常会说：

- 我不喜欢这个主题
- 这个不行
- 换一个
- 这个标题太普通
- 我想写个有意思的帖子
- 参考这张图
- 昨天那篇数据不好
- 不想这么功利

这些输入不是单个按钮能完整表达的。

它们可能代表否定当前结果、要求换方向、修改语气、引用历史内容、追加图片输入、表达价值观偏好、反馈发布效果，或者要求重新规划内容路径。

如果只靠固定按钮，系统只能覆盖少量预设动作，无法理解用户真实的运营语境，也无法形成连续的产品闭环。

所以，固定按钮可以保留，但必须和自由输入框、Router、Planner、确认卡片一起组成受控 Agent 工作台。

## 5. 为什么也不能完全自由 Agent

虽然需要自由输入，但也不能把系统做成完全自由 Agent。

Router / Planner 不能直接执行业务，否则可能出现严重问题：

- 编造 `account_id` / `report_id` / `draft_id`
- 跳过人工确认
- 缺数据也继续生成
- 把评论或截图内容当系统指令
- 把 mock 数据当真实数据

小红书运营链路里有大量不可信输入，例如评论、截图、竞品内容、用户粘贴的外部材料。它们可以作为分析对象，但不能作为系统指令直接驱动执行。

此外，当前项目仍然以手动录入、只读采集和未来 MCP 预留为主，不能默认具备任意读写小红书笔记、自动发布、自动评论或自动修改内容的能力。

因此，第 6 阶段的 Agent 必须是受控 Agent：允许用户自由表达，但所有执行都要经过结构化 Router、Planner、Validator 和必要的人工确认。

## 6. 新产品形态

第 6 阶段建议的新产品形态是：

自由输入框 + 固定工具按钮 + 动作确认卡片的受控 Agent 工作台。

其中：

- 自由输入框用于承接用户真实表达、反馈、补充想法、图片说明、复盘意见和多轮修改；
- 固定工具按钮用于高频、明确、低歧义的快捷动作；
- 动作确认卡片用于展示系统理解、计划步骤、风险提示、缺失参数和等待用户确认的动作；
- 后端 Router / Planner / Validator / Executor 负责把用户输入转成可控计划并安全执行；
- Trace / ContextSnapshot / Memory 负责记录过程、评估质量和沉淀策略。

这个形态既不是传统表单工具，也不是完全自由的黑盒 Agent，而是适合内容运营工作流的受控智能工作台。

## 7. 新 Agent 流程

新的 Agent 流程应该是：

用户输入
→ Input Understanding
→ Intent Router
→ Task Planner
→ Param Validator
→ Plan Validator
→ Human Confirmation
→ Execution Orchestrator
→ Service / Workflow
→ Trace / ContextSnapshot
→ Memory
→ 用户反馈继续迭代

这个流程的关键点是：

- 用户输入先被理解和结构化，而不是直接执行；
- Router 识别用户想做什么；
- Planner 把目标拆成步骤；
- Param Validator 检查参数是否完整、合法、可信；
- Plan Validator 检查计划风险、权限、是否需要确认；
- Human Confirmation 处理需要用户确认的动作；
- Execution Orchestrator 只执行通过校验的计划；
- Service / Workflow 复用已有后端能力；
- Trace / ContextSnapshot 记录链路和指标；
- Memory 只沉淀经过确认或复盘验证的偏好和策略；
- 用户反馈会重新进入 Router / Planner，形成多轮迭代。

## 8. Router、Planner、Validator、Executor 分工

Router：识别用户想做什么。

Router 应该识别用户输入属于生成、分析、审核、复盘、拒绝、修改、补充材料、确认动作还是查询状态。Router 不应该调用业务服务，也不应该编造缺失 ID。

Planner：把目标拆成步骤。

Planner 应该基于 Router 输出生成结构化计划，明确每一步的 action、输入依赖、输出、风险、是否只读、是否需要执行、是否需要确认。Planner 不直接执行业务。

Validator：检查参数、权限、风险、是否需要确认。

Validator 包括 Param Validator 和 Plan Validator。它应该检查必填参数、ID 是否存在、输入来源是否可信、是否使用 mock 数据、是否涉及外部写入、是否需要人工确认，以及当前阶段是否允许执行该 action。

Executor：只执行通过校验的计划，调用已有 service / workflow。

Executor 不负责猜测用户意图，也不负责临时改计划。它只接收已通过 Validator 的计划，并调用已有 service / workflow 完成执行。

Trace：记录输入、路由、计划、执行结果。

Trace 应该记录用户原始输入摘要、Router 结果、Planner 计划、Validator 结论、确认状态、Executor 结果和错误信息，为调试、复盘、指标统计和后续策略沉淀提供依据。

Memory：沉淀用户偏好、策略、复盘结论。

Memory 不应该直接相信单次用户负反馈。用户偏好和策略应先进入候选状态，经过确认、重复出现或复盘验证后，再沉淀为长期记忆。

## 9. 用户反馈怎么处理

用户说“这个不行 / 我不喜欢这个主题 / 换一个 / 太 AI / 太普通”时，Router 应识别为 `REFINE_OR_REJECT_RESULT`。

系统需要识别：

- `feedback_action`
- `feedback_polarity`
- `target_type`
- `target_id`
- `reject_reason`
- `preferred_direction`

例如：

- “这个不行”可能表示拒绝当前草稿、当前标题、当前选题或当前计划；
- “太 AI”可能表示语气不自然、表达套路化、缺少个人经验；
- “太普通”可能表示标题缺少冲突、角度缺少新意、选题竞争过高；
- “换一个”可能表示要求替换当前候选结果，而不是重新开始整个工作流。

如果系统无法判断“这个”指什么，就必须追问，而不是擅自选择目标。

用户负反馈不要立刻写长期 Memory。更合适的方式是先写 Candidate Preference / Candidate Strategy Memory，例如：

- 候选偏好：用户可能不喜欢太功利的表达；
- 候选策略：该账号可能需要更生活化、更经验感的内容角度；
- 候选拒绝原因：当前标题被认为太普通。

只有当用户明确确认、类似反馈重复出现，或后续复盘证明有效时，才应该沉淀为长期 Memory。

## 10. 用户自己有新想法怎么处理

当用户输入一个新选题或想法时，Router 应识别为 `GENERATE_CONTENT_OPPORTUNITY` 或 `GENERATE_DRAFT`。

例如：

- “我想写个有意思的帖子”
- “能不能做一个护肤新手避坑主题”
- “这周想围绕秋冬换季敏感肌写点内容”
- “我想把这个用户评论发展成一篇笔记”

Planner 需要判断这个输入处在内容工作流的哪个阶段：

- 如果只是一个模糊方向，应该先生成内容机会；
- 如果已经有清晰受众、角度和目标，可以生成实验；
- 如果实验已经明确，可以生成草稿；
- 草稿生成后还应该进入审核；
- 如果用户给的是历史表现反馈，则可能进入复盘和策略沉淀。

因此，用户新想法不应该一律直接变成草稿。Planner 应决定是否需要先生成实验、再生成草稿、再审核。

## 11. 图片 / 链接 / 文件输入怎么预留

第 6 阶段的输入类型应该支持：

- `TEXT`
- `IMAGE`
- `URL`
- `FILE`
- `MIXED`

图片输入需要先预留 `image_type`，例如：

- 小红书笔记截图；
- 评论区截图；
- 数据表现截图；
- 用户上传的参考图；
- 未分类图片。

本阶段不实现 OCR 或视觉模型，也不调用真实视觉能力。图片只作为输入类型和未来能力的 Schema 预留。

如果用户只发图片，没有文字说明，系统应该设置 `requires_confirmation=true` 或进入追问，因为当前阶段不能可靠判断图片意图。

链接和文件也应该先作为输入类型预留，不要默认具备任意抓取、解析或外部写入能力。

## 12. 第 6 阶段新路线

第 6 阶段建议调整为：

6.1 Router + Planner Schema

定义 RouterResult、Plan、PlanStep、ValidationResult、InputType、Intent、Action、RiskFlag、AllowedEffect、ConfirmationRequirement 等结构。先稳定契约，不接真实 LLM，不执行业务。

6.2 LLM Router

让 LLM 只负责把用户自然语言转成结构化 RouterResult。输出必须经过 Schema 校验，低置信度或缺参数时进入澄清。

6.3 Task Planner

基于 RouterResult 生成结构化 Plan。Planner 只规划，不调用 service / workflow，不直接生成业务结果。

6.4 Validator

实现 Param Validator 和 Plan Validator，检查参数完整性、ID 合法性、数据可信度、mock / seed 状态、风险动作、人工确认和当前能力边界。

6.5 Router / Planner Trace

记录用户输入摘要、Router 输出、Planner 输出、Validator 结果、缺失参数、风险标记和确认状态，为调试和复盘提供链路证据。

6.6 Execution Orchestrator

接入执行编排层，只执行通过 Validator 的计划，调用已有 service / workflow。优先支持只读和本地生成类动作，外部写入保持确认或阻断。

6.7 多轮反馈与 Conversation State

支持用户继续说“这个不行”“换一个”“太普通”“我不喜欢这个方向”。维护当前目标、当前结果、候选偏好、待确认计划和多轮上下文。

6.8 前端最小输入框 + 确认卡片

前端先实现最小自由输入框和动作确认卡片。固定按钮继续保留，但所有复杂意图都通过输入框、Router / Planner 和确认卡片形成闭环。

## 13. 结论

第 1 到第 5 阶段不是废掉，而是后端底座。

这些阶段已经完成了 Agent Trace、Mock / Seed 治理、Provider 状态码、真实 LLM 配置检查、LLM 结构化输出 Schema、Context Engineering、ContextSnapshot 指标统计等基础能力。

第 6 阶段开始补 Agent 产品入口层。

后续所有设计必须从“用户怎么使用”倒推：用户如何输入、如何表达不满意、如何补充材料、如何确认动作、如何继续迭代、如何把偏好沉淀为策略。

最终产品不应该只是一些后端接口，也不应该是不可控的自由 Agent，而应该是自由输入框 + 固定工具按钮 + 动作确认卡片组成的受控 Agent 工作台。
