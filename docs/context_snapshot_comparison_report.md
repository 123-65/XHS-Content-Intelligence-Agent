# 第 5.6 ContextSnapshot 对比报告

## 1. 报告目的

第 5.5 已经完成竞品证据、策略记忆、评论洞察的上下文治理。

第 5.6 的目的不是继续改生成逻辑，而是把已经写入 `ContextSnapshot / ContextSlotLog / PromptRunLog` 的上下文治理数据统计出来。

本报告重点回答：

- 当前一次或多次 LLM context 里有哪些 slot；
- 每个 slot 大概占多少 token；
- 哪些 slot 超预算；
- 哪些 slot 被压缩、筛选或摘要；
- 筛选前后保留了多少、丢弃了多少；
- 哪些数据是真实数据、部分数据或未提供；
- 哪些外部文本被标记为不可信；
- 这些工程指标哪些可以写进简历，哪些还不能写。

## 2. 数据来源

统计脚本是：

```powershell
.\.venv\Scripts\python.exe backend\scripts\context_snapshot_report.py
```

也可以在 `backend` 目录运行：

```powershell
..\.venv\Scripts\python.exe scripts\context_snapshot_report.py
```

脚本读取的数据表和字段：

- `ContextSnapshot`
  - `slot_token_breakdown`
  - `total_tokens`
  - `token_budget`
  - `injected_slot_names`
- `ContextSlotLog`
  - `slot_name`
  - `trust_level`
  - `injected_tokens`
  - `token_ratio`
  - `was_truncated`
  - `metadata_payload["budget_meta"]`
- `PromptRunLog`
  - `input_payload["_context"]["slot_budget_summary"]`

优先级：

1. 优先从 `ContextSlotLog.metadata_payload["budget_meta"]` 读取；
2. 如果缺少 `budget_meta`，再从 `ContextSnapshot.slot_token_breakdown` 兜底；
3. 如果还缺，再从 `PromptRunLog.input_payload["_context"]["slot_budget_summary"]` 兜底。

## 3. 当前统计口径

这是工程可观测性统计口径，不是业务效果评估。

特别注意：

- `rough_tokens` 是粗略 token 估算，不是真实 tokenizer 结果；
- `token_saved_estimate` 是基于 `before_rough_tokens - after_rough_tokens` 的估算；
- `token_saved_ratio_estimate` 只能叫估算比例，不能写成真实成本下降；
- 当前本地数据库可能包含测试数据，所以不能把本报告数字当成生产业务结论。

## 4. Slot 级统计指标

以下是脚本在当前本地数据库最近 100 个 `ContextSnapshot` 上输出的示例统计。

| Slot | 出现次数 | rough_tokens | over_budget | compressed | compression_method | 平均 token 占比 |
|---|---:|---:|---:|---:|---|---:|
| account_profile | 40 | 3600 | 0 | 0 |  | 0.0462 |
| comment_insight | 4 | 884 | 0 | 4 | deterministic_comment_insight_summary(4) | 0.0676 |
| competitor_evidence | 17 | 5168 | 0 | 17 | deterministic_top_k(17) | 0.1280 |
| output_schema | 40 | 28160 | 0 | 0 |  | 0.3617 |
| risk_constraints | 40 | 1497 | 0 | 0 |  | 0.0191 |
| strategy_memory | 40 | 8676 | 0 | 9 | deterministic_strategy_memory_filter(9) | 0.0976 |
| system_rules | 100 | 6780 | 0 | 0 |  | 0.0924 |
| task_instruction | 100 | 2218 | 0 | 0 |  | 0.0428 |
| tool_result | 60 | 4035 | 0 | 0 |  | 0.6212 |
| user_input | 40 | 324 | 0 | 0 |  | 0.0042 |
| workflow_state | 40 | 22446 | 4 | 0 |  | 0.2721 |

说明：

- `出现次数`：这个 slot 在最近快照中出现了多少次；
- `rough_tokens`：该 slot 的粗略 token 总量；
- `over_budget`：超出 slot 预算的次数；
- `compressed`：被压缩、筛选或摘要的次数；
- `compression_method`：使用过的确定性治理方法；
- `平均 token 占比`：该 slot 每次出现时在对应快照中的平均 token 占比。

## 5. 压缩 / 筛选方法分布

当前脚本能统计到这些方法：

- `deterministic_top_k`：17 次
- `deterministic_strategy_memory_filter`：9 次
- `deterministic_comment_insight_summary`：4 次

含义：

- `deterministic_top_k`：用于 `COMPETITOR_EVIDENCE`；
- `deterministic_strategy_memory_filter`：用于 `STRATEGY_MEMORY`；
- `deterministic_comment_insight_summary`：用于 `COMMENT_INSIGHT`。

这些都是确定性规则，不调用 LLM。

