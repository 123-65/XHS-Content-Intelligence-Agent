# 第 5.4 Context Token Budget 预算控制设计

## 1. 设计目的

第 5.4 是在第 5.3 Context Slot 分槽设计之后，为每个 slot 设置第一版 token budget、保留策略、缺失处理和超预算处理规则。

第 5.3 已经回答了“上下文应该分成哪些槽位，以及每类信息应该放到哪里”。第 5.4 继续回答“每个槽位最多应该占多少输入额度，哪些必须保留，哪些可以压缩，哪些可以截断，哪些缺失时应该阻断”。

这样做的目的不是立刻减少 token，而是先建立预算边界。没有预算边界时，竞品证据、评论洞察、策略记忆等长文本可能不断膨胀，挤占系统规则、任务说明、账号画像、输出 schema 和风险约束，导致模型跑偏、输出格式错误或风险判断失效。

## 2. 本阶段边界

本阶段只做预算控制设计，不做业务实现。

本阶段不做：

- 不修改业务 service 逻辑。
- 不修改 prompt 内容。
- 不修改 LLMClient。
- 不新增 Agent。
- 不新增数据库字段。
- 不新增 migration。
- 不调用真实 LLM。
- 不连接数据库。
- 不实现 token 压缩。
- 不实现 Top-K。
- 不替换硬编码领域词。
- 不实现 `domain_profile` 自动生成。
- 不修改前端。
- 不新增第三方依赖。

本阶段输出的是设计文档，后续实现时才把这些规则接入 `ContextManager`、`ContextSnapshot` 或普通 context dict。

## 3. Token Budget 是什么

Token Budget 可以理解为“给每类上下文分配一个最大输入额度”。

模型每次调用时能读取的上下文窗口是有限的。如果某一类信息太长，例如竞品笔记、评论原文、历史策略全部塞进去，就会挤掉更关键的信息，例如系统规则、任务说明、输出结构、账号画像和风险规则。

所以 Token Budget 的作用是：

1. 给每个 slot 设置一个建议上限。
2. 判断某个 slot 是否超过预算。
3. 明确超过预算后应该保留、压缩、Top-K 还是截断。
4. 记录每次上下文构造时的 chars、rough_tokens、budget_tokens 和 over_budget，为后续第 5.5 压缩设计提供依据。

本设计中的 token 数字是第一版工程预算，不是最终性能指标，也不是精确 tokenizer 结果。后续实现阶段可以先用粗略估算，例如按字符数估算，再逐步替换为更准确的 tokenizer。

## 4. Slot 预算设计原则

### 4.1 必须保留原则

以下 slot 控制系统边界、任务目标、输出结构和风险规则，不能随意压缩，也不应该被竞品证据或评论文本挤掉：

- `SYSTEM_RULES`
- `TASK_INSTRUCTION`
- `OUTPUT_SCHEMA`
- `RISK_CONSTRAINTS`

原因是这些 slot 一旦缺失或被压缩过度，模型可能出现三类问题：

1. 不遵守系统边界。
2. 忘记本次任务要做什么。
3. 输出 JSON schema 错误。
4. 风险判断失效或漏掉重要合规约束。

其中 `RISK_CONSTRAINTS` 可以在极端情况下做少量去重或删掉重复解释，但核心规则必须保留。

### 4.2 可压缩原则

以下 slot 很重要，但可以通过摘要、字段筛选或保留关键字段减少 token：

- `ACCOUNT_PROFILE`
- `DOMAIN_PROFILE`
- `WORKFLOW_STATE`
- `DRAFT_CONTENT`

这些 slot 不能简单丢弃，但可以只保留对本次任务真正有用的部分。例如账号画像只保留定位、人群、目标、语气和禁用项；领域画像只保留核心词、风险词、版本号和人工确认状态；流程状态只保留当前实验、机会、假设、指标和风险等级。

### 4.3 Top-K 原则

以下 slot 通常数量多、文本长，最适合在第 5.5 做 Top-K 或摘要：

- `COMPETITOR_EVIDENCE`
- `COMMENT_INSIGHT`
- `STRATEGY_MEMORY`

竞品证据、评论洞察和策略记忆都不应该无上限进入 LLM。后续应该按相关性、置信度、新鲜度、风险等级和证据强度筛选，而不是把所有原始样本都传给模型。

### 4.4 缺失处理原则

