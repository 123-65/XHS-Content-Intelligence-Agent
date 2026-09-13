# 第 5.5.2 Context 压缩与 Top-K 策略设计

## 1. 设计目的

第 5.5.1 已经让 `content_draft_v2` 的每个上下文槽位可以记录 `budget_meta`，也就是能看见每个槽位的字符数、粗略 token 数、预算上限、是否超预算、是否可压缩、是否可截断等信息。

但是第 5.5.1 只解决了“看得见”的问题，还没有解决“超预算后怎么办”的问题。例如：

- `COMPETITOR_EVIDENCE` 超预算时，是删低赞笔记，还是只保留最相关的爆款拆解？
- `COMMENT_INSIGHT` 超预算时，是保留全部评论，还是保留需求分类和代表评论？
- `STRATEGY_MEMORY` 超预算时，是按时间取最新，还是按置信度和领域匹配度筛选？

第 5.5.2 的目的，就是把这些处理规则先设计清楚。这样后续第 5.5.3 真正写代码时，就不是“看到长文本就随便截断”，而是按槽位类型、业务价值和风险优先级处理。

本阶段的核心结论是：

1. `COMPETITOR_EVIDENCE` 优先做 Top-K。
2. `COMMENT_INSIGHT` 优先做摘要加代表评论保留。
3. `STRATEGY_MEMORY` 优先按同领域、置信度、新鲜度和结果验证筛选。
4. `SYSTEM_RULES`、`TASK_INSTRUCTION`、`OUTPUT_SCHEMA`、`RISK_CONSTRAINTS` 不做语义压缩。

## 2. 本阶段边界

本阶段只做策略设计，不做代码实现。

本阶段不做：

- 不修改业务 service 逻辑。
- 不修改 prompt 文案。
- 不修改 LLMClient。
- 不新增 Agent。
- 不重构 workflow。
- 不新增数据库字段。
- 不新增 migration。
- 不调用真实 LLM。
- 不连接数据库。
- 不实现真正压缩算法。
- 不实现 Top-K 代码。
- 不替换硬编码领域词。
- 不实现 `domain_profile` 自动生成。
- 不修改前端。
- 不删除已有测试。

本阶段只新增设计文档。后续第 5.5.3 才考虑把规则写进 `context_compressor`、`ContextManager` 或 `content_draft_v2` 相关上下文构建流程。

## 3. Slot 压缩分级

不同槽位承担的责任不同，不能用同一种方式压缩。

| Slot | 压缩等级 | 处理方式 | 是否允许丢弃 | 风险 |
|---|---|---|---|---|
| `SYSTEM_RULES` | 不压缩，只保留 | 完整保留系统边界和行为规则 | 否 | 压缩后模型可能不遵守系统边界 |
| `TASK_INSTRUCTION` | 不压缩，只保留 | 完整保留本次任务目标、动作和范围 | 否 | 压缩后模型可能不知道本次要做什么 |
| `OUTPUT_SCHEMA` | 不压缩，只保留 | 保留 JSON schema、字段名、类型和必填约束 | 否 | 压缩后结构化输出可能校验失败 |
| `RISK_CONSTRAINTS` | 不压缩，只保留 | 保留通用风险、平台风险和领域风险核心规则 | 否 | 压缩后可能漏掉违规承诺或风险判断 |
| `ACCOUNT_PROFILE` | 可轻量压缩 | 保留账号定位、目标用户、账号目标、禁用项、语气 | 否 | 丢核心字段会导致内容不符合账号定位 |
| `DOMAIN_PROFILE` | 可轻量压缩 | 保留版本、人工确认状态、核心领域词、风险词、转化词 | 否 | 未确认或过期领域词会带偏生成和审核 |
| `WORKFLOW_STATE` | 可轻量压缩 / 可截断 | 保留选题、实验假设、主指标、风险等级、当前机会 | 否 | 丢当前实验目标会导致草稿和实验脱节 |
| `DRAFT_CONTENT` | 可轻量压缩 / 可截断 | 审核时保留标题、正文、标签、CTA；生成上下文可摘要 | 审核任务否 | 截断待审正文核心会导致审核失真 |
| `COMPETITOR_EVIDENCE` | 优先 Top-K | 按可信度、相关性、互动表现、多样性、新鲜度筛选 | 可丢低价值样本 | 全量塞入会挤占更关键的槽位 |
| `COMMENT_INSIGHT` | 优先摘要 | 保留高频需求、代表评论、转化信号、风险点 | 可丢重复评论 | 评论原文过多会引入噪声和不可信文本 |
| `STRATEGY_MEMORY` | 优先筛选 | 按同领域、置信度、新鲜度、结果验证筛选 | 可丢低置信和过期记忆 | 过期或错领域记忆会放大历史错误 |
| `USER_INPUT` | 可截断 | 保留用户本轮明确要求，长文本只截断不改写语义 | 可丢冗余尾部 | 截断错误会改变用户真实意图 |

