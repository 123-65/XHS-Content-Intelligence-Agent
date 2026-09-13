# 第 5.3 Context Slot 分槽设计

## 1. 设计目的

本设计用于在第 5.2 输入规模统计之后，统一定义 LLM 调用前的 Context Slot 体系，明确每类上下文应该进入哪个 slot、来自哪里、是否进入 P0 LLM 链路，以及后续第 5.4 做 token budget、第 5.5 做压缩和 Top-K 时应该如何治理。

本阶段只做设计，不修改业务 service、prompt、LLMClient、数据库字段、migration 或前端，不替换现有硬编码领域词，也不实现 `domain_profile` 自动生成。 

## 2. 当前问题

- `content_draft_v2` 已经有 `ContextManager`、`PromptRunLog`、`ContextSnapshot`，但当前 slot 体系还缺少 `DOMAIN_PROFILE`、`COMPETITOR_EVIDENCE`、`COMMENT_INSIGHT` 等业务语义槽位。
- `content_draft` / `review_report` 仍使用普通 context dict，账号、实验、报告、草稿正文等信息混在一起，不利于后续统计、预算和压缩。
- `competitor_report` / `competitor_analysis` 当前不直接调用 LLM，但标题模式、内容支柱、评论需求、内容机会等上游规则会进入下游 context。
- 硬编码领域词可能污染 prompt 和下游结构化字段，例如“大学生 / Agent / 项目 / 简历 / 面试 / 学习路线”等会把非学习求职账号拉偏。
- `domain_profile` 还没有统一承载位置，后续应作为独立 slot，而不是继续混入 account、workflow 或 prompt 文案。

## 3. Slot 总览