不同 slot 缺失时不能一刀切处理。

必须阻断的 slot：

- `SYSTEM_RULES` 缺失：阻断。
- `TASK_INSTRUCTION` 缺失：阻断。
- `OUTPUT_SCHEMA` 缺失：阻断。
- `ACCOUNT_PROFILE` 缺失：阻断或要求用户补充。
- `DRAFT_CONTENT` 缺失：审核任务阻断，草稿生成任务不需要。

可以继续但必须标记状态的 slot：

- `DOMAIN_PROFILE` 缺失：允许继续，但标记 `UNKNOWN`。
- `WORKFLOW_STATE` 缺失：允许继续，但标记 `DATA_PARTIAL`。
- `COMPETITOR_EVIDENCE` 缺失：允许继续，但标记 `DATA_NOT_PROVIDED`。
- `COMMENT_INSIGHT` 缺失：允许继续，但标记 `DATA_NOT_PROVIDED`。
- `STRATEGY_MEMORY` 缺失：允许继续，但标记 `NOT_PROVIDED`。
- `RISK_CONSTRAINTS` 缺失：使用通用风险规则兜底，并记录 warning。

### 4.5 超预算处理原则

超预算时按 slot 类型处理：

- 必须保留 slot：不直接压缩，优先去重、删重复说明或阻断后提示需要人工处理。
- 可压缩 slot：保留关键字段，摘要长文本。
- Top-K slot：先筛选最相关、最高置信、最新或最高价值的记录。
- 可截断 slot：保留开头的明确要求、当前状态或待审核正文核心，截断低价值尾部。

第 5.4 只定义这些规则，不实现压缩和 Top-K。

## 5. Slot 预算总览表

| Slot | 建议预算 token | 保留策略 | 是否必须保留 | 是否可压缩 | 是否可截断 | 缺失处理 | 超预算处理 | 第 5.5 优先动作 | 是否进入 ContextSnapshot |
|---|---:|---|---|---|---|---|---|---|---|
| `SYSTEM_RULES` | 300 | 系统边界必须保留 | 是 | 否 | 否 | 阻断 | 去重或阻断，不做语义压缩 | 保留 | 是 |
| `TASK_INSTRUCTION` | 300 | 本次任务说明必须保留 | 是 | 否 | 否 | 阻断 | 去重或要求缩短任务描述 | 保留 | 是 |
| `USER_INPUT` | 500 | 原文优先，保留本轮明确要求 | 否 | 可轻微压缩 | 是，可截断长文本 | 可为空 | 保留明确约束，截断冗余长文本 | 可截断 | 是 |
| `ACCOUNT_PROFILE` | 500 | 关键字段保留 | 是 | 是 | 是 | 阻断或要求补充 | 保留定位、人群、目标、语气、禁用项 | 轻量摘要 | 是 |
| `DOMAIN_PROFILE` | 700 | 核心词、风险词、版本和确认状态保留 | 否，未确认时可缺省 | 是 | 是 | `UNKNOWN` | 保留核心词和版本，长尾词截断 | 人工确认后再启用压缩策略 | 是 |
| `WORKFLOW_STATE` | 800 | 当前实验、机会、假设和指标优先 | 否 | 是 | 是 | `DATA_PARTIAL` | 保留当前链路状态，截断历史状态 | 可截断 | 是 |
| `COMPETITOR_EVIDENCE` | 1200 | Top-K 证据保留 | 否 | 是 | 是 | `DATA_NOT_PROVIDED` | 按相关性、表现、证据强度做 Top-K | 优先 Top-K | 是 |
| `COMMENT_INSIGHT` | 800 | 摘要加代表评论 | 否 | 是 | 是 | `DATA_NOT_PROVIDED` | 保留需求分类、计数、代表评论，截断原文 | 优先摘要和 Top-K | 是 |
| `STRATEGY_MEMORY` | 600 | 最近有效策略优先 | 否 | 是 | 是 | `NOT_PROVIDED` | 按新鲜度、置信度、同领域匹配筛选 | 优先 Top-K | 是 |
| `RISK_CONSTRAINTS` | 500 | 通用风险和领域风险必须保留 | 是 | 否 | 可少量截断重复解释 | 通用规则兜底 | 保留核心规则，删重复说明 | 保留 | 是 |
| `OUTPUT_SCHEMA` | 800 | schema 核心必须保留 | 是 | 否 | 否 | 阻断 | 保留字段和类型约束，必要时精简解释文字 | 保留 | 是 |
| `DRAFT_CONTENT` | 1200 | 审核任务必须保留待审正文核心 | 审核任务是，生成任务否 | 是 | 是 | 审核任务阻断 | 保留 title、body、tags、cta，压缩 generation_context | 可截断 generation_context | 是 |

