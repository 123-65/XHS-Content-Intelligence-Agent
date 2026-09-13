# 第 5.2 Context 输入规模统计报告

## 1. 统计目的

本报告用于统计草稿生成、审核报告等真实 LLM 入口的 prompt/context 输入规模，并登记竞品分析、内容实验、策略记忆等上游结构化字段对下游 LLM context 的影响。

本阶段只统计，不优化，不改业务代码。

## 2. 统计范围

### P0：直接 LLM 业务入口

- content_draft_v2
- content_draft
- review_report

### P1：上游 context 来源

- competitor_report
- competitor_analysis
- content_experiment
- content_experiment_v2
- comment_insight
- strategy_memory
- context_engineering

### P2：只登记

- crawler_collection
- keyword_seed
- confirmation
- post_publish
- API route
- repository
- provider_health
- llm_infra

本次静态扫描 Python 文件数：219。

## 3. P0 LLM 入口统计表

| 模块 | 是否直接调用 LLM | 调用方式 | schema_model | prompt_key/version | system_prompt 来源 | context 来源 | 是否 ContextManager | 是否 PromptRunLog | 是否 ContextSnapshot | 模板字符数 | 模板粗略 token | 硬编码领域词 | 5.3 建议 |
|---|---|---|---|---|---|---|---|---|---|---:|---:|---|---|
| content_draft_v2 | 是 | generate_structured_with_context | DraftGenerateV2Result | xhs_draft_generation / v2.0 | backend/app/prompts/xhs_draft_v2.py | ContextManager / BuiltContext / ContextSnapshot | 是 | 是 | 是 | 1801 | 451 | Agent | 拆分 ACCOUNT_PROFILE / DOMAIN_PROFILE / WORKFLOW_STATE / OUTPUT_SCHEMA / STRATEGY_MEMORY |
| content_draft | 是 | generate_structured | DraftGenerateResult | xhs_writer_draft_generation / v1 | backend/app/prompts/xhs_writer.py | ordinary service context dict / build_xhs_writer_prompt(context) | 否 | 否 | 否 | 1247 | 561 | 大学生, Agent, AI Agent, 项目, 实战, 简历, 求职 | 拆分 ACCOUNT_PROFILE / DOMAIN_PROFILE / WORKFLOW_STATE / OUTPUT_SCHEMA / STRATEGY_MEMORY |
| review_report | 是 | generate_structured | DraftReviewResult | content_reviewer / v1 | backend/app/prompts/content_reviewer.py | ordinary service review context dict / build_content_reviewer_prompt(context) | 否 | 否 | 否 | 1260 | 522 | Agent, 项目 | 拆分 ACCOUNT_PROFILE / DOMAIN_PROFILE / WORKFLOW_STATE / OUTPUT_SCHEMA / STRATEGY_MEMORY |

## 4. P1 上游 context 来源统计表

