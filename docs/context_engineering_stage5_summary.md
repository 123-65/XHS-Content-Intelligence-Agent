# 第 5 阶段 Context Engineering 总结

## 1. 阶段目标

第 5 阶段的目标不是简单优化 prompt。

更准确地说，第 5 阶段是在做一套 LLM 输入治理体系：把原本混在一起的上下文，拆成可观测、可预算、可压缩、可复盘的 Context Engineering 结构。

最终目标是让系统知道：

- 本次 LLM 到底用了哪些上下文；
- 每类上下文来自哪里；
- 每个 slot 大概占多少 token；
- 哪些 slot 超预算；
- 哪些 slot 被压缩、筛选或摘要；
- 哪些外部文本是不可信的；
- 某次草稿生成后，能不能回头复盘“模型当时看到了什么”。

所以第 5 阶段不是“把 prompt 写得更长”，而是把 prompt 前面的上下文输入工程化。

## 2. 为什么要做 Context Engineering

Agent 生成草稿时，不是只靠一句 prompt。

它实际依赖很多类上下文：

- 账号画像；
- 当前实验；
- 内容机会；
- 竞品证据；
- 评论洞察；
- 策略记忆；
- 风险规则；
- 输出 schema；
- 用户本轮补充要求。

如果这些上下文不治理，会出现这些问题：

- token 膨胀：所有信息都往 prompt 里塞，越跑越长；
- 竞品证据噪声大：低质量、重复或不相关竞品样本影响生成；
- 评论原文污染 prompt：评论属于外部文本，可能有诱导、攻击或无关内容；
- 旧策略记忆误导生成：历史策略可能过期、低置信或不适合当前领域；
- 硬编码领域词污染其他账号：比如某些 demo 赛道词会被带到不相关账号；
- 无法复盘某次生成：如果没有 snapshot，就不知道当时到底注入了哪些上下文。

Context Engineering 就是为了解决这些问题。

它把“上下文”从一个大字典，升级为一组有名称、有来源、有预算、有压缩策略、有审计记录的 slot。

## 3. 第 5.1 到第 5.6 分阶段总结

| 阶段 | 目标 | 产物 | 解决的问题 |
|---|---|---|---|
| 5.1.1 | 扫描 LLM / Context / Workflow 入口 | `docs/context_entrypoint_scan_report.md` | 搞清楚哪些模块构造 context、哪些调用 LLM、哪些会影响后续治理 |
| 5.1.2 | 修正第 5.2 统计范围 | 范围修正说明和统计口径调整 | 避免只看草稿生成，漏掉竞品报告、策略记忆、评论洞察等上游来源 |
| 5.2 | 统计 Context 输入规模 | `docs/context_input_size_baseline.md` | 建立优化前基线，知道模板、上下文、硬编码领域词大概规模 |
| 5.3 | 设计 Context Slot 分槽 | `docs/context_slot_design.md` | 明确不同上下文应该进入哪个 slot，以及哪些需要预算、压缩和 snapshot |
| 5.4 | 设计 Context Token Budget | `docs/context_token_budget_design.md` | 定义每类 slot 的预算、优先级、缺失策略、压缩策略方向 |
| 5.5.1 | 落地 slot 级 `budget_meta` | `context_budget.py`、`context_builder.py`、`context_usage_logger.py`、`docs/context_budget_5_5_1_implementation_report.md` | 每个 slot 都能记录 token 粗估、预算、是否超预算、数据状态等 metadata |
| 5.5.2 | 设计压缩 / Top-K 策略 | `docs/context_compression_strategy_5_5_2.md` | 明确竞品证据、评论洞察、策略记忆分别应该怎么治理 |
| 5.5.3 | 实现 `COMPETITOR_EVIDENCE` 确定性 Top-K | `context_compressor.py`、`context_builder.py`、`test_context_compressor.py`、`docs/context_topk_5_5_3_implementation_report.md` | 竞品证据不再全量注入，而是按规则筛选 |
| 5.5.4 | 接入真实竞品证据 | `content_draft_v2_sev.py`、`test_content_draft_v2.py`、`docs/context_evidence_slot_5_5_4_implementation_report.md` | `content_draft_v2` 真正把上游机会证据放入 `COMPETITOR_EVIDENCE` slot |
| 5.5.5 | 实现 `STRATEGY_MEMORY` 确定性筛选 | `context_compressor.py`、`context_builder.py`、`test_strategy_memory_filter.py`、`docs/context_strategy_memory_5_5_5_implementation_report.md` | 历史策略记忆按同领域、置信度、新鲜度、结果验证筛选 |
| 5.5.6 | 接入真实策略记忆 | `content_draft_v2_sev.py`、`test_content_draft_v2.py`、`docs/context_strategy_memory_slot_5_5_6_implementation_report.md` | `content_draft_v2` 能从真实 `StrategyMemory` 表读取记忆并以 `list[dict]` 注入 |
| 5.5.7 | 实现 `COMMENT_INSIGHT` 规则摘要 | `context_compressor.py`、`context_builder.py`、`content_draft_v2_sev.py`、`test_comment_insight_summary.py`、`docs/context_comment_insight_5_5_7_implementation_report.md` | 评论洞察不再全量塞入，而是保留高频需求、代表评论、转化信号和风险点 |
| 5.6 | ContextSnapshot 对比报告 | `backend/scripts/context_snapshot_report.py`、`backend/tests/test_context_snapshot_report.py`、`docs/context_snapshot_comparison_report.md` | 汇总 slot token、压缩方法、selected/dropped、data_status、trust_level 等工程指标 |