### 3.1 不压缩，只保留

以下槽位不能做语义压缩：

- `SYSTEM_RULES`
- `TASK_INSTRUCTION`
- `OUTPUT_SCHEMA`
- `RISK_CONSTRAINTS`

原因是它们分别控制系统边界、任务目标、输出结构和风险规则。它们不是“参考材料”，而是模型必须遵守的框架。压缩它们可能导致模型跑偏、输出格式错误或风险判断失效。

### 3.2 可轻量压缩

以下槽位可以压缩，但不能丢核心字段：

- `ACCOUNT_PROFILE`
- `DOMAIN_PROFILE`
- `WORKFLOW_STATE`
- `DRAFT_CONTENT`

处理原则：

- `ACCOUNT_PROFILE`：保留账号定位、目标用户、账号目标、禁用项、语气偏好。
- `DOMAIN_PROFILE`：保留 `version`、`human_confirmed`、核心领域词、风险词、转化词。
- `WORKFLOW_STATE`：保留 `selected_topic`、`hypothesis`、`primary_metric`、`risk_level`、当前机会摘要。
- `DRAFT_CONTENT`：审核时保留 `title`、`body`、`tags`、`cta`；历史 `generation_context` 可以摘要。

### 3.3 优先 Top-K / 摘要

以下槽位是第 5.5.3 的优先处理对象：

- `COMPETITOR_EVIDENCE`
- `COMMENT_INSIGHT`
- `STRATEGY_MEMORY`

原因是它们通常来自上游报告、评论样本和历史策略，会随着数据量增长不断变长。如果不治理，它们最容易把上下文窗口占满。

### 3.4 可截断

以下槽位过长时可以截断：

- `USER_INPUT`
- `WORKFLOW_STATE`
- `DRAFT_CONTENT`

但有两个限制：

1. `USER_INPUT` 截断不能改写用户语义，只能保留明确要求并截掉冗余尾部。
2. `DRAFT_CONTENT` 在审核任务中不能截断正文核心，只能截断历史生成上下文或低价值附加信息。

## 4. COMPETITOR_EVIDENCE Top-K 策略

### 4.1 为什么要 Top-K

`COMPETITOR_EVIDENCE` 承载竞品笔记、爆款拆解、标题模式、内容支柱、封面模式、内容结构和证据来源。它的问题是：数据价值高，但数量很容易膨胀。

如果把所有竞品证据都塞进 LLM，会出现四个问题：

1. token 被竞品样本占满，挤占账号画像、任务说明和输出结构。
2. 低质量样本和高质量样本混在一起，模型难以判断重点。
3. 重复标题模式或同一内容支柱会放大偏差。
4. 外部文本可能包含不可信内容，增加 prompt injection 和噪声风险。

所以 `COMPETITOR_EVIDENCE` 不适合“全量保留”，更适合做 Top-K：只选最可信、最相关、表现最好、类型最多样、风险最低的一小批证据。

### 4.2 候选输入字段

候选字段包括：

