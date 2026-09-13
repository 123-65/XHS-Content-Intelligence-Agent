# 第 5.5.5 实施报告：实现 STRATEGY_MEMORY 的确定性筛选

## 一、我这一步做了什么

第 5.5.5 实现了 `STRATEGY_MEMORY` 的确定性筛选。

简单说：当策略记忆是 `list[dict]` 时，系统不会再无差别把所有历史策略、复盘结论、有效表达、失败经验都塞进 LLM context，而是会先按规则过滤和排序，再选出最值得参考的 Top-K。

本次只做规则筛选，不调用 LLM。

## 二、为什么要做这一步

策略记忆会随着复盘和生成次数越来越多。如果不筛选，会有几个问题：

- 旧策略可能已经过期；
- 低置信策略可能把模型带偏；
- 不同领域的策略可能污染当前账号；
- mock、seed、failed 数据不应该进入核心上下文；
- 全量塞入会浪费 token；
- 只看成功经验会让模型忽略失败教训，容易重复踩坑。

所以 `STRATEGY_MEMORY` 需要确定性筛选，让当前草稿优先参考同领域、高置信、新鲜、经过结果验证的策略，同时保留少量真实失败复盘。

## 三、我新增 / 修改了哪些文件

本次修改 / 新增了 4 个文件：

- `backend/app/context/context_compressor.py`
- `backend/app/context/context_builder.py`
- `backend/tests/test_strategy_memory_filter.py`
- `docs/context_strategy_memory_5_5_5_implementation_report.md`

没有新增数据库字段，没有新增 migration。

## 四、每个文件改了什么

### `backend/app/context/context_compressor.py`

新增 `select_strategy_memory_items()`。

它负责：

- 接收策略记忆列表；
- 过滤不可用记忆；
- 按同领域、置信度、新鲜度、结果验证排序；
- 保留少量失败经验；
- 返回筛选后的 selected items；
- 返回 `compression_meta`。

同时新增了一组内部辅助函数：

- `_pick_strategy_memory_rows()`
- `_score_strategy_memory()`
- `_strategy_memory_blocked_reason()`
- `_strategy_domain_score()`
- `_strategy_memory_haystack()`
- `_strategy_confidence()`
- `_normalize_confidence()`
- `_has_result_validation()`
- `_is_failure_memory()`
- `_domain_profile_version_mismatch()`
- `_is_generic_memory()`
- `_strategy_query_keywords()`
- `_add_keywords()`

这些函数都不调用 LLM，不连数据库，不依赖第三方库。

### `backend/app/context/context_builder.py`

在 `ContextManager._prepare_slot()` 中新增判断：

如果当前 slot 是 `STRATEGY_MEMORY`，并且内容是 `list[dict]`，就调用 `select_strategy_memory_items()`。

筛选后的 `compression_meta` 会写回 slot metadata，随后合并进 `budget_meta`。

如果 `STRATEGY_MEMORY` 是 dict、字符串或其他结构，则不强行改数据结构，继续按原逻辑处理。

### `backend/tests/test_strategy_memory_filter.py`

新增策略记忆筛选测试，覆盖：

- 能选出指定数量；
- 高 confidence 优先；
- updated_at 新的优先；
- query_context 领域匹配优先；
- failed / mock / seed / risk_blocked / 低置信被过滤；
- domain_profile_version 不匹配会被过滤，但通用记忆可以保留；
- 保留少量 failure memory；
- compression_meta 字段完整；
- 不修改原始输入对象；
- ContextManager 能应用筛选并记录 metadata。

### `docs/context_strategy_memory_5_5_5_implementation_report.md`

也就是本文档，用中文记录本次实现的原因、设计、数据流、测试结果和边界。

## 五、重要函数怎么设计

### `select_strategy_memory_items(items, top_k=5, query_context=None)`

这是本次核心函数。

输入：

- `items`: `list[dict]`，策略记忆列表；
- `top_k`: 最多保留几条；
- `query_context`: 当前任务上下文，例如账号画像、领域关键词、当前选题、内容支柱、目标受众等。

输出：

- `selected_items`: 筛选后的策略记忆；
- `compression_meta`: 筛选过程元数据。

函数会先浅拷贝每条 item，所以不会修改原始输入对象。

### 评分函数

实际评分函数是 `_score_strategy_memory()`。

排序顺序是：