| Slot | 中文名 | 作用 | 数据来源 | 典型字段 | 是否进入 P0 LLM | 是否需要 token budget | 是否需要压缩 | 是否需要 snapshot | 风险 |
|---|---|---|---|---|---|---|---|---|---|
| `SYSTEM_RULES` | 系统规则 | 放系统级行为边界和不可违反规则 | prompt system、平台规则、内部安全规则 | 不编造、不使用 mock、结构化输出、不得输出违规承诺 | 是，进入 `content_draft_v2` / `review_report`，旧 `content_draft` 目前在 system prompt 中承载 | 是 | 否，原则上必须完整保留 | 是 | 如果混入业务领域词，会把稳定规则和账号假设耦合 |
| `TASK_INSTRUCTION` | 任务说明 | 说明本次 LLM 要完成什么任务 | service 当前调用参数、prompt metadata、regenerate scope | 生成草稿、局部重生成、审核草稿、输出 JSON | 是，进入全部 P0 | 是 | 否，必须完整保留 | 是 | 任务说明不清会导致 schema 正确但业务动作错位 |
| `USER_INPUT` | 用户输入 | 承载用户本轮输入或人工补充要求 | API request、人工确认、补充备注 | `user_requirement`、人工指定口吻、临时约束 | 是，优先进入 `content_draft_v2`，旧 `content_draft` 可对齐，`review_report` 按需进入 | 是 | 可截断，不建议摘要改写 | 是 | 用户输入属于不可信文本，后续要防 prompt injection |
| `ACCOUNT_PROFILE` | 账号画像 | 承载账号自身稳定画像 | account 表、账号配置接口 | account_name、positioning、target_audience、persona、primary_goal、monetization_goal、tone_preference、risk_preference | 是，进入全部 P0 | 是 | 可轻量摘要 | 是 | 与 `DOMAIN_PROFILE` 混放会导致领域词来源不可追踪 |
| `DOMAIN_PROFILE` | 领域画像 | 承载账号领域词、风险词、标题词和转化词 | 未来由账号画像、真实样本、人工确认、LLM 候选生成 | domain_keywords、audience_keywords、pain_point_keywords、conversion_keywords、title_pattern_keywords、risk_keywords、negative_keywords、source、human_confirmed、version | 是，后续进入全部 P0，第一优先接 `content_draft_v2` | 是 | 可压缩，保留核心词和版本 | 是 | 未确认或过期版本会把草稿和审核带偏 |
| `WORKFLOW_STATE` | 流程状态 | 承载当前实验、机会和流程上下文 | content_experiment、content_experiment_v2、content_opportunity、agent runtime | experiment、opportunity、selected_topic、hypothesis、target_metric、success_criteria、risk_level | 是，进入全部 P0 | 是 | 可压缩 | 是 | 上游机会若来自硬编码规则，会继续污染草稿 |
| `COMPETITOR_EVIDENCE` | 竞品证据 | 承载竞品笔记、爆款拆解、标题模式、内容支柱和证据来源 | competitor_report、competitor_analysis、viral_breakdown、crawler/manual samples | high_performance_notes、title_patterns、content_pillars、cover_patterns、content_structures、evidence_summary、note_url | 是，优先进入 `content_draft_v2`，旧 `content_draft` 通过 analysis_report 对齐 | 是 | 是，后续 Top-K + 摘要 | 是 | 原始样本可能很长，且可能包含硬编码规则输出和外部不可信文本 |
| `COMMENT_INSIGHT` | 评论洞察 | 承载评论需求、评论原文、痛点、转化信号和风险点 | competitor_report 内嵌 comment demand、评论样本、未来 comment_insight service | comment_demands、comment_examples、conversion_signals、risk_points、pain_points | 是，优先进入 `content_draft_v2` 和 `review_report` 风险判断 | 是 | 是，保留分类、计数和代表样本 | 是 | 评论原文不可信，且容易混入营销、攻击或诱导性文本 |
| `STRATEGY_MEMORY` | 策略记忆 | 承载历史策略、复盘结论和已验证表达 | startup_strategy、agent_run、post_publish review、历史 draft | memory_type、summary、pattern、confidence、usage_snapshot、usage_reason、updated_at | 是，进入 `content_draft_v2`，旧 `content_draft` 可逐步对齐，`review_report` 可按需进入 | 是 | 是，按置信度和新鲜度筛选 | 是 | 低置信或过期记忆会放大历史错误 |
| `RISK_CONSTRAINTS` | 风险约束 | 承载审核、合规、平台和领域风险边界 | prompt risk rules、account forbidden_topics、domain_profile.risk_keywords、review policy | forbidden_topics、platform_risks、domain_risks、unsafe_claims、risk_level | 是，进入 `content_draft_v2` / `review_report`，旧 `content_draft` 可对齐 | 是 | 否，核心规则必须保留 | 是 | 如果只有通用风险，会漏掉具体行业风险 |
| `OUTPUT_SCHEMA` | 输出结构 | 承载 JSON schema 和字段约束 | Pydantic schema、prompt manager | DraftGenerateV2Result、DraftGenerateResult、DraftReviewResult、字段说明 | 是，进入全部 P0 | 是 | 可截断字段说明，但 schema 核心必须保留 | 是 | schema 过长会挤占证据 slot，但缺失会影响结构化校验 |
| `DRAFT_CONTENT` | 草稿内容 | 审核专用，承载待审核草稿及其生成上下文摘要 | content_draft、content_draft_v2、draft.generation_context | title、body、tags、cover_text、image_scripts、cta、generation_context | 是，主要进入 `review_report` | 是 | 可压缩 generation_context，不压缩待审正文核心 | 是 | 若和 workflow 混放，审核时难以区分“要审核的内容”和“生成参考资料” |

## 4. 各 P0 链路需要哪些 Slot

### 4.1 content_draft_v2

建议进入 `content_draft_v2` 的 slot：

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