- `high_performance_notes`
- `viral_note_breakdowns`
- `title_patterns`
- `content_pillars`
- `cover_patterns`
- `content_structures`
- `evidence_summary`
- `note_url`
- `like_count`
- `collect_count`
- `comment_count`
- `confidence`
- `source_type`
- `is_mock`
- `data_status`

### 4.3 排序规则

建议按以下顺序排序：

1. 数据可信度优先。
   - `REAL`、`MANUAL`、`MCP` 优先。
   - `SEED_SAMPLE`、`MOCK` 不进入生产默认链路。

2. 相关性优先。
   - 与 `selected_topic` 更相关的证据优先。
   - 与 `ACCOUNT_PROFILE` 的账号定位、人群、目标更相关的优先。
   - 与 `DOMAIN_PROFILE` 的领域词、痛点词、转化词更相关的优先。

3. 互动表现优先。
   - `collect_count` 高的优先，因为收藏通常表示内容可复用或用户需求强。
   - `like_count` 高的优先，表示标题和内容有吸引力。
   - `comment_count` 高的优先，表示有讨论或需求线索。

4. 证据多样性优先。
   - 不要全选同一种标题模式。
   - 不要全选同一个 `content_pillar`。
   - 不要全选同一个作者或同一种内容结构。

5. 新鲜度优先。
   - 如果有发布时间、采集时间或更新时间，较新的优先。
   - 没有时间字段时，不强行推断新鲜度。

6. 风险过滤。
   - 高风险样本不进入核心证据。
   - 风险样本可以进入 `risk warning`，提醒模型不要模仿。

### 4.4 过滤规则

建议先过滤，再排序：

1. 过滤 `is_mock=true` 的样本。
2. 过滤 `source_type=SEED_SAMPLE` 或明显测试来源的样本。
3. 过滤 `data_status=MOCK`、`DATA_NOT_PROVIDED`、`UNCONFIRMED` 且没有人工确认的样本。
4. 过滤与当前账号领域明显不匹配的样本。
5. 高风险样本不作为正向模仿证据，只作为风险提醒。

### 4.5 保留数量

建议输出：

- Top 3 到 5 条核心竞品证据。
- 2 到 3 个标题模式。
- 2 到 3 个内容支柱。
- 1 个 `evidence_summary`。
- 可选：1 到 2 条风险提醒，不进入正向模仿样本。

### 4.6 输出摘要结构

建议第 5.5.3 输出类似结构：

```json
{
  "selected_notes": [],
  "title_patterns": [],
  "content_pillars": [],
  "evidence_summary": "",
  "risk_warnings": [],
  "dropped_reason_summary": ""
}
```

### 4.7 风险说明

`COMPETITOR_EVIDENCE` 里的原始竞品标题、正文和评论都属于外部文本，不应该被模型当成系统指令。后续实现时，如果原文进入 prompt，应继续保持不可信来源标记。

第 5.5.2 只设计规则，第 5.5.3 再实现 Top-K 代码。

## 5. COMMENT_INSIGHT 摘要策略

### 5.1 为什么要摘要

`COMMENT_INSIGHT` 承载评论需求、代表评论、痛点、转化信号和风险点。评论的价值很高，因为它能告诉我们用户真实在问什么、担心什么、想要什么。

但评论也有三个问题：

1. 评论数量可能很多，原文全量进入 LLM 会快速超预算。
2. 评论属于外部不可信文本，可能包含诱导、攻击、营销或无关内容。
3. 多条评论可能表达同一个需求，全量保留会重复消耗 token。

所以 `COMMENT_INSIGHT` 更适合“摘要加代表评论”：先把评论归类，再每类保留少量代表样本。

### 5.2 候选输入字段

候选字段包括：

- `comment_demands`
- `comment_examples`
- `conversion_signals`
- `risk_points`
- `pain_points`
- `comment_count`
- `demand_count`
- `confidence`

### 5.3 高频需求保留

优先保留高频需求分类，例如：