## 4. Context Slot 体系

第 5 阶段设计并逐步落地了一套 Context Slot 体系。

核心 slot 如下：

- `SYSTEM_RULES`：系统规则。控制模型行为边界，通常进入 system prompt。
- `TASK_INSTRUCTION`：任务说明。告诉模型这次要生成什么、scope 是什么、输出要求是什么。
- `USER_INPUT`：用户本轮输入。承载用户临时补充要求。
- `ACCOUNT_PROFILE`：账号画像。包含账号定位、内容领域、目标人群、人格、变现目标等。
- `DOMAIN_PROFILE`：领域画像。设计上用于承载领域词、风险词、转化词、版本信息等；当前还没有真正自动生成和完整接入。
- `WORKFLOW_STATE`：流程状态。包含当前实验、机会、账号 id、实验 id、机会 id 等流程信息。
- `COMPETITOR_EVIDENCE`：竞品证据。承载上游竞品报告、内容机会中的证据摘要和相关竞品信息。
- `COMMENT_INSIGHT`：评论洞察。承载评论需求、代表评论、转化信号、风险点。
- `STRATEGY_MEMORY`：策略记忆。承载历史策略、复盘结论、有效表达、失败经验。
- `RISK_CONSTRAINTS`：风险约束。承载不允许承诺、夸大收益、诱导评论等规则。
- `OUTPUT_SCHEMA`：输出结构。承载结构化输出 schema。
- `DRAFT_CONTENT`：草稿内容。主要用于后续审核、重写或 review 场景。

这套 slot 的意义是：后续不再把所有东西混成一个大 prompt，而是每类上下文都有明确的位置、来源、预算和治理策略。

## 5. content_draft_v2 当前 Context 数据流

当前 `content_draft_v2` 的上下文数据流可以理解成下面这条链：

`account / experiment / opportunity / competitor_report / comments / strategy_memory`

→ `content_draft_v2` 构造 `context_payload`

→ 拆成多个 `ContextSlot`

→ 交给 `ContextManager`

→ 每个 slot 生成 `budget_meta`

→ `COMPETITOR_EVIDENCE` 执行确定性 Top-K

→ `STRATEGY_MEMORY` 执行确定性筛选

→ `COMMENT_INSIGHT` 执行规则摘要

→ 写入 `ContextSnapshot / ContextSlotLog / PromptRunLog`

→ 调用 LLM structured call

更具体一点：

1. `account` 提供账号画像，进入 `ACCOUNT_PROFILE`。
2. `experiment` 和 `opportunity` 提供当前实验与机会状态，进入 `WORKFLOW_STATE`。
3. `opportunity` 和竞品报告沉淀出的证据进入 `COMPETITOR_EVIDENCE`。
4. 竞品报告中的评论需求、转化信号、风险点，以及真实评论样本进入 `COMMENT_INSIGHT`。
5. 数据库里的 `StrategyMemory` 进入 `STRATEGY_MEMORY`。
6. 风险规则进入 `RISK_CONSTRAINTS`。
7. 输出模型 schema 进入 `OUTPUT_SCHEMA`。
8. 构建完成后，所有 slot 的 metadata 会被记录到快照和日志里。

## 6. 三类重点上下文治理

### 6.1 COMPETITOR_EVIDENCE

来源：

- `ContentOpportunity`
- 上游竞品报告沉淀出的机会证据
- 实验信息中的辅助证据

为什么要 Top-K：

竞品证据可能很多，而且质量不一。如果全量进入 LLM，会带来 token 膨胀、重复证据、低质量证据污染生成等问题。

排序规则：

- 可信度优先；
- 与当前选题、账号关键词、内容支柱相关性优先；
- 互动表现优先；
- 新鲜度优先；
- 保持一定多样性；
- 过滤 mock、seed、failed、高风险样本。

metadata 记录：

- `compressed`
- `compression_method=deterministic_top_k`
- `selected_count`
- `dropped_count`
- `top_k`
- `before_rough_tokens`
- `after_rough_tokens`
- `drop_reason`

真实接入情况：

`content_draft_v2` 已经把真实机会证据接入 `COMPETITOR_EVIDENCE` slot，并在 `ContextSlotLog.metadata_payload["budget_meta"]` 中记录 Top-K metadata。

### 6.2 STRATEGY_MEMORY

来源：

- 数据库中的 `StrategyMemory` 表；
- 发布后复盘提取出的策略记忆；
- 历史有效表达、失败经验、策略 pattern。

为什么要筛选：

策略记忆会越来越多。如果不筛选，旧记忆、低置信记忆、错领域记忆会误导当前草稿生成。