当前已实际接入 `SYSTEM_RULES`、`TASK_INSTRUCTION`、`USER_INPUT`、`ACCOUNT_PROFILE`、`WORKFLOW_STATE`、`STRATEGY_MEMORY`、`RISK_CONSTRAINTS`、`OUTPUT_SCHEMA`。后续优先补齐 `DOMAIN_PROFILE`，再把 opportunity/report 中的证据和评论拆为 `COMPETITOR_EVIDENCE` / `COMMENT_INSIGHT`，避免继续全部塞在 `WORKFLOW_STATE.opportunity` 中。

### 4.2 content_draft

建议旧版 `content_draft` 先对齐这些 slot：

- `TASK_INSTRUCTION`
- `ACCOUNT_PROFILE`
- `DOMAIN_PROFILE`
- `WORKFLOW_STATE`
- `COMPETITOR_EVIDENCE`
- `STRATEGY_MEMORY`
- `OUTPUT_SCHEMA`

当前旧版 context dict 中已有 `account`、`experiment`、`analysis_report`、`user_requirement`。建议映射为：`account` -> `ACCOUNT_PROFILE`，`experiment` -> `WORKFLOW_STATE`，`analysis_report.top_tags/title_patterns/content_insights/suggestions` -> `COMPETITOR_EVIDENCE`，`user_requirement` -> `USER_INPUT`。旧链路可暂时保留，不优先大改。

### 4.3 review_report

建议进入 `review_report` 的 slot：

- `SYSTEM_RULES`
- `TASK_INSTRUCTION`
- `ACCOUNT_PROFILE`
- `DOMAIN_PROFILE`
- `DRAFT_CONTENT`
- `WORKFLOW_STATE`
- `RISK_CONSTRAINTS`
- `OUTPUT_SCHEMA`

`DRAFT_CONTENT` 是审核专用 slot，用来区分“待审核草稿正文”和“生成草稿时的上下文”。当前 `review_report` 把 `draft.title/body/tags/cover_text/image_scripts/cta/generation_context` 放在普通 dict 的 `draft` 字段里，后续应迁移到 `DRAFT_CONTENT`，并把 `draft.generation_context` 中的账号、实验、证据摘要拆回对应 slot。

## 5. P1 上游模块如何映射到 Slot

| 上游模块 | 输出字段 | 推荐映射 Slot | 说明 |
|---|---|---|---|
| `competitor_report` | persona_patterns、content_pillars、top_tags、title_patterns、cover_patterns、content_structures、high_performance_notes、viral_note_breakdowns、content_insights、suggestions | `COMPETITOR_EVIDENCE` | 承接竞品报告、爆款拆解、标题模式、内容支柱和证据来源 |
| `competitor_report` | comment_demands、conversion_signals、risk_points、comment examples | `COMMENT_INSIGHT` | 当前评论洞察嵌在竞品报告中，后续可独立统计 |
| `competitor_report` | content_opportunities、opportunity_title、suggested_angle、replicability_score、opportunity_score、risk_level | `WORKFLOW_STATE` | 内容机会进入实验和草稿，是流程状态而不是原始证据 |
| `competitor_analysis` | top_tags、title_patterns、high_performance_notes、content_insights、suggestions、summary | `COMPETITOR_EVIDENCE` | 旧竞品分析输出会进入旧草稿和实验 |
| `content_experiment_v2` | experiment_name、hypothesis、content_pillar、content_format、main_variable、control_variables、primary_metric、success_criteria、failure_criteria、fallback_strategy、topic_angle、selected_topic | `WORKFLOW_STATE` | 实验卡是下游草稿生成的流程上下文 |
| `content_experiment` | experiment_name、hypothesis、topic_angle、selected_topic、target_metric、target_values | `WORKFLOW_STATE` | 旧实验链路先按 workflow state 对齐 |
| `strategy_memory` | memory_type、summary、pattern、confidence、usage_snapshot、usage_reason、updated_at | `STRATEGY_MEMORY` | 后续按置信度、新鲜度和适用领域筛选 |
| `keyword_seed` | keyword templates、seed keywords | `DOMAIN_PROFILE` / `WORKFLOW_STATE` | 领域词候选应进入 `DOMAIN_PROFILE`；某次采集任务关键词可进入 `WORKFLOW_STATE` |