- 路线需求：用户想知道步骤、路径、先后顺序。
- 价格需求：用户关心报价、成本、性价比。
- 咨询需求：用户想私信、预约、获得进一步建议。
- 案例需求：用户想看真实案例、样板、结果展示。
- 资源需求：用户想要清单、模板、源码、资料。

需求分类应该保留：

- 分类名称。
- 出现次数。
- 代表性说明。
- 置信度。

### 5.4 代表评论保留

每个高频需求分类保留 1 到 2 条代表评论即可。

代表评论选择原则：

1. 能清楚表达用户需求。
2. 不包含明显攻击、诱导或违规内容。
3. 不重复表达同一个意思。
4. 优先保留点赞较高或更具体的评论。

注意：评论属于外部不可信文本，后续进入 prompt 时要标记为不可信数据，不能让评论原文变成模型指令。

### 5.5 转化信号保留

需要保留转化信号摘要，例如：

- 求资料。
- 求报价。
- 想咨询。
- 想预约。
- 求模板。
- 想看案例。

转化信号的作用是帮助草稿设计 CTA，但不能变成强诱导、夸大承诺或违规营销。

### 5.6 风险点保留

需要保留风险点摘要，例如：

- 焦虑营销。
- 虚假承诺。
- 隐私授权。
- 价格误导。
- 过度承诺效果。
- 引导评论或私信过强。

风险点可以进入 `RISK_CONSTRAINTS` 或 `COMMENT_INSIGHT.risk_summary`，提醒生成链路不要模仿高风险表达。

### 5.7 数据不足处理

如果评论样本太少，不应该假装有充分洞察。建议标记：

- `DATA_INSUFFICIENT`
- `COMMENT_SAMPLE_INSUFFICIENT`

触发场景：

- 评论总量低于最低样本阈值。
- 评论分类置信度过低。
- 评论来源是 mock、seed 或未确认数据。

### 5.8 建议输出结构

建议第 5.5.3 输出：

```json
{
  "demand_summary": [],
  "representative_comments": [],
  "conversion_signal_summary": [],
  "risk_summary": [],
  "data_status": "REAL/PARTIAL/DATA_INSUFFICIENT"
}
```

## 6. STRATEGY_MEMORY 筛选策略

### 6.1 为什么要筛选

`STRATEGY_MEMORY` 承载历史策略、复盘结论和已验证表达。它的价值是：系统可以记住过去哪些表达有效、哪些表达失败，避免每次从零开始。

但策略记忆也有风险：

1. 旧策略可能已经过期。
2. 某个领域有效的策略，不一定适合另一个领域。
3. 低置信记忆可能会放大历史错误。
4. 如果把所有记忆都塞进 prompt，会让模型被旧信息拖偏。

所以 `STRATEGY_MEMORY` 应该筛选，不应该全量进入 prompt。

### 6.2 候选输入字段

候选字段包括：

- `memory_type`
- `summary`
- `pattern`
- `confidence`
- `usage_snapshot`
- `usage_reason`
- `updated_at`
- `source_version`
- `domain_profile_version`
- `result_metric`
- `success_or_failure`

### 6.3 筛选规则

建议按以下优先级筛选：

1. 同领域优先。
   - `domain_profile_version` 与当前账号匹配的优先。
   - 领域标签、目标人群、转化目标一致的优先。
   - 不同领域的记忆不应该直接复用。

2. 高置信度优先。
   - `confidence` 高的策略优先。
   - 低置信策略可以保留为候选，但不应大量进入 prompt。

3. 新鲜度优先。
   - `updated_at` 较新的优先。
   - 太旧的策略需要降权或标记 `STALE`。

4. 有结果验证优先。
   - 有发布后数据、复盘结论、转化指标或明确成功/失败标记的优先。
   - 没有结果验证的记忆，不应和已验证记忆同等权重。

5. 失败经验也要保留少量。
   - 保留 1 到 2 条失败经验，避免重复犯错。
   - 失败经验应该以“不要做什么”的形式进入摘要，而不是作为正向模仿样本。