筛选规则：

- 同领域优先；
- 高置信度优先；
- 新鲜度优先；
- 有结果验证优先；
- 保留少量失败经验；
- 过滤 mock、seed、failed、低置信、高风险记忆。

metadata 记录：

- `compressed`
- `compression_method=deterministic_strategy_memory_filter`
- `selected_count`
- `dropped_count`
- `top_k`
- `drop_reason`
- `before_rough_tokens`
- `after_rough_tokens`

真实接入情况：

`content_draft_v2` 已经能从真实 `StrategyMemory` 表读取当前账号记忆，并整理成 `list[dict]` 进入 `STRATEGY_MEMORY` slot，从而触发筛选。

### 6.3 COMMENT_INSIGHT

来源：

- `CompetitorAnalysisReport.comment_demands`
- `CompetitorAnalysisReport.conversion_signals`
- `CompetitorAnalysisReport.risk_points`
- `ContentOpportunity.comment_demand_type`
- `ContentOpportunity.risk_points`
- `CompetitorComment` 真实评论样本

为什么不能全量塞评论：

评论文本数量多、噪声大，而且属于外部不可信文本。全量塞入 prompt 会浪费 token，也可能引入 prompt injection 风险。

保留方式：

- 高频需求：按需求分类计数，保留高频类别；
- 代表评论：每类保留少量点赞较高或排序靠前的样本；
- 转化信号：保留求资料、求源码、想进群等信号；
- 风险点：保留夸大收益、强诱导评论等风险；
- 数据不足：样本太少时标记 `DATA_INSUFFICIENT` 或 warning。

为什么 `trust_level=UNTRUSTED`：

评论来自外部用户，不是系统规则，也不是开发者指令。它只能作为数据参考，不能被模型当成系统指令执行。

metadata 记录：

- `compressed`
- `compression_method=deterministic_comment_insight_summary`
- `summary_generated=true`
- `sample_count`
- `demand_count`
- `risk_count`
- `selected_count`
- `dropped_count`
- `warning`

## 7. ContextSnapshot 指标统计

第 5.6 新增了 `ContextSnapshot` 对比报告脚本，可以统计：

- slot token；
- over_budget；
- compression_method；
- selected_count；
- dropped_count；
- before / after rough token；
- data_status；
- trust_level；
- hardcoded domain terms；
- warning。

这些指标能说明：

- 系统已经具备上下文可观测性；
- 每个 slot 的成本和治理过程可以被记录；
- 外部文本是否被标记为 untrusted 可以被检查；
- 哪些上下文被压缩、筛选、摘要可以被复盘。

但它不能说明：

- 真实 token 成本已经下降了多少；
- 生成质量提升了多少；
- 转化率提升了多少；
- 延迟降低了多少。

原因是这些需要真实样本、多轮运行、稳定 before / after 数据和 Eval 支撑。

## 8. 当前已具备的工程能力

第 5 阶段结束后，项目已经具备这些能力：

- Context Slot 分槽；
- Token Budget；
- slot 级 `budget_meta`；
- 确定性 Top-K；
- 策略记忆筛选；
- 评论规则摘要；
- untrusted 外部文本标记；
- ContextSnapshot 可复盘；
- ContextSlotLog 记录每个 slot 的注入情况；
- PromptRunLog 记录上下文摘要；
- 统计脚本汇总上下文治理指标；
- 对核心能力有测试覆盖。

从工程角度看，这已经不是单纯“prompt 拼接”，而是一套可审计的 LLM 上下文治理层。

## 9. 当前限制

目前仍然有这些限制：

- `DOMAIN_PROFILE` 还没有真正生成和接入；
- 旧 `content_draft` / `review_report` 还没有完全迁移到新 slot 体系；
- `token_saved` 目前是 rough estimate，不是真实 tokenizer 统计；
- 还没有基于真实多轮样本计算百分比优化；
- 硬编码领域词目前只是标记，还没有替换；
- 还不是成熟多 Agent 自治系统；
- 目前更多是 `AgentRuntime + Workflow + LLM-powered service` 的渐进式架构；
- 还没有把上下文治理指标和最终内容质量、转化结果做 Eval 关联。

这些限制不能回避。面试时诚实说明，反而会显得工程判断更成熟。

## 10. 下一步建议

建议下一步进入第 6：User Input Router。

原因：

第 5 阶段已经解决了“当系统要调用 LLM 时，应该如何治理上下文”的问题。

下一步要解决的是：

用户输入一句自然语言后，系统怎么判断用户到底想做什么。

比如用户可能想：

- 采集小红书数据；
- 生成竞品报告；
- 生成内容实验；
- 生成草稿；
- 审核草稿；
- 发布后复盘；
- 更新策略记忆；
- 查询已有结果。

User Input Router 要解决的就是“意图识别 + 参数提取 + 路由到正确 workflow / service”。

它和第 5 阶段的关系是：

- 第 5 阶段治理 LLM 输入；
- 第 6 阶段治理用户输入；
- 两者结合起来，系统才更像一个真正可用的 Agent 产品。