第一版总预算口径约为 8200 token。如果不包含审核专用的 `DRAFT_CONTENT`，草稿生成主链路约为 7000 token。

这些数字只是第一版预算设计，不能写成“token 降低 xx%”“成本下降 xx%”或“延迟降低 xx%”，因为本阶段还没有做压缩实现和对比实验。

## 6. P0 链路预算设计

### 6.1 content_draft_v2

`content_draft_v2` 是第一优先治理对象，建议总预算约 7000 token。

它最适合先接 slot budget，原因是它已经使用：

- `ContextManager`
- `BuiltContext`
- `PromptRunLog`
- `ContextSnapshot`

也就是说，它已经具备上下文构建和记录基础，不需要先大规模改造业务链路。第 5.4 的预算规则可以先在它上面验证，再迁移到 `review_report` 和旧 `content_draft`。

建议预算：

| Slot | 建议预算 token | 在 content_draft_v2 中的作用 | 处理策略 |
|---|---:|---|---|
| `SYSTEM_RULES` | 300 | 控制系统边界和通用行为规则 | 必须保留 |
| `TASK_INSTRUCTION` | 300 | 说明生成草稿、局部重生成或指定输出动作 | 必须保留 |
| `USER_INPUT` | 500 | 承载用户本轮要求、补充语气或临时约束 | 原文优先，长文本可截断 |
| `ACCOUNT_PROFILE` | 500 | 提供账号定位、人群、目标和语气 | 关键字段保留 |
| `DOMAIN_PROFILE` | 700 | 提供领域核心词、风险词、转化词和版本 | 先记录，人工确认后稳定启用 |
| `WORKFLOW_STATE` | 800 | 提供当前实验、内容机会、选题和目标指标 | 保留当前状态，压缩历史状态 |
| `COMPETITOR_EVIDENCE` | 1200 | 提供标题模式、内容支柱、爆款拆解和证据来源 | 第 5.5 优先 Top-K |
| `COMMENT_INSIGHT` | 800 | 提供评论需求、痛点、转化信号和代表评论 | 第 5.5 摘要加 Top-K |
| `STRATEGY_MEMORY` | 600 | 提供历史有效策略和复盘结论 | 第 5.5 按置信度和新鲜度筛选 |
| `RISK_CONSTRAINTS` | 500 | 提供平台、账号和领域风险边界 | 必须保留 |
| `OUTPUT_SCHEMA` | 800 | 提供结构化输出字段和校验约束 | 必须保留 |

合计约 7000 token。

后续需要做 Top-K 的 slot：

- `COMPETITOR_EVIDENCE`
- `COMMENT_INSIGHT`
- `STRATEGY_MEMORY`

后续需要记录到 `ContextSnapshot` 的 slot：

- `SYSTEM_RULES`
- `TASK_INSTRUCTION`
- `USER_INPUT`
- `ACCOUNT_PROFILE`
- `DOMAIN_PROFILE`
- `WORKFLOW_STATE`
- `COMPETITOR_EVIDENCE`
- `COMMENT_INSIGHT`
- `STRATEGY_MEMORY`
- `RISK_CONSTRAINTS`
- `OUTPUT_SCHEMA`

其中 `DOMAIN_PROFILE` 还应记录 `source_version`、`human_confirmed` 语义和 `data_status`。如果上下文中包含硬编码领域词，应记录 `contains_hardcoded_domain_terms=true`。

### 6.2 content_draft

旧版 `content_draft` 仍是普通 context dict，建议总预算约 4000 token。

本阶段不建议对旧版做大改，原因是旧链路还没有 `ContextManager`、`PromptRunLog` 和 `ContextSnapshot` 的完整结构。如果此时投入复杂压缩逻辑，容易把旧链路改得很重，但收益不如先治理 `content_draft_v2` 明确。

建议旧版先做 slot 命名对齐，不优先投入复杂压缩：