### 6.4 低置信 / 过期记忆处理

低置信、过期、不同领域的记忆可以这样处理：

- 不进入主策略列表。
- 只进入 `dropped_reason_summary`。
- 如果有强风险价值，可以进入风险提醒。
- 如果完全无关，则不进入本次 prompt。

### 6.5 建议输出结构

建议第 5.5.3 输出：

```json
{
  "selected_success_memories": [],
  "selected_failure_memories": [],
  "strategy_summary": "",
  "confidence_summary": "",
  "dropped_reason_summary": ""
}
```

建议保留数量：

- 3 到 5 条有效策略。
- 1 到 2 条失败经验。
- 1 个 `strategy_summary`。
- 1 个 `confidence_summary`。

## 7. 压缩后 metadata 字段设计

第 5.5.1 已经有 `budget_meta`。第 5.5.3 真正实现压缩或 Top-K 后，不新增数据库字段，仍然优先写入已有 JSON 字段，例如：

- `ContextSlotLog.metadata_payload.budget_meta`
- `ContextSnapshot.slot_token_breakdown`
- 其他已有可观测 JSON 字段

建议新增或更新以下字段：

| 字段 | 作用 |
|---|---|
| `compressed` | 当前槽位是否已经做过摘要压缩或筛选压缩。 |
| `truncated` | 当前槽位是否发生过截断。截断是直接裁掉一部分内容，和摘要压缩不同。 |
| `compression_method` | 使用了什么处理方法，例如 `top_k_rule`、`rule_summary`、`field_filter`、`recency_filter`、`manual_keep`。 |
| `before_chars` | 压缩或筛选前的字符数。 |
| `after_chars` | 压缩或筛选后的字符数。 |
| `before_rough_tokens` | 压缩或筛选前的粗略 token 数。 |
| `after_rough_tokens` | 压缩或筛选后的粗略 token 数。 |
| `selected_count` | 被选中保留的记录数量，例如 Top-K 后保留了 5 条竞品证据。 |
| `dropped_count` | 被丢弃或未进入 prompt 的记录数量。 |
| `drop_reason` | 丢弃原因摘要，例如“低相关性”“mock 数据”“过期记忆”“风险过高”。 |
| `top_k` | 本次 Top-K 的 K 值，例如 3、5。 |
| `summary_generated` | 是否生成了摘要。规则摘要或 LLM 摘要都可以记录为 true，但要在 `compression_method` 区分方法。 |
| `warning` | 压缩、截断、数据不足、样本不可信、领域不匹配等提示。 |

字段说明：

- `compressed`：说明这个槽位是否被压缩过。Top-K 也是一种压缩，因为它从多条候选中只保留少量高价值内容。
- `truncated`：说明是否直接截断文本。截断风险比摘要更高，因为可能截掉关键语义。
- `compression_method`：说明具体处理方式，方便后续排查效果。
- `before_chars` / `after_chars`：用字符数观察压缩前后的长度变化。
- `before_rough_tokens` / `after_rough_tokens`：用粗略 token 观察预算变化。
- `selected_count`：说明保留了多少条。
- `dropped_count`：说明丢掉了多少条。
- `drop_reason`：说明为什么丢弃，避免以后不知道系统删了什么。
- `top_k`：记录 Top-K 参数，方便复现实验。
- `summary_generated`：说明是否生成摘要。
- `warning`：记录风险提示，例如评论样本不足、硬编码领域词未替换、策略记忆过期。

## 8. 硬编码领域词处理原则

本阶段仍然不替换硬编码领域词，只设计处理策略。

### 8.1 出现在 COMPETITOR_EVIDENCE 中

如果硬编码领域词出现在 `COMPETITOR_EVIDENCE`：

- 标记 `contains_hardcoded_domain_terms=true`。
- 标记来源，例如 `source=rule_based` 或 `source=prompt_template`。
- 不直接删除。
- 后续等待 `DOMAIN_PROFILE` 替换或校正。