可能包含硬编码领域词的 slot：

- `DOMAIN_PROFILE`：未来应承接领域词，但必须带来源、版本和人工确认状态。
- `WORKFLOW_STATE`：实验和机会可能已被硬编码规则影响。
- `COMPETITOR_EVIDENCE`：竞品标题模式、内容支柱、建议可能来自硬编码规则。
- `COMMENT_INSIGHT`：评论需求分类可能来自硬编码关键词。
- `STRATEGY_MEMORY`：历史策略可能保存了旧领域偏差。
- `SYSTEM_RULES` / `TASK_INSTRUCTION` / `RISK_CONSTRAINTS`：如果 prompt 文案继续写死赛道词，也会污染下游。

后续需要由 `DOMAIN_PROFILE` 替换或校正的 slot：

- `COMPETITOR_EVIDENCE`：标题模式、内容支柱、人设、封面模式、结构模式中的领域词。
- `COMMENT_INSIGHT`：评论需求、痛点、转化词、风险词中的领域关键词。
- `WORKFLOW_STATE`：content opportunity、experiment format_hint、selected_topic 中的赛道默认值。
- `RISK_CONSTRAINTS`：领域风险从 `domain_profile.risk_keywords` 或风险配置注入。
- `TASK_INSTRUCTION` / prompt 文案：账号定位、人群表达不要继续写死在 system prompt。

## 6. DOMAIN_PROFILE 设计

`DOMAIN_PROFILE` 不是手写多行业词表，而是未来由用户账号画像 + 真实样本 + 人工确认生成的统一领域画像。它的目标是把“账号适合什么领域、目标人群怎么表达、用户痛点和转化词是什么、哪些词不能用”从分散代码和 prompt 文案中拿出来，变成可版本化、可审计、可回滚的上下文输入。

建议结构：

```json
{
  "domain_keywords": [],
  "audience_keywords": [],
  "pain_point_keywords": [],
  "conversion_keywords": [],
  "title_pattern_keywords": {},
  "risk_keywords": [],
  "negative_keywords": [],
  "source": "account_profile/manual/llm/sample_calibrated",
  "human_confirmed": false,
  "version": "v1"
}
```

字段说明：

| 字段 | 作用 |
|---|---|
| `domain_keywords` | 账号领域核心词，例如赛道、服务、主题、产品类别 |
| `audience_keywords` | 目标人群表达，例如身份、阶段、城市、需求场景 |
| `pain_point_keywords` | 用户痛点词，用于标题、正文切入和评论洞察 |
| `conversion_keywords` | 转化信号词，例如咨询、预约、领取、报价、试用 |
| `title_pattern_keywords` | 按标题模式组织的领域词，如痛点型、结果展示型、避坑型、清单型 |
| `risk_keywords` | 领域风险词和需要谨慎处理的承诺 |
| `negative_keywords` | 明确不属于本账号、不希望采集或生成的词 |
| `source` | 生成来源，区分账号画像、人工录入、LLM 候选、样本校正 |
| `human_confirmed` | 是否经人工确认后可进入生产默认链路 |
| `version` | 领域画像版本，用于回放、评估和回滚 |

不能继续把“大学生 / Agent / 简历 / 面试”写死在代码里，原因是这些词只适配当前学习求职类账号。换成摄影接单、健身教练、本地生活、B2B 服务后，这些词会污染关键词采集、竞品分析、标题模式、实验变量和草稿表达，使系统在源头样本和下游 prompt 上连续偏航。