## 6. selected_count / dropped_count 统计

当前脚本输出：

- `selected_count_total`：60
- `dropped_count_total`：13

含义：

- `selected_count_total` 表示被保留下来进入摘要或 Top-K 结果的项目数量；
- `dropped_count_total` 表示因为 Top-K、代表评论上限、低置信、mock、风险等原因没有进入最终 slot 内容的项目数量。

注意：  
这里统计的是“上下文治理过程中的保留/丢弃”，不是业务层面的成功/失败。

## 7. before / after token 估算

当前脚本输出：

- `before_rough_tokens_total`：0
- `after_rough_tokens_total`：0
- `token_saved_estimate`：0
- `token_saved_ratio_estimate`：0.0000

解释：

当前本地数据库里最近 100 个快照中，有压缩方法统计，但可用于汇总的 `before_rough_tokens / after_rough_tokens` 历史字段并不完整，所以本次估算为 0。

这不能写成“没有节省 token”，也不能写成“节省了 0%”。  
正确说法是：当前历史快照不足以计算可信的 before / after token 节省比例。

后续如果每次压缩都稳定写入 `before_rough_tokens / after_rough_tokens`，这个指标才可以进入更正式的对比报告。

## 8. data_status / trust_level 分布

当前脚本输出：

data_status：

- `PARTIAL`：22
- `REAL`：352

trust_level：

- `trusted`：440
- `untrusted`：81

解释：

- `REAL` 表示上下文来自真实数据或已验证数据；
- `PARTIAL` 表示数据真实但不完整，或只是候选状态；
- `NOT_PROVIDED` 表示该 slot 没有数据；
- `DATA_INSUFFICIENT` 表示样本不足；
- `trusted` 表示内部可信上下文；
- `untrusted` 表示外部文本，例如竞品内容、评论文本。

这对 prompt injection 风险治理很重要。外部评论和竞品内容不能被当成系统指令。

## 9. 硬编码领域词命中情况

当前脚本输出：

- `hardcoded_domain_term_count`：133
- `warning_count`：48

解释：

- `contains_hardcoded_domain_terms` 只是标记上下文中是否出现了当前 demo 赛道或领域词；
- 它不代表本阶段已经替换掉硬编码领域词；
- 它的价值是告诉后续第 6 阶段或 domain profile 阶段：哪些 slot 仍然有领域词耦合，需要继续治理。

## 10. 当前可写进简历的内容

当前可以写：

- 设计并实现 `Context Slot + Token Budget` 机制；
- 将 LLM 上下文拆分为 `SYSTEM_RULES / TASK_INSTRUCTION / ACCOUNT_PROFILE / WORKFLOW_STATE / COMPETITOR_EVIDENCE / COMMENT_INSIGHT / STRATEGY_MEMORY / OUTPUT_SCHEMA` 等 slot；
- 为每个 slot 记录 `budget_meta`，包含 token 粗估、预算、是否超预算、是否压缩、数据状态、来源标签；
- 对竞品证据实现确定性 Top-K；
- 对策略记忆实现确定性筛选；
- 对评论洞察实现规则摘要和代表评论保留；
- 通过 `ContextSnapshot / ContextSlotLog / PromptRunLog` 记录 slot 级 token、压缩方法、选中数量和丢弃数量；
- 新增统计脚本，支持上下文治理过程可观测、可复盘。

比较稳妥的简历表达可以是：

> 设计并实现 LLM Context Slot 与 Token Budget 治理机制，将竞品证据、策略记忆和评论洞察拆分为独立上下文槽位，并通过确定性 Top-K、规则筛选和摘要策略控制注入内容；基于 ContextSnapshot / ContextSlotLog 记录 slot 级 token、压缩方法、保留/丢弃数量，实现上下文治理过程可观测与可复盘。

## 11. 当前不能写进简历的内容

当前不能写：

- token 成本下降 xx%；
- 延迟降低 xx%；
- 生成质量提升 xx%；
- 转化率提升 xx%；
- 粉丝增长 xx%；
- 内容点击率提升 xx%。

原因：

这些都需要真实样本、多轮运行、稳定 before / after 指标和 Eval 结果支持。  
目前第 5.6 只是建立统计能力，不等于已经完成业务效果验证。

## 12. 结论

第 5.6 是指标统计能力，不是效果夸大。

当前系统已经可以把上下文治理动作记录下来，并用脚本汇总：

- 哪些 slot 被注入；
- 哪些 slot 超预算；
- 哪些 slot 被压缩；
- 使用了什么压缩方法；
- 保留了多少；
- 丢弃了多少；
- 哪些数据来自真实来源；
- 哪些外部文本被标记为 untrusted。

后续需要结合真实样本、多次运行和 Eval，才能形成可信的“token 节省比例”“成本下降比例”“质量提升比例”等量化结论。
