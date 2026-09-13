# Context Engineering 简历与面试笔记

## 1. 简历可写表达

### 1.1 简洁版

- 设计并落地 LLM Context Slot、预算、压缩与快照复盘机制。

### 1.2 标准版

- 设计 Context Engineering 体系，将 LLM 输入拆分为账号画像、竞品证据、评论洞察、策略记忆、风险约束、输出 schema 等 slot，避免上下文无边界拼接。
- 为核心 slot 落地 token budget、`budget_meta`、压缩策略和 `ContextSnapshot` 记录，使每次生成可追踪、可复盘。
- 实现竞品证据 Top-K、策略记忆筛选和评论规则摘要，降低低质量外部文本、过期记忆和原始评论对生成结果的干扰。

### 1.3 强化版

- 在小红书内容运营决策系统中设计并实现 Context Engineering 层，把原本散落在 workflow、service 和 prompt 中的 LLM 输入统一抽象为 Context Slot，包括 `ACCOUNT_PROFILE`、`COMPETITOR_EVIDENCE`、`COMMENT_INSIGHT`、`STRATEGY_MEMORY`、`RISK_CONSTRAINTS`、`OUTPUT_SCHEMA` 等。
- 为 slot 增加 token 粗估、预算上限、数据状态、信任等级、压缩方法、筛选数量、丢弃数量等 `budget_meta`，并写入 `ContextSnapshot`、`ContextSlotLog`、`PromptRunLog`，支持生成后审计和问题复盘。
- 针对高噪声上下文实现确定性治理策略：竞品证据按相关性、可信度、新鲜度和互动表现 Top-K；策略记忆按领域、置信度、新鲜度和结果验证筛选；评论洞察通过规则摘要保留高频需求、代表评论、转化信号和风险点，并将外部评论标记为 `UNTRUSTED`。

这些表述都没有写“成本下降百分比”“质量提升百分比”。因为项目目前有工程统计和 rough token estimate，但还没有稳定的真实多轮评测数据，不能编造优化比例。

## 2. 面试一句话介绍

我在项目里做的 Context Engineering，不是简单拼 prompt，而是把 LLM 输入拆成账号画像、竞品证据、评论洞察、策略记忆、风险规则、输出 schema 等 slot，并为每个 slot 做 token budget、压缩策略和快照记录。

## 3. 面试问答：为什么做 Context Engineering？

可以这样答：

LLM 生成内容时，输入不只是用户一句话，还包括账号定位、实验状态、竞品证据、评论洞察、历史策略和风险规则。早期如果把这些信息直接拼到 prompt 里，会有几个问题：token 越来越大、竞品证据噪声多、评论原文可能污染 prompt、历史策略可能过期、生成失败后也很难复盘模型到底看到了什么。

所以我做 Context Engineering 的目标，是把上下文从“随手拼字符串”变成“可分类、可预算、可压缩、可记录、可复盘”的工程结构。

## 4. 面试问答：Context Slot 是什么？

可以这样答：

Context Slot 是我对 LLM 输入做的分层。比如账号画像放到 `ACCOUNT_PROFILE`，竞品证据放到 `COMPETITOR_EVIDENCE`，评论洞察放到 `COMMENT_INSIGHT`，策略记忆放到 `STRATEGY_MEMORY`，风险规则放到 `RISK_CONSTRAINTS`，输出结构放到 `OUTPUT_SCHEMA`。

这样做的好处是，每一类上下文都有固定位置、固定来源、预算上限和治理策略。后面排查问题时，也能知道到底是哪类上下文影响了生成结果。

## 5. 面试问答：Token Budget 是什么？

可以这样答：

Token Budget 是给每类上下文设置一个大致预算。比如竞品证据可以比较大，但不能无限增长；评论洞察通常更容易膨胀，所以要摘要；风险规则和输出 schema 比较关键，不能随便丢。

我这里做的是工程上的 rough token estimate，不是严格 tokenizer 计数。它的价值是能帮助系统发现哪个 slot 超预算、哪个 slot 被压缩、压缩前后大概变化多少，并把这些信息记录到 `budget_meta` 里。

## 6. 面试问答：COMPETITOR_EVIDENCE 怎么 Top-K？

可以这样答：

竞品证据不适合全量塞给模型，因为会带来 token 膨胀和噪声。所以我做了确定性 Top-K。

筛选时主要看几类因素：和当前选题、账号关键词、内容支柱的相关性；证据可信度；互动表现；新鲜度；以及是否存在风险或 mock、seed、failed 这类不适合作为生产证据的数据。