也不建议手写 `photography / fitness / beauty` 等行业词表。手写多行业词表会快速膨胀，难以覆盖具体账号定位，也无法跟随用户所在城市、客单价、产品形态、风险偏好和真实样本变化。更好的方式是保留通用结构规则，把领域词作为每个账号自己的动态画像。

`domain_profile` 需要版本号，因为领域画像会随着账号定位、样本范围、人工确认、发布反馈和复盘结论变化。版本号可以让每次 draft/review 的 ContextSnapshot 复现当时用的是哪一版领域词，也方便比较“v1 学习类表达”和“v2 本地服务表达”的效果，必要时回滚。

`domain_profile` 需要人工确认，因为领域词直接影响生产内容和风险判断。尤其是目标人群、转化词、禁用词、风险词，如果只靠自动推断，可能把用户不想要的方向写进默认链路。人工确认可以把候选画像从“建议”提升为“可用于生产”。

`domain_profile` 需要和竞品样本校正，因为单靠账号画像容易主观化。真实竞品笔记的标题、评论、标签、互动数据和转化线索能暴露用户真实说法，例如同一摄影账号可能更该强调“档期 / 客片 / 修图周期”，而不是泛泛的“摄影技巧”。样本校正可以让领域词贴近市场语言。

未来进入 `content_draft_v2` 的方式：

- 在 `_build_context` 阶段读取当前账号已确认的 `domain_profile` 摘要，不在本阶段实现数据来源。
- 在 `_build_llm_context` 阶段新增独立 `DOMAIN_PROFILE` slot，优先级建议低于 `ACCOUNT_PROFILE`、高于 `WORKFLOW_STATE` 或与其接近。
- slot metadata 记录 `source`、`version`、`human_confirmed`、`source_sample_count`、`data_status`。
- 如果 `human_confirmed=false`，只作为低置信候选或不进入生产默认链路，具体策略放到后续实现阶段。
- `DOMAIN_PROFILE` 不替代 `ACCOUNT_PROFILE`，而是从账号画像派生出来，服务于领域词、标题词、转化词和风险词治理。

## 7. Snapshot 和可观测性设计

后续每个 slot 都应在 ContextSnapshot / ContextSlotLog 或等价结构中记录：

- `slot_name`
- `source`
- `chars`
- `rough_tokens`
- `priority`
- `truncated`
- `compressed`
- `data_status`
- `contains_hardcoded_domain_terms`
- `source_version`

建议补充语义：

| 字段 | 建议含义 |
|---|---|
| `source` | `prompt_template`、`account_profile`、`domain_profile`、`competitor_report`、`competitor_analysis`、`content_experiment_v2`、`manual_input` 等 |
| `data_status` | `READY`、`PARTIAL`、`EMPTY`、`MOCK`、`UNCONFIRMED` |
| `contains_hardcoded_domain_terms` | 标记 slot 内容是否含第 5.2 扫描出的当前赛道硬编码词 |
| `source_version` | prompt version、domain_profile version、report id/version、experiment id/version 等 |

`COMPETITOR_EVIDENCE` 和 `COMMENT_INSIGHT` 如果包含外部文本，应保持 untrusted 语义，避免评论或竞品正文被模型当成系统指令。`DOMAIN_PROFILE` 如果未人工确认，应在 snapshot 中保留 `human_confirmed=false` 和来源。

## 8. 第 5.4 Token Budget 前置建议