| Slot | 建议预算 token | 旧 context dict 映射 | 处理策略 |
|---|---:|---|---|
| `TASK_INSTRUCTION` | 250 | prompt 任务描述 | 保留 |
| `USER_INPUT` | 300 | `user_requirement` | 长文本截断 |
| `ACCOUNT_PROFILE` | 400 | `account` | 关键字段保留 |
| `DOMAIN_PROFILE` | 500 | 后续新增或从账号画像派生 | 缺失标记 `UNKNOWN` |
| `WORKFLOW_STATE` | 600 | `experiment` | 保留当前实验 |
| `COMPETITOR_EVIDENCE` | 1000 | `analysis_report` 中的标题、标签、内容洞察和建议 | 后续 Top-K |
| `STRATEGY_MEMORY` | 400 | 历史策略或复盘摘要 | 可缺省 |
| `OUTPUT_SCHEMA` | 550 | DraftGenerateResult 字段要求 | 保留 |

合计约 4000 token。

旧版 `content_draft` 的原则是：

1. 先把 `account`、`experiment`、`analysis_report`、`user_requirement` 映射到统一 slot 名称。
2. 暂时不做复杂压缩实现。
3. 不优先改 prompt 和业务逻辑。
4. 等 `content_draft_v2` 的预算统计稳定后，再逐步迁移旧链路。

### 6.3 review_report

`review_report` 的重点是审核草稿，不是塞入大量竞品证据，建议总预算约 5000 token。

审核链路最关键的是：

- `DRAFT_CONTENT`：待审核草稿正文，审核任务必须保留。
- `RISK_CONSTRAINTS`：风险判断规则，不应该压缩。
- `OUTPUT_SCHEMA`：审核报告结构，不应该压缩。
- `DOMAIN_PROFILE`：后续用于领域风险词，例如具体行业的违规承诺、敏感表达和禁用词。

建议预算：

| Slot | 建议预算 token | 在 review_report 中的作用 | 处理策略 |
|---|---:|---|---|
| `SYSTEM_RULES` | 300 | 控制审核边界 | 必须保留 |
| `TASK_INSTRUCTION` | 300 | 说明本次是审核任务 | 必须保留 |
| `ACCOUNT_PROFILE` | 400 | 判断草稿是否符合账号定位 | 关键字段保留 |
| `DOMAIN_PROFILE` | 600 | 提供领域风险词和禁用词 | 缺失标记 `UNKNOWN` |
| `DRAFT_CONTENT` | 1200 | 承载待审核 title、body、tags、cover_text、image_scripts、cta | 待审正文核心必须保留 |
| `WORKFLOW_STATE` | 500 | 提供实验目标、选题背景和生成上下文摘要 | 可压缩 |
| `COMMENT_INSIGHT` | 400 | 提供评论风险、用户疑虑或代表需求 | 可缺省，可摘要 |
| `RISK_CONSTRAINTS` | 500 | 提供平台、账号和领域风险规则 | 必须保留 |
| `OUTPUT_SCHEMA` | 800 | 提供审核结果结构和字段约束 | 必须保留 |

合计约 5000 token。

`DRAFT_CONTENT` 缺失时，审核任务必须阻断。因为没有待审核正文，模型无法判断标题、正文、标签、封面文案、图片脚本和 CTA 是否存在问题。

## 7. P1 上游模块预算口径

P1 模块当前不一定直接调用 LLM，但它们的输出会进入下游 P0 context，所以第 5.4 需要明确这些输出未来应该进入哪个 slot。

### 7.1 competitor_report

`competitor_report` 可能输出：

- `persona_patterns`
- `content_pillars`
- `title_patterns`
- `cover_patterns`
- `content_structures`
- `comment_demands`
- `conversion_signals`
- `risk_points`
- `high_performance_notes`
- `viral_note_breakdowns`
- `content_opportunities`
- `suggestions`

建议映射：