1. 同领域匹配分；
2. 置信度；
3. 新鲜度；
4. 是否有结果验证；
5. 是否为失败经验。

分数是 tuple，排序稳定且确定，不需要 LLM。

### 过滤函数

实际过滤函数是 `_strategy_memory_blocked_reason()`。

它会过滤：

- `data_status=FAILED`
- `data_status=MOCK`
- `data_status=SEED_SAMPLE`
- `is_mock=True`
- `risk_blocked=True`
- `source_type=SEED_SAMPLE / MOCK / TEST / DEMO`
- `risk_level=HIGH / BLOCKED`
- 显式低置信，例如 `confidence < 0.2`
- `domain_profile_version` 明显不匹配，且不是通用记忆

### compression_meta 构建逻辑

`select_strategy_memory_items()` 会用筛选前后的稳定 JSON 文本计算：

- 字符数；
- 粗略 token；
- selected_count；
- dropped_count；
- drop_reason。

这里复用了 `rough_token_count()`，和第 5.5.1 的 `budget_meta` 估算口径保持一致。

### 是否复用了 `rough_token_count`

是。

`before_rough_tokens` 和 `after_rough_tokens` 都来自 `rough_token_count()`。

## 六、筛选排序和过滤规则

### 同领域怎么判断

系统会从 `query_context` 中提取关键词，例如：

- `selected_topic`
- `content_pillar`
- `target_audience`
- `account_type`
- `memory_domain`
- `account_profile.content_domain`
- `account_profile.positioning`
- `domain_profile.domain_keywords`
- `domain_keywords`
- `tags`

然后和策略记忆里的这些字段做简单字符串匹配：

- `memory_type`
- `summary`
- `pattern`
- `usage_reason`
- `content_pillar`
- `memory_domain`
- `account_type`
- `target_audience`
- `tags`

匹配越多，同领域分越高。

如果 `domain_profile_version` 和当前 query_context 完全一致，也会加分。

### 置信度怎么判断

优先看这些字段：

- `confidence`
- `score`
- `reliability`

如果数值大于 1，会按百分制转换，例如 80 会变成 0.8。

如果完全没有置信度字段，本次把它视为中性值 `0.5`，不会因为“未知”而直接过滤。

如果显式低于 `0.2`，会被过滤，并记录 `drop_reason.low_confidence`。

### 新鲜度怎么判断

复用已有 `_freshness_score()`：

- 优先看 `updated_at`
- 其次看 `published_at`
- 再看 `created_at`

使用字符串排序，适合 ISO 时间格式；如果没有时间字段，不报错。

### 有结果验证怎么判断

如果策略记忆含有以下字段之一，就认为有结果验证：

- `result_metric`
- `result_value`
- `success_or_failure`
- `verified`
- `usage_snapshot`
- `has_result`

这类记忆在排序中会优先于没有验证痕迹的记忆。

### 失败经验怎么保留

失败经验通过这些字段识别：

- `success_or_failure`
- `result_status`
- `outcome`
- `memory_type`
- `sentiment`

如果值是：

- `failure`
- `failed`
- `negative`
- `ineffective`
- `invalid`
- `失败`
- `无效`
- `负向`

就视为 failure memory。

当 `top_k > 1` 时，会保留少量真实失败复盘：

- `top_k <= 5` 时，最多保留 1 条；
- `top_k >= 6` 时，最多保留 2 条。

这样做是为了让模型不仅看到“什么有效”，也看到“什么容易失败”。

### mock / seed / failed / high risk 怎么处理

这些不会进入核心结果：

- mock：记录为 `mock`
- seed sample：记录为 `source_type_seed_sample` 或 `data_status_seed_sample`
- failed：记录为 `data_status_failed`
- high risk：记录为 `high_risk`
- risk blocked：记录为 `risk_blocked`

注意：原始数据不会被删除，只是不进入本次 `selected_items`。

## 七、重要 metadata 字段是什么意思

`compression_meta` 至少包含：

- `compressed`：是否执行过筛选，本次为 `true`；
- `truncated`：是否截断原文，本次为 `false`；
- `compression_method`：筛选方法，本次是 `deterministic_strategy_memory_filter`；
- `before_chars`：筛选前稳定 JSON 的字符数；
- `after_chars`：筛选后稳定 JSON 的字符数；
- `before_rough_tokens`：筛选前粗略 token 数；
- `after_rough_tokens`：筛选后粗略 token 数；
- `selected_count`：保留数量；
- `dropped_count`：未进入结果的数量；
- `drop_reason`：丢弃原因统计；
- `top_k`：最多保留几条；
- `summary_generated`：是否生成摘要，本次固定为 `false`；
- `warning`：额外说明，例如保留了失败复盘。