原因是竞品证据可能既包含真实样本，也包含规则输出。如果立刻删除，可能误删真实市场语言；如果不标记，后续又无法追踪偏差来源。

### 8.2 出现在 COMMENT_INSIGHT 中

如果硬编码领域词出现在 `COMMENT_INSIGHT`：

- 标记来源。
- 不直接删除。
- 摘要时不要把硬编码词当成跨行业通用规律。
- 后续由 `DOMAIN_PROFILE` 校正。

例如“项目”“简历”“面试”可能适合学习求职账号，但不适合摄影接单账号。评论洞察必须区分“真实评论里出现”和“规则分类里写死”。

### 8.3 出现在 STRATEGY_MEMORY 中

如果硬编码领域词出现在 `STRATEGY_MEMORY`：

- 检查 `domain_profile_version`。
- 检查当前账号领域是否匹配。
- 不同领域账号不应直接复用。
- 可以保留为历史记忆，但不一定进入当前 prompt。

例如学习求职账号的“简历项目标题策略”，不能直接复用到本地摄影账号。

## 9. 第 5.5.3 实施建议

第 5.5.3 建议按确定性规则逐步实现，不要一上来做 LLM 摘要。

建议顺序：

1. 先实现 `COMPETITOR_EVIDENCE` 的确定性 Top-K。
   - 先按 `is_mock`、`source_type`、`data_status` 过滤。
   - 再按相关性、互动表现、多样性排序。
   - 不调用 LLM。

2. 再实现 `STRATEGY_MEMORY` 筛选。
   - 按同领域、置信度、新鲜度、结果验证筛选。
   - 保留少量失败经验。

3. 再实现 `COMMENT_INSIGHT` 规则摘要。
   - 先做需求分类统计。
   - 每类保留 1 到 2 条代表评论。
   - 保留转化信号和风险点。

4. 最后才考虑 LLM 摘要压缩。
   - 只有当规则摘要不足以表达复杂信息时，再考虑 LLM 摘要。
   - LLM 摘要会增加成本和不稳定性，不应该作为第一步。

这个顺序的好处是：先用确定性规则建立稳定基线，再考虑更复杂的摘要能力。这样更容易测试、回放和解释。

## 10. 当前可写进简历的表达

当前只能写设计，不写优化百分比。

可写：

> 设计 Context 压缩与 Top-K 策略，将竞品证据、评论洞察、策略记忆拆分为可筛选上下文来源，基于数据可信度、相关性、互动表现、置信度和新鲜度制定上下文保留规则，为后续降低 token 成本和提升生成质量提供依据。

不能写：

- token 降低 xx%
- 成本下降 xx%
- 延迟降低 xx%
- 输出质量提升 xx%

原因是第 5.5.2 只做策略设计，还没有实现压缩、Top-K、对比实验和线上指标采集。

## 11. 结论

1. `COMPETITOR_EVIDENCE` 是第一个应该做 Top-K 的槽位，因为它数据量大、证据价值高，但也最容易超预算。
2. `COMMENT_INSIGHT` 应该做摘要加代表评论保留，因为评论原文数量多且属于不可信外部文本。
3. `STRATEGY_MEMORY` 应该按同领域、置信度、新鲜度和结果验证筛选，避免低置信、过期、错领域记忆影响生成。
4. `SYSTEM_RULES`、`TASK_INSTRUCTION`、`OUTPUT_SCHEMA`、`RISK_CONSTRAINTS` 不应该做语义压缩。
5. `ACCOUNT_PROFILE`、`DOMAIN_PROFILE`、`WORKFLOW_STATE`、`DRAFT_CONTENT` 可以轻量压缩，但不能丢核心字段。
6. `USER_INPUT`、`WORKFLOW_STATE`、`DRAFT_CONTENT` 可以在保留核心语义后截断。
7. 压缩后仍然不新增数据库字段，优先写入已有 JSON metadata。
8. 第 5.5.2 不改代码，只为第 5.5.3 实现做准备。