| 输出字段 | 推荐 Slot | 说明 |
|---|---|---|
| `persona_patterns` | `COMPETITOR_EVIDENCE` | 同行账号人设证据 |
| `content_pillars` | `COMPETITOR_EVIDENCE` | 内容支柱和选题证据 |
| `title_patterns` | `COMPETITOR_EVIDENCE` | 标题模式证据 |
| `cover_patterns` | `COMPETITOR_EVIDENCE` | 封面模式证据 |
| `content_structures` | `COMPETITOR_EVIDENCE` | 内容结构证据 |
| `high_performance_notes` | `COMPETITOR_EVIDENCE` | 高表现笔记证据，后续 Top-K |
| `viral_note_breakdowns` | `COMPETITOR_EVIDENCE` | 爆款拆解，后续 Top-K |
| `comment_demands` | `COMMENT_INSIGHT` | 评论需求分类 |
| `conversion_signals` | `COMMENT_INSIGHT` | 转化信号 |
| `risk_points` | `RISK_CONSTRAINTS` / `COMMENT_INSIGHT` | 风险规则和评论风险线索 |
| `content_opportunities` | `WORKFLOW_STATE` | 内容机会进入实验和草稿流程 |
| `suggestions` | `STRATEGY_MEMORY` / `WORKFLOW_STATE` | 可沉淀为策略，也可作为当前流程建议 |

`competitor_report` 本阶段不一定做 token 预算实现，但必须明确它输出的字段后续会进入 `COMPETITOR_EVIDENCE`、`COMMENT_INSIGHT`、`WORKFLOW_STATE`、`RISK_CONSTRAINTS` 或 `STRATEGY_MEMORY`。

### 7.2 competitor_analysis

建议映射：

| 输出字段 | 推荐 Slot | 说明 |
|---|---|---|
| `top_tags` | `COMPETITOR_EVIDENCE` | 标签证据 |
| `title_patterns` | `COMPETITOR_EVIDENCE` | 标题模式证据 |
| `high_performance_notes` | `COMPETITOR_EVIDENCE` | 高表现笔记证据 |
| `content_insights` | `COMPETITOR_EVIDENCE` / `COMMENT_INSIGHT` | 内容洞察和用户需求洞察 |
| `suggestions` | `WORKFLOW_STATE` | 当前草稿或实验可用建议 |
| `summary` | `WORKFLOW_STATE` | 当前分析摘要 |

`competitor_analysis` 当前是旧上游链路，先做 slot 映射，不优先做复杂预算实现。

### 7.3 content_experiment_v2

建议映射：

| 输出字段 | 推荐 Slot | 说明 |
|---|---|---|
| `experiment_name` | `WORKFLOW_STATE` | 当前实验名称 |
| `hypothesis` | `WORKFLOW_STATE` | 实验假设 |
| `content_pillar` | `WORKFLOW_STATE` | 当前内容支柱 |
| `content_format` | `WORKFLOW_STATE` | 当前内容形式 |
| `main_variable` | `WORKFLOW_STATE` | 主变量 |
| `control_variables` | `WORKFLOW_STATE` | 控制变量 |
| `primary_metric` | `WORKFLOW_STATE` | 主指标 |
| `success_criteria` | `WORKFLOW_STATE` | 成功标准 |
| `failure_criteria` | `WORKFLOW_STATE` | 失败标准 |
| `fallback_strategy` | `WORKFLOW_STATE` | 兜底策略 |
| `topic_angle` | `WORKFLOW_STATE` | 选题角度 |
| `selected_topic` | `WORKFLOW_STATE` | 最终选题 |

`content_experiment_v2` 的输出主要进入 `WORKFLOW_STATE`，后续预算重点是保留当前实验、当前选题、假设、指标和风险等级，而不是保留所有历史实验细节。

### 7.4 strategy_memory

建议映射：

| 输出字段 | 推荐 Slot | 说明 |
|---|---|---|
| `memory_type` | `STRATEGY_MEMORY` | 记忆类型 |
| `summary` | `STRATEGY_MEMORY` | 策略摘要 |
| `pattern` | `STRATEGY_MEMORY` | 已验证表达或策略模式 |
| `confidence` | `STRATEGY_MEMORY` | 置信度，后续 Top-K 重要依据 |
| `usage_snapshot` | `STRATEGY_MEMORY` | 使用场景摘要 |
| `usage_reason` | `STRATEGY_MEMORY` | 为什么本次使用 |
| `updated_at` | `STRATEGY_MEMORY` | 新鲜度依据 |

`STRATEGY_MEMORY` 后续应该按置信度、新鲜度和同领域匹配筛选，不应该把所有历史记忆都塞入当前 prompt。

## 8. 硬编码领域词的预算处理

本阶段不替换硬编码领域词，只做预算和记录原则。

处理原则：

