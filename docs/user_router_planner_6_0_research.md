# 第 6.0 调研文档：User Intent Router + Task Planner

## 1. 本阶段要解决什么

第 6 阶段的核心目标不是直接增强某一个业务接口，也不是让系统立刻自动生成小红书文案，而是先补上用户意图理解、任务规划、执行前校验和后续可追踪的基础层。

当前项目已经有了内容洞察、竞品证据、上下文预算、策略记忆等能力。下一步如果直接把用户输入接到业务服务，会出现几个问题：

- 用户一句话里可能混合多个目标，例如“帮我看看这个截图能不能做成选题，再给三个草稿方向”；
- 同一个目标可能需要不同数据来源，例如手动录入、只读采集、历史策略记忆、未来 MCP；
- 小红书评论、截图、竞品文本都可能包含误导性内容，不能直接当成系统指令；
- 有些动作只是分析，有些动作会生成草稿，有些动作未来可能会写入外部平台，风险级别不同；
- 如果没有结构化计划和验证层，后续 Trace、人工确认、失败复盘都会很难补。

因此，第 6.0 的调研结论是：先设计 User Intent Router + Task Planner 的架构边界，再逐步接入 Validator、Trace 和 Executor。

## 2. 常见 Agent 系统拆分方式

别人做 Agent 系统一般不会把“理解用户、拆任务、调用工具、检查结果、记录上下文”全部塞进一个函数里，而是拆成几个角色：

- Router：识别用户到底想做什么，把自然语言请求路由到合适的任务类型；
- Planner：把任务拆成结构化步骤，明确输入、输出、依赖、风险和是否需要人工确认；
- Executor：根据已经验证过的计划调用工具、业务服务、数据库读写或外部接口；
- Validator：检查计划和执行请求是否合法、参数是否完整、风险是否可控、是否需要人工确认；
- Trace：记录用户请求、Router 输出、Planner 输出、Validator 结论、Executor 结果和错误信息；
- Memory：沉淀长期策略、历史偏好、有效模式、失败经验和可复用上下文。

这个拆分的关键价值是边界清楚：Router 不执行业务，Planner 不直接调工具，Executor 不自行猜测用户意图，Validator 不生成业务结果，Trace 不改变业务状态，Memory 不替代当前请求的真实输入。

## 3. Router、Planner、Executor 的边界

Router 负责识别用户想做什么。

它应该回答的是：

- 用户意图属于哪一类；
- 用户是否在请求分析、规划、生成、审核、复盘或执行；
- 请求里有哪些显式参数；
- 哪些参数缺失；
- 是否涉及图片、评论、竞品笔记、账号信息、历史策略记忆等输入；
- 是否可能触发高风险动作或需要人工确认。

Planner 负责拆步骤。

它应该回答的是：

- 这个任务需要哪些阶段；
- 每一步依赖哪些输入；
- 每一步预期产出什么结构化结果；
- 哪些步骤只能读取数据；
- 哪些步骤未来可能触发写入或外部动作；
- 哪些步骤必须经过 Validator 或人工确认。

Executor 才负责调用工具和业务服务。

Executor 不应该根据用户原话自由发挥，也不应该绕过 Planner 和 Validator。它只能执行已经通过校验的结构化计划，并且执行结果应该进入 Trace，供后续复盘和策略沉淀使用。

## 4. 为什么不适合纯硬规则 NLU

传统 NLU 通常会做两件事：

- intent：识别用户意图，例如 `generate_draft`、`analyze_competitor`、`review_content`；
- entities：抽取实体或参数，例如账号、选题、平台、目标人群、竞品链接、发布时间。

这种方式适合意图集合稳定、话术变化有限、参数格式明确的系统。但本项目不适合完全依赖纯硬规则，原因是：

- 小红书内容运营请求天然模糊，用户经常用口语表达，例如“这个方向值不值得做”“帮我看看能不能爆”；
- 一个请求可能同时包含分析、判断、规划、草稿和审核；
- 用户输入可能来自截图、评论、竞品文本、人工备注，格式不稳定；
- 运营动作需要结合上下文、策略记忆、证据质量和风险等级，不是简单 keyword 能判断；
- 纯规则容易把新增场景变成大量 if/else，后期维护成本会越来越高；
- 本项目仍处在能力逐步接入阶段，不能把未来 MCP、平台写入、图片理解等能力提前硬编码成已可用。

所以，传统 intent + entities 的思想可以保留，但实现方式不应该是纯硬规则。

## 5. 推荐方案：LLM-assisted Router + Structured Schema + Param Validator

更适合本项目的是 LLM-assisted Router + Structured Schema + Param Validator。

LLM-assisted Router 负责理解自然语言和复杂上下文，但它的输出必须落到结构化 Schema 里。Schema 负责限制输出形态，Param Validator 负责检查参数、能力边界和风险。