最后会把选中的数量、丢弃的数量、压缩方法、压缩前后 rough token 等信息写进 metadata。这样不是黑盒地少传了一些内容，而是可解释地筛选。

## 7. 面试问答：STRATEGY_MEMORY 怎么筛选？

可以这样答：

策略记忆是历史经验，会随着系统运行越来越多。它的问题是可能过期、低置信、跨领域不适用。如果全塞给模型，反而会误导生成。

所以我做了确定性筛选：同领域优先、高置信优先、新鲜记忆优先、有结果验证的优先，同时保留少量失败经验作为避坑参考。低置信、错领域、失败状态或高风险记忆会被降权或过滤。

这部分也会记录 `selected_count`、`dropped_count`、`compression_method` 和 rough token 变化，方便后续复盘。

## 8. 面试问答：COMMENT_INSIGHT 为什么要摘要？

可以这样答：

评论是最容易膨胀、也最容易污染 prompt 的上下文。真实评论里有重复表达、情绪化表达、无关内容，甚至可能有 prompt injection 风险。如果全量塞给模型，既浪费 token，也会让模型被原始评论牵着走。

所以我把评论处理成规则摘要，只保留几类信息：高频需求、每类需求的代表评论、转化信号、风险点。这样模型看到的是经过整理的用户洞察，而不是一大堆未经治理的原文。

## 9. 面试问答：为什么评论要标记 UNTRUSTED？

可以这样答：

评论来自外部用户，不是系统规则，也不是开发者指令。它只能作为参考数据，不能被模型当成指令执行。

所以我把 `COMMENT_INSIGHT` 标记为 `UNTRUSTED`。这个标记的意义是提醒系统和后续审计：评论属于不可信外部输入，需要摘要、筛选和隔离，不能直接改变系统行为边界。

## 10. 面试问答：ContextSnapshot 有什么用？

可以这样答：

`ContextSnapshot` 的作用是记录某次 LLM 调用时到底注入了什么上下文。它让生成过程可以复盘。

比如某次草稿质量不好，我们可以回头看当时 `COMPETITOR_EVIDENCE` 选了哪些证据，`STRATEGY_MEMORY` 有没有引入旧策略，`COMMENT_INSIGHT` 有没有数据不足或风险提示，哪些 slot 超预算，哪些 slot 被压缩。

没有 snapshot 的话，生成失败只能猜。加了 snapshot 后，排查方向会清楚很多。

## 11. 面试问答：有没有真实降低 token 成本？

可以这样答：

目前我不会说已经稳定降低了多少百分比。现在已经有 slot 级 token 粗估、压缩前后 rough token、selected/dropped 数量和 snapshot 统计，但这还只是工程可观测能力。

要说真实成本下降百分比，需要真实 tokenizer、稳定样本、多轮 before/after 对照和统计分析。目前项目还没做到这个阶段，所以简历和面试里我只说“具备预算、压缩和统计能力”，不说“降低了 xx% 成本”。

## 12. 面试问答：这是多 Agent 吗？

可以这样答：

这个项目的目标方向是多 Agent 驱动的小红书内容情报与运营决策系统，但我会诚实区分当前状态。

当前已经有 `AgentRuntime`、workflow 编排、LLM-powered service，以及面向内容生成、竞品分析、策略记忆的模块化能力。但它还不是成熟的多个自治 Agent 相互协作、自主规划、自主调用工具的系统。

我做的 Context Engineering 更像是为后续多 Agent 化打基础：如果将来有多个 Agent，它们共享和传递上下文时，需要先有 slot、预算、压缩、信任等级和 snapshot 这些底层能力。

## 13. 不能写进简历的话

以下内容现在不能写，除非后面真的做了评测和数据验证：

- token 降低 xx%；
- 成本下降 xx%；
- 延迟降低 xx%；
- 生成质量提升 xx%；
- 内容转化率提升 xx%；
- 实现多个成熟自治 Agent；
- 通过多 Agent 自动完成完整内容运营闭环；
- 已经具备生产级 Agent 自主决策能力。

原因很简单：这些都需要真实数据支撑。现在项目能证明的是工程结构、治理能力、记录能力和测试覆盖，不能虚构业务收益。

## 14. 推荐最终简历写法

推荐写成这一条：

- 设计并落地 LLM Context Engineering 层，将账号画像、竞品证据、评论洞察、策略记忆、风险约束和输出 schema 拆分为可治理 Context Slot，支持 token budget、确定性 Top-K / 规则摘要、外部文本信任标记和 ContextSnapshot 复盘，提升内容生成链路的可观测性与可维护性。

这条比较稳。它强调了真实完成的工程能力，没有夸大成未经验证的成本优化或业务增长。