1. 如果硬编码词来自 tests、mock 或 seed，可以保留，但必须标记为 `test/demo`，避免被误认为生产真实样本。
2. 如果硬编码词来自生产 prompt，需要后续迁移到 `DOMAIN_PROFILE`，并从账号画像、真实样本和人工确认中获得。
3. 如果硬编码词来自 `competitor_report` 或 `competitor_analysis` 的规则输出，需要标记 `source=rule_based`。
4. 如果硬编码词进入 `content_draft_v2` context，需要在 `ContextSnapshot` 中标记 `contains_hardcoded_domain_terms=true`。
5. 第 5.4 不删除这些词，只为第 5.5 压缩、Top-K 和后续 `domain_profile` 改造提供依据。

硬编码领域词进入预算体系后，不应该只看 token 数，还要看来源和数据状态。例如同样是“项目、简历、面试”，如果来自测试样本，可以标记为 demo；如果来自生产 prompt，就需要迁移；如果来自规则输出，就需要在 snapshot 中记录 `source=rule_based`，方便后续追踪。

## 9. ContextSnapshot 预算字段设计

后续每个进入 LLM context 的 slot 都应该记录预算字段。这样才能知道“哪个 slot 占了多少 token、是否超预算、是否被压缩或截断、数据是否缺失、是否含硬编码领域词”。

建议字段：

| 字段 | 类型建议 | 中文解释 |
|---|---|---|
| `slot_name` | string | 当前上下文槽位名称，例如 `ACCOUNT_PROFILE`、`COMPETITOR_EVIDENCE`。 |
| `source` | string | 当前 slot 的来源，例如 `prompt_template`、`account_profile`、`domain_profile`、`competitor_report`、`competitor_analysis`、`content_experiment_v2`、`manual_input`。 |
| `chars` | int | 当前 slot 的字符数，用于粗略观察文本长度。 |
| `rough_tokens` | int | 粗略 token 数，用于预算判断，不是精确 tokenizer 结果。 |
| `budget_tokens` | int | 当前 slot 的预算上限。 |
| `over_budget` | bool | 当前 slot 是否超过预算。 |
| `priority` | string | 当前 slot 的优先级，例如 `P0_REQUIRED`、`P0_CONTEXT`、`P1_EVIDENCE`、`OPTIONAL`。 |
| `required` | bool | 当前 slot 是否为必须存在的上下文。 |
| `compressible` | bool | 是否允许摘要压缩。 |
| `trimmable` | bool | 是否允许截断。 |
| `compressed` | bool | 本次构造中是否已经被压缩。第 5.4 只设计字段，第 5.5 后才会真正使用。 |
| `truncated` | bool | 本次构造中是否已经被截断。 |
| `data_status` | string | 数据状态，例如 `REAL`、`MANUAL`、`UNKNOWN`、`NOT_PROVIDED`、`PARTIAL`、`MOCK`、`UNCONFIRMED`。 |
| `contains_hardcoded_domain_terms` | bool | 当前 slot 是否包含第 5.2 扫描出的硬编码领域词。 |
| `source_version` | string | 来源版本，例如 prompt version、domain_profile version、report id、experiment id 或 strategy memory version。 |
| `warning` | string | 超预算、缺失、未确认、使用兜底规则、含硬编码领域词等提示。 |

字段解释：

- `slot_name`：告诉我们当前记录的是哪个槽位。
- `source`：告诉我们这段上下文从哪里来，方便追踪问题来源。
- `chars`：字符数，便于快速观察文本长短。
- `rough_tokens`：粗略 token 数，便于判断是否超过预算。
- `budget_tokens`：这个 slot 被允许使用的预算上限。
- `over_budget`：是否超过预算，上线后可以用来报警或触发压缩策略。
- `priority`：优先级，用于决定保留、压缩、Top-K 或截断顺序。
- `required`：是否必须存在。必需 slot 缺失时通常要阻断。
- `compressible`：是否可以被摘要压缩。
- `trimmable`：是否可以被截断。
- `compressed`：是否已经压缩。第 5.4 暂不实现，只预留记录字段。
- `truncated`：是否已经截断。第 5.4 暂不实现，只预留记录字段。
- `data_status`：数据状态，例如真实数据、人工数据、未知、未提供、部分数据、mock 数据或未确认数据。
- `contains_hardcoded_domain_terms`：是否包含硬编码领域词，用于后续领域画像改造。
- `source_version`：来源版本，保证回放和排查时知道当时用的是哪版 prompt、报告、实验或领域画像。
- `warning`：给工程排查看的提示，例如“超预算”“缺失但继续”“使用通用风险规则兜底”“领域画像未人工确认”。