推荐的 Router 输出不应该是一段自由文本，而应该类似：

```json
{
  "intent": "CONTENT_OPPORTUNITY_ANALYSIS",
  "confidence": 0.86,
  "input_types": ["manual_text", "xhs_comment", "screenshot"],
  "entities": {
    "account_id": null,
    "topic": "护肤新手避坑",
    "target_audience": "新手用户"
  },
  "missing_params": ["account_id"],
  "risk_flags": ["untrusted_user_supplied_context"],
  "needs_clarification": true
}
```

这个方案的原则是：

- LLM 可以帮助理解模糊表达，但不能直接执行；
- Router 可以给出置信度，但不能跳过参数校验；
- Schema 必须稳定，方便测试、Trace 和前后端协作；
- Validator 必须独立存在，不能完全相信 LLM 的判断；
- 当参数缺失、风险较高或能力不支持时，系统应该进入澄清或人工确认，而不是继续执行。

## 6. Planner 应该结构化输出，不能直接执行业务

Planner 的职责是生成计划，不是执行业务。

Planner 输出应该是结构化 Plan，例如：

```json
{
  "task_type": "XHS_CONTENT_WORKFLOW",
  "steps": [
    {
      "step_id": "collect_inputs",
      "action": "NORMALIZE_USER_INPUT",
      "requires_execution": false,
      "allowed_effect": "read_only"
    },
    {
      "step_id": "analyze_competitors",
      "action": "BUILD_COMPETITOR_INSIGHT",
      "requires_execution": true,
      "allowed_effect": "read_only"
    },
    {
      "step_id": "draft_candidates",
      "action": "GENERATE_DRAFT_OPTIONS",
      "requires_execution": true,
      "allowed_effect": "local_generation"
    }
  ],
  "requires_human_confirmation": false
}
```

这里的重点是：

- Planner 只描述步骤，不直接调用数据库、爬虫、LLMClient 或业务服务；
- 每一步都要有明确 action、输入、输出、风险和 allowed effect；
- 如果某一步未来涉及外部写入、发布、删除、私信、评论回复等动作，必须标记人工确认；
- Plan 必须能被 Validator 静态检查；
- Plan 必须能被 Trace 原样记录。

## 7. Plan Validator 必须检查什么

Plan Validator 是第 6 阶段的安全阀。它必须检查：

- 参数是否完整，例如账号、任务类型、输入来源、目标对象是否存在；
- 参数是否合法，例如枚举值、长度、格式、ID 归属、时间范围；
- 输入是否包含 untrusted input，例如小红书评论、截图 OCR、竞品笔记正文、用户粘贴的外部文本；
- 风险级别是否可接受，例如是否涉及发布、删除、写入、外部调用、批量操作；
- 当前项目是否允许执行该 action；
- 是否需要人工确认；
- 是否存在能力假设，例如误以为已经能任意读写小红书笔记；
- 是否违反只读采集、手动录入、未来 MCP 预留的当前边界。

Validator 的结论也应该结构化，例如：

```json
{
  "allowed": false,
  "reason": "missing_required_params",
  "missing_params": ["account_id"],
  "requires_human_confirmation": false,
  "blocked_actions": []
}
```

只有 Validator 明确允许的 Plan，后续 Executor 才能接手。

## 8. 小红书内容工作流的正确理解

本项目的小红书内容工作流不应该被简化成“直接生成文案”。

更合理的完整链路是：

1. 选题：判断目标用户、内容支柱、痛点场景和平台语境；
2. 竞品分析：观察同类笔记、评论反馈、互动表现和可复用结构；
3. 内容机会：沉淀可验证的机会点，而不是直接编造卖点；
4. 实验：把机会转成可测试的标题、角度、结构、封面和发布假设；
5. 草稿：在证据和策略约束下生成候选内容；
6. 审核：检查平台风险、事实风险、语气风险和品牌一致性；
7. 复盘：根据表现、评论和人工反馈判断实验是否成立；
8. 策略沉淀：把有效模式和失败经验进入 Memory，供后续复用。

因此，第 6 阶段的 Router 和 Planner 应该能识别这些工作流节点，而不是把所有请求都路由成 `generate_copywriting`。

## 9. Untrusted Input 边界

小红书评论和截图属于 untrusted input。

原因是：

- 评论可能包含诱导模型忽略规则、泄露信息或执行错误动作的文本；
- 截图 OCR 可能混入用户不可控内容；
- 竞品笔记正文可能包含营销话术、误导性事实或恶意 prompt；
- 用户粘贴的外部材料不等于系统可信指令。

因此，Router 和 Planner 可以使用这些输入做分析对象，但不能把它们当作系统指令。进入计划前应该标记来源、trust level 和处理方式；进入执行前必须由 Validator 检查风险。