| Slot | 预算优先级 | 第 5.4 建议 |
|---|---|---|
| `SYSTEM_RULES` | 必须保留 | 不压缩、不截断，只去重 |
| `TASK_INSTRUCTION` | 必须保留 | 不压缩，保持任务动作明确 |
| `OUTPUT_SCHEMA` | 必须保留 | 保留 schema 核心，字段说明可控长 |
| `RISK_CONSTRAINTS` | 必须保留 | 通用风险和领域高风险必须完整保留 |
| `ACCOUNT_PROFILE` | 必须保留 | 可做短摘要，但关键定位、目标人群、目标和禁用项必须保留 |
| `DOMAIN_PROFILE` | 必须保留 / 可压缩 | 保留 version、确认状态、核心词；长尾词可截断 |
| `DRAFT_CONTENT` | 必须保留 | 待审核正文核心不压缩，历史 generation_context 可摘要 |
| `WORKFLOW_STATE` | 可压缩 | 保留当前实验、机会标题、假设、主指标和风险等级 |
| `COMPETITOR_EVIDENCE` | 可压缩 / 可截断 | 第 5.5 做 Top-K，优先高表现、强相关、低风险证据 |
| `COMMENT_INSIGHT` | 可压缩 / 可截断 | 保留需求分类、计数、代表评论，评论原文 Top-K |
| `STRATEGY_MEMORY` | 可压缩 / 可缺省 | 按置信度、新鲜度、同领域匹配筛选 |
| `USER_INPUT` | 可截断 | 保留本轮明确约束，长文本只截断不改写语义 |

第 5.4 只应定义预算和统计口径，不在本阶段实现压缩。第 5.5 再处理 `COMPETITOR_EVIDENCE`、`COMMENT_INSIGHT`、`STRATEGY_MEMORY` 的摘要和 Top-K。

## 9. 后续实施顺序

1. 先让 `content_draft_v2` 输出 slot 级统计，并补齐 `DOMAIN_PROFILE`、`COMPETITOR_EVIDENCE`、`COMMENT_INSIGHT` 的设计接入点。
2. 再接 `review_report`，把 `DRAFT_CONTENT`、`ACCOUNT_PROFILE`、`DOMAIN_PROFILE`、`RISK_CONSTRAINTS`、`OUTPUT_SCHEMA` 拆清楚。
3. 再逐步把旧 `content_draft` 对齐到同一套 slot 名称，但暂不优先大改旧链路。
4. 再设计 `domain_profile` schema、确认状态、版本号和来源记录。
5. 最后处理 `competitor_report` / `competitor_analysis` 中的硬编码领域词，把通用结构规则和账号领域词拆开。

P0 接入优先级：

- 第一优先：`content_draft_v2`。它已经有 `ContextManager`、`ContextSnapshot`，最适合做 slot 级统计和 token budget。
- 第二优先：`review_report`。审核需要 `ACCOUNT_PROFILE`、`DOMAIN_PROFILE`、`RISK_CONSTRAINTS`、`OUTPUT_SCHEMA`，也需要明确 `DRAFT_CONTENT`。
- 第三优先：旧 `content_draft`。旧链路可以暂时保留，后续按 slot 命名对齐。

P1 接入优先级：

- `competitor_report` / `competitor_analysis`：先标记输出字段属于 `COMPETITOR_EVIDENCE`、`COMMENT_INSIGHT` 或 `WORKFLOW_STATE`，暂不重构规则。
- `content_experiment_v2`：先标记实验卡字段属于 `WORKFLOW_STATE`，暂不重构实验变量。

## 10. 结论

- 第 5.3 不实现压缩，只完成 Context Slot 分槽设计。
- 第 5.4 才做 token budget 和 slot 级预算统计。
- 第 5.5 才做压缩、摘要和 Top-K。
- `domain_profile` 暂不自动生成，后续单独设计 schema、版本、人工确认和样本校正流程。
- 当前第一版统一 slot 建议包含：`SYSTEM_RULES`、`TASK_INSTRUCTION`、`USER_INPUT`、`ACCOUNT_PROFILE`、`DOMAIN_PROFILE`、`WORKFLOW_STATE`、`COMPETITOR_EVIDENCE`、`COMMENT_INSIGHT`、`STRATEGY_MEMORY`、`RISK_CONSTRAINTS`、`OUTPUT_SCHEMA`、`DRAFT_CONTENT`。
- 本设计不要求本轮修改 `ContextSlotName` enum；代码接入留到后续实施阶段。