## 10. 第 5.5 压缩前置规则

第 5.5 不应该一上来压缩所有内容，而应该按优先级处理。

必须保留：

- `SYSTEM_RULES`
- `TASK_INSTRUCTION`
- `OUTPUT_SCHEMA`
- `RISK_CONSTRAINTS`

这些 slot 控制边界、任务、结构和风险，不应该做语义压缩。

优先压缩或 Top-K：

- `COMPETITOR_EVIDENCE`
- `COMMENT_INSIGHT`
- `STRATEGY_MEMORY`

这些 slot 信息量大、数量多，最容易超预算，应该优先做 Top-K、摘要和筛选。

可截断：

- `USER_INPUT`
- `WORKFLOW_STATE`
- `DRAFT_CONTENT`

这些 slot 可以在保留核心信息后截断低价值尾部。`DRAFT_CONTENT` 要特别注意：待审核正文核心不能乱压缩，但 `generation_context` 可以摘要或截断。

需要人工确认后再启用：

- `DOMAIN_PROFILE`

`DOMAIN_PROFILE` 会影响领域词、风险词和转化词，应该带版本号和人工确认状态。未确认时可以作为低置信候选或标记 `UNKNOWN`，不应该直接变成生产默认规则。

## 11. 后续实施顺序

建议后续按以下顺序实现：

1. 先在 `content_draft_v2` 上实现 slot 级 token budget 统计。
2. 再在 `ContextSnapshot` 中记录每个 slot 的 `chars`、`rough_tokens`、`budget_tokens`、`over_budget`。
3. 对 `COMPETITOR_EVIDENCE` 做 Top-K。
4. 对 `COMMENT_INSIGHT` 做摘要压缩。
5. 对 `STRATEGY_MEMORY` 做最近有效策略筛选。
6. 再把 `review_report` 接入 slot 级预算。
7. 最后逐步处理旧 `content_draft`。

这个顺序的原因是：`content_draft_v2` 已经有上下文工程基础设施，适合作为第一个预算统计落地点；`review_report` 对风险和待审正文更敏感，应该在预算字段稳定后接入；旧 `content_draft` 可以先做命名对齐，避免过早重构旧链路。

## 12. 当前可写进简历的表达

当前只能写设计和基线，不能写优化后百分比。

可写：

> 完成 Context Engineering 设计，基于 SYSTEM_RULES、ACCOUNT_PROFILE、DOMAIN_PROFILE、WORKFLOW_STATE、COMPETITOR_EVIDENCE、COMMENT_INSIGHT、STRATEGY_MEMORY、RISK_CONSTRAINTS、OUTPUT_SCHEMA 等 slot 设计 token budget，为后续上下文压缩、Top-K 证据筛选和成本优化建立基线。

不能写：

- token 降低 xx%
- 成本下降 xx%
- 延迟降低 xx%
- 输出质量提升 xx%

原因是第 5.4 只做预算控制设计，还没有实现压缩、Top-K、对比实验和线上指标采集。

## 13. 结论

1. `content_draft_v2` 是第一个应该实现 slot budget 的链路，因为它已经有 `ContextManager`、`BuiltContext`、`PromptRunLog` 和 `ContextSnapshot`。
2. `COMPETITOR_EVIDENCE`、`COMMENT_INSIGHT`、`STRATEGY_MEMORY` 是最需要压缩和 Top-K 的 slot。
3. `SYSTEM_RULES`、`TASK_INSTRUCTION`、`OUTPUT_SCHEMA`、`RISK_CONSTRAINTS` 不应该做语义压缩。
4. `ACCOUNT_PROFILE`、`DOMAIN_PROFILE`、`WORKFLOW_STATE`、`DRAFT_CONTENT` 可以压缩，但不能简单丢弃。
5. `DOMAIN_PROFILE` 应该有版本号、来源和人工确认状态。
6. 所有进入 LLM context 的 slot 后续都应该进入 `ContextSnapshot` 记录预算字段。
7. 第 5.4 不产生优化后指标，只为第 5.5 压缩、摘要和 Top-K 做准备。