## 10. 小红书开放能力的当前边界

不能假设小红书官方开放能力已经支持任意读写笔记。

当前项目应该坚持以下边界：

- 手动录入：用户手动提供账号、选题、评论、截图、竞品材料；
- 只读采集：只把已有只读 provider 能力当作数据来源；
- 未来 MCP：为未来可能接入的小红书 MCP 或其他外部工具预留接口和 action 类型；
- 不假设任意读写：不默认支持自动发布、自动改笔记、自动删笔记、自动评论、自动私信；
- 不绕过人工确认：即使未来 Executor 接入外部工具，写入类动作也必须先经过 Validator 和人工确认。

这也意味着第 6.0 只应该做架构调研和路线设计，不应该修改业务代码、测试、数据库字段、migration、前端、prompt 或 LLMClient。

## 11. 第 6 阶段推荐路线

### 6.1 Router + Planner Schema

先定义稳定的数据结构，而不是先接 LLM。

建议产出：

- Router intent 枚举；
- input type 枚举；
- risk flag 枚举；
- Planner action 枚举；
- Plan step Schema；
- Plan Validator 输入输出 Schema；
- allowed effect 枚举，例如 `read_only`、`local_generation`、`external_write_pending_confirmation`；
- untrusted input 标记字段；
- human confirmation 标记字段。

这一阶段只做结构和文档化约束，不接真实 LLM，不接 Executor。

### 6.2 LLM Router

在 Schema 稳定后，引入 LLM-assisted Router。

建议做法：

- 让 LLM 只输出 Router Schema；
- 对输出做 JSON 解析和字段校验；
- 低置信度或缺参数时进入澄清；
- 不允许 Router 调业务服务；
- 不允许 Router 自行判断外部能力已可用。

### 6.3 Task Planner

基于 Router 输出生成结构化 Plan。

建议做法：

- Planner 输入只接受已校验的 RouterResult；
- Planner 输出 Plan Schema；
- 每个 step 都声明 action、输入依赖、输出、风险和 allowed effect；
- Planner 不调用业务服务；
- Planner 不调用 LLMClient 执行业务生成。

### 6.4 Validator

实现 Plan Validator。

建议做法：

- 校验必填参数；
- 校验 action 是否在当前阶段允许；
- 校验 untrusted input 是否被标记；
- 校验风险和人工确认；
- 禁止未支持的小红书写入能力；
- 输出结构化 validation result。

### 6.5 Trace

记录 Router、Planner、Validator 和未来 Executor 的关键状态。

建议做法：

- 记录原始用户请求摘要；
- 记录 RouterResult；
- 记录 Plan；
- 记录 ValidationResult；
- 记录 blocked reason、missing params 和 risk flags；
- 为后续复盘和策略沉淀预留关联字段。

### 6.6 Executor 接入

在 Router、Planner、Validator、Trace 都稳定后，再接 Executor。

建议做法：

- Executor 只执行通过 Validator 的 Plan；
- 先接只读和本地生成类 action；
- 外部写入类 action 保持 blocked 或 pending confirmation；
- 执行结果进入 Trace；
- 失败信息结构化返回，不让 Executor 自己改 Plan。

### 6.7 多轮反馈和图片输入预留

最后预留多轮澄清、反馈修正和图片输入。

建议做法：

- 支持 Router 返回 missing params；
- 支持用户补充参数后重建 Plan；
- 支持 screenshot input type；
- 支持 OCR 或图片理解结果以 untrusted input 进入系统；
- 支持用户对 Plan 做确认、取消或修改。

## 12. 本阶段结论

第 6 阶段应该选择 LLM Router + Planner + Validator + Executor 的分层方案。

原因是：

- LLM Router 能处理用户口语化、混合型、模糊型请求；
- Structured Schema 能把 LLM 输出约束成可测试、可追踪、可验证的数据；
- Planner 能把复杂内容运营任务拆成明确步骤；
- Validator 能防止参数缺失、风险动作、能力误判和 untrusted input 污染执行链路；
- Executor 延后接入，可以避免在意图和计划还不稳定时直接触发业务副作用；
- Trace 和 Memory 可以在后续阶段承接复盘和策略沉淀。

这条路线更符合小红书内容情报与运营决策系统的真实工作流：先理解用户目标，再组织证据和步骤，再校验风险，最后才执行具体工具或业务服务。

## 13. 调研来源说明

本文档是面向当前项目第 6 阶段的架构调研和方案归纳，没有引用或编造外部调研来源。

结论主要来自：

- Agent 系统常见职责拆分方式；
- 当前项目已有的内容工作流、上下文、证据和策略记忆方向；
- 小红书内容运营任务的实际链路；
- 对 untrusted input、人工确认和外部平台能力边界的工程约束。