这些字段会合并进 `budget_meta`。

## 八、数据流怎么走

当 `STRATEGY_MEMORY` slot 是 `list[dict]` 时：

`STRATEGY_MEMORY slot`

→ 判断内容是否为 `list[dict]`

→ 过滤不可用记忆

→ 计算领域匹配、置信度、新鲜度、结果验证

→ 保留少量失败经验

→ 排序

→ 选择 Top-K

→ 生成 `compression_meta`

→ 写入 slot metadata

→ 合并进 `budget_meta`

→ 进入 `ContextSnapshot / ContextSlotLog`

当前 `content_draft_v2` 里的 `strategy_memory_snapshot` 仍然是 dict，例如 `{"status": "NOT_IMPLEMENTED_IN_ROUND_6"}` 或带 `previous_draft` 的结构。  
所以当前真实草稿链路不会被强行改造成 list，也不会触发策略记忆筛选。  
本次完成的是通用筛选函数、ContextManager 接入和测试验证，为后续真实策略记忆列表接入做准备。

## 九、这一步达到了什么效果

后续只要上游把历史策略记忆以 `list[dict]` 放进 `STRATEGY_MEMORY`，ContextManager 就会自动执行确定性筛选。

效果是：

- 优先使用同领域策略；
- 优先使用高置信策略；
- 优先使用较新策略；
- 优先使用有结果验证的策略；
- 保留少量失败复盘；
- 过滤 mock、seed、failed、低置信、高风险记忆；
- 把筛选过程写入 metadata，方便审计；
- 减少旧记忆污染和 token 浪费。

## 十、这一步没有做什么

本次明确没有做：

- 没调用真实 LLM；
- 没新增数据库字段；
- 没新增 migration；
- 没做 `COMMENT_INSIGHT` 摘要；
- 没替换硬编码领域词；
- 没实现 `DOMAIN_PROFILE` 自动生成；
- 没重构多 Agent；
- 没改 prompt 文案；
- 没改 LLMClient；
- 没连接真实外部服务；
- 没改 `COMPETITOR_EVIDENCE` Top-K 规则；
- 没强行改变 `content_draft_v2` 现有 `strategy_memory_snapshot` 数据结构。

## 十一、测试结果

已运行：

```powershell
.\.venv\Scripts\python.exe -m pytest backend/tests/test_strategy_memory_filter.py -q -s -p no:cacheprovider --basetemp=.pytest_tmp
```

结果：`10 passed`

```powershell
.\.venv\Scripts\python.exe -m pytest backend/tests/test_context_compressor.py -q -s -p no:cacheprovider --basetemp=.pytest_tmp
```

结果：`6 passed`

```powershell
.\.venv\Scripts\python.exe -m pytest backend/tests/test_context_budget.py -q -s -p no:cacheprovider --basetemp=.pytest_tmp
```

结果：`5 passed`

```powershell
.\.venv\Scripts\python.exe -m pytest backend/tests/test_context_engineering.py -q -s -p no:cacheprovider --basetemp=.pytest_tmp
```

结果：`6 passed`

```powershell
.\.venv\Scripts\python.exe -m pytest backend/tests/test_content_draft_v2.py -q -s -p no:cacheprovider --basetemp=.pytest_tmp
```

结果：`5 passed, 1 warning`

```powershell
.\.venv\Scripts\python.exe -m pytest backend/tests -q -x -p no:cacheprovider --basetemp=.pytest_tmp
```

结果：`138 passed, 1 warning`

warning 来自 Starlette TestClient 的 `DeprecationWarning`，不是本次功能失败。

## 十二、下一步建议

下一步可以做第 5.5.6：`COMMENT_INSIGHT` 的规则摘要与代表评论保留。

也可以先完善 `DOMAIN_PROFILE` 接入设计，让策略记忆和竞品证据的领域匹配有更稳定的统一来源。

不建议下一步一次性把 `COMMENT_INSIGHT` 摘要、`DOMAIN_PROFILE` 自动生成、长期策略记忆检索和 LLM 摘要全部做完。继续小步、确定性、可测试会更稳。