| 模块 | 是否直接调用 LLM | 可能输出字段 | 是否进入下游 LLM context | 影响下游 | 硬编码领域词 | 风险 | 5.3 建议 |
|---|---|---|---|---|---|---|---|
| competitor_report | 否 | persona_patterns, content_pillars, top_tags, title_patterns, cover_patterns, content_structures, comment_demands, conversion_signals, risk_points, high_performance_notes, content_insights, suggestions, viral_note_breakdowns, content_opportunities | 是 | content_experiment, content_experiment_v2, content_draft, content_draft_v2 | 大学生, 小白, 新手, 零基础, 项目, 实战, 简历, 面试, 求职, 学习路线, 源码, github, 课程, 普通本科 | 硬编码领域词会影响下游标题、机会和草稿角度 | 第 5.3 设计 domain_profile / 字段来源标记 |
| competitor_analysis | 否 | top_tags, title_patterns, high_performance_notes, content_insights, suggestions, summary | 是 | content_experiment, content_draft | 大学生, 小白, 新手, 零基础, 项目, 实战, 简历, 面试, 求职 | 硬编码领域词会影响下游标题、机会和草稿角度 | 第 5.3 设计 domain_profile / 字段来源标记 |
| content_experiment | 否 | experiment_name, hypothesis, topic_angle, selected_topic, target_metric, target_values | 是 | content_draft, review_report, content_draft_v2 | Agent, 学习路线 | 实验选题和变量会进入草稿 context | 第 5.3 设计 domain_profile / 字段来源标记 |
| content_experiment_v2 | 否 | experiment_name, hypothesis, content_pillar, content_format, main_variable, control_variables, primary_metric, success_criteria, failure_criteria, fallback_strategy, topic_angle, selected_topic | 是 | content_draft_v2 | - | 实验选题和变量会进入草稿 context | 第 5.3 设计 domain_profile / 字段来源标记 |
| comment_insight | 否 | comment_demands, conversion_signals, risk_points, comment_examples | 是 | competitor_report, content_opportunity, content_experiment_v2, content_draft_v2 | 大学生, 小白, 新手, 零基础, 项目, 实战, 简历, 面试, 求职, 学习路线, 源码, github, 课程, 普通本科 | 硬编码领域词会影响下游标题、机会和草稿角度 | 第 5.3 设计 domain_profile / 字段来源标记 |
| strategy_memory | 否 | memory_type, summary, pattern, confidence, usage_snapshot, usage_reason | 是 | content_draft_v2, agent_runtime | Agent | 历史策略会被注入后续 context，需要置信和版本 | 第 5.3 设计 domain_profile / 字段来源标记 |
| context_engineering | 否 | BuiltContext, BuiltContextSlot, ContextSnapshot, ContextSlotLog, truncation_summary, sanitizer_summary | 是 | content_draft_v2 | Agent | 基础设施影响可观测性和 slot 统计 | 第 5.3 设计 domain_profile / 字段来源标记 |

## 5. 硬编码领域词进入 context 的风险

- `keyword_seed` 会影响采集源头；如果关键词围绕学习路线、项目、简历、求职生成，后续采集和竞品样本会偏向当前账号赛道。
- `competitor_report` / `competitor_analysis` 会影响标题模式、内容支柱、评论需求、机会生成；这些字段会进入内容实验和草稿上下文。
- `content_experiment` / `content_experiment_v2` 会影响选题、实验变量、成功标准和草稿的 workflow state。
- prompt 模板会直接影响 LLM 输出风格；旧 writer prompt 中的学生/自学者表达应在第 5.3 进入账号画像和领域画像设计。
- mock / seed / tests 中的领域词可保留，但必须标记为 demo/test，不进入生产默认链路。

生产代码命中的领域词：大学生, 小白, 新手, 零基础, Agent, AI Agent, 项目, 实战, 简历, 面试, 求职, 学习路线, 源码, github, 课程, 普通本科, 转码, 应届生

Prompt 模板命中的领域词：大学生, Agent

测试/demo 命中的领域词：大学生, 双非, 27届, 新手, Agent, AI Agent, 项目, 实战, 简历, 面试, 求职, 学习路线, 源码, github, 普通本科, 转码, 应届生

## 6. 当前不能写的指标

当前不能写：

- token 降低 xx%
- 延迟降低 xx%
- 成本下降 xx%
- 输出质量提升 xx%

原因：本阶段只统计优化前基线，还没有做 Context Slot、Token Budget 和压缩。

## 7. 后续第 5.3 建议

- 设计 `DOMAIN_PROFILE` slot。
- 区分 `ACCOUNT_PROFILE` 和 `DOMAIN_PROFILE`。
- 把硬编码领域词从生产 prompt / service 中逐步迁移到 `domain_profile`。
- `domain_profile` 需要版本号和人工确认状态。
- `content_draft_v2` 优先接入 slot 统计，因为它已经使用 ContextManager、PromptRunLog 和 ContextSnapshot。
- `competitor_report` 暂时不重构，但要登记哪些输出字段来自硬编码规则。

## 8. 后续第 5.4 建议

- 先给 `content_draft_v2` 设置 token budget。
- 对 competitor evidence 做 Top-K。
- 对 comment insight 做摘要。
- 对 strategy memory 做最近有效策略筛选。
- 对 prompt 中重复的账号定位进行去重。

## 9. 结论

1. 第 5.2 第一版统计对象是 `content_draft_v2`、`content_draft`、`review_report`。
2. `competitor_report` / `competitor_analysis` 当前不直接调用 LLM，但会影响下游 context，必须 P1 登记。
3. 硬编码领域词问题暂不修改，放到第 5.3 `domain_profile` / context slot 设计。
4. 本阶段不产生优化后指标，只产生优化前基线。
