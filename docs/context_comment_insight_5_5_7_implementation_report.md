# 第 5.5.7 实施报告：COMMENT_INSIGHT 的规则摘要与代表评论保留

## 一、我这一步做了什么

第 5.5.7 实现了 `COMMENT_INSIGHT` 的规则摘要与代表评论保留。

这一步让评论洞察不再以大量评论原文的形式直接进入 LLM context，而是先经过确定性规则摘要，只保留：

- 高频需求分类；
- 少量代表评论；
- 转化信号；
- 风险点；
- 数据是否不足的状态。

本次是规则摘要，不是 LLM 摘要。

## 二、为什么要做这一步

评论文本有三个特点：

1. 数量容易变多；
2. 噪声很大；
3. 属于外部不可信文本。

如果把所有评论原文直接塞进 prompt，会浪费 token，也可能把低质量评论、营销评论、攻击性表达、诱导性文本甚至 prompt injection 带进 LLM 上下文。

所以 `COMMENT_INSIGHT` 更适合用“规则摘要 + 代表评论”的方式进入 context：  
模型能看到用户真实需求，但不会被大量原文淹没。

## 三、这一步和前面几步的关系

### 和第 5.5.1 `budget_meta` 的关系

第 5.5.1 已经让每个 slot 都能记录 `budget_meta`。  
本次 `COMMENT_INSIGHT` 摘要后的元数据会合并进 `budget_meta`，例如：

- `compressed`
- `compression_method`
- `selected_count`
- `dropped_count`
- `before_rough_tokens`
- `after_rough_tokens`

### 和第 5.5.2 压缩策略的关系

第 5.5.2 设计里已经说明：`COMMENT_INSIGHT` 应该做摘要加代表评论保留。  
本次就是把这个设计落成代码。

### 和第 5.5.4 `COMPETITOR_EVIDENCE` 的关系

`COMPETITOR_EVIDENCE` 解决的是“竞品笔记/机会证据怎么 Top-K”。  
`COMMENT_INSIGHT` 解决的是“评论需求和代表评论怎么摘要”。

两者都来自竞品报告链路，但职责不同：

- `COMPETITOR_EVIDENCE` 偏内容证据；
- `COMMENT_INSIGHT` 偏用户评论需求、转化信号和风险。

### 和第 5.5.6 `STRATEGY_MEMORY` 的关系

`STRATEGY_MEMORY` 是历史策略记忆筛选。  
`COMMENT_INSIGHT` 是本次竞品评论洞察摘要。

两者都会进入独立 slot，都能记录 metadata，但来源和压缩规则不同。

## 四、我新增 / 修改了哪些文件

本次修改 / 新增了 6 个文件：

- `backend/app/context/context_compressor.py`
- `backend/app/context/context_builder.py`
- `backend/app/services/content_draft_v2_sev.py`
- `backend/tests/test_comment_insight_summary.py`
- `backend/tests/test_content_draft_v2.py`
- `docs/context_comment_insight_5_5_7_implementation_report.md`

没有新增数据库字段，没有新增 migration。

## 五、每个文件改了什么

### `backend/app/context/context_compressor.py`

新增 `summarize_comment_insights()`。

它负责：

- 统计高频需求；
- 选择代表评论；
- 汇总转化信号；
- 汇总风险点；
- 标记数据不足；
- 返回 `compression_meta`。

同时新增辅助函数：

- `_comment_demand_name()`
- `_comment_signal_name()`
- `_comment_count_value()`
- `_record_comment_example()`
- `_select_representative_comments()`
- `_comment_insight_data_status()`

### `backend/app/context/context_builder.py`

在 `ContextManager._prepare_slot()` 中新增逻辑：

当 slot 是 `COMMENT_INSIGHT` 且内容是 list 时，调用：

```python
summarize_comment_insights(...)
```

然后把摘要结果作为 slot 内容，并把 `compression_meta` 合并到 `budget_meta`。

### `backend/app/services/content_draft_v2_sev.py`

新增 `COMMENT_INSIGHT` 真实接入：

- 从 `ContentOpportunity.report_id` 找到竞品报告；
- 从 `CompetitorAnalysisReport` 读取 `comment_demands / conversion_signals / risk_points`；
- 从 `CompetitorComment` 读取真实评论样本；
- 构造成 `comment_insight_items`；
- 在 LLM context 中新增 `COMMENT_INSIGHT` slot；
- 设置 `trust_level=UNTRUSTED`；
- 设置 `source_type=comment_insight`；
- 写入 `sample_count / demand_count / risk_count / data_status`。

### `backend/tests/test_comment_insight_summary.py`

新增 7 个测试，覆盖：

- 高频需求保留；
- 代表评论数量限制；
- 转化信号摘要；
- 风险点摘要；
- 评论样本不足；
- metadata 字段；
- 原始输入不被修改；
- ContextManager 能应用摘要并保持 untrusted。

### `backend/tests/test_content_draft_v2.py`

扩展原有草稿生成集成测试：

- 断言 `opportunity_snapshot.comment_insight_items` 有真实 comment / demand item；
- 断言 `comment_insight` slot 进入 `ContextSnapshot`；
- 断言 `ContextSlotLog.metadata_payload["budget_meta"]` 中有规则摘要 metadata；
- 断言 `comment_insight` slot 的 `trust_level` 是 `untrusted`；
- 断言代表评论使用 `untrusted_text`。

## 六、重要函数怎么设计

### `summarize_comment_insights(items, top_k=6)`

这是本次核心函数。

输入：

- `items`: `list[dict]`，评论洞察原始项；
- `top_k`: 最多保留多少条代表评论。

输出：

- `summary`: 摘要结果；
- `compression_meta`: 摘要元数据。

摘要结果结构：

```python
{
    "demand_summary": [...],
    "representative_comments": [...],
    "conversion_signal_summary": [...],
    "risk_summary": [...],
    "data_status": "...",
}
```

### `demand_summary` 怎么生成

来源有两类：

1. 已经聚合好的 demand item；
2. 原始 comment item 上的 `demand_type`。

函数会用 `Counter` 做计数，最多保留 5 类高频需求。

### `representative_comments` 怎么保留

代表评论来自：

- 原始 comment item 的 `content`；
- demand item 中的 `examples`。

规则：

- 每个需求分类最多保留 2 条；
- 总数最多保留 `top_k` 条；
- 同类评论按 `like_count` 高低优先；
- 评论原文统一写成 `untrusted_text`。

### `conversion_signal_summary` 怎么生成

来源：

- `item_type=conversion_signal` 的 item；
- comment item 中附带的 `conversion_signals`。

同名信号会计数合并，最多保留 5 条。

### `risk_summary` 怎么生成

来源：

- `item_type=risk_point` 的 item；
- comment item 中附带的 `risk_points`。

同名风险会计数合并，最多保留 5 条。

### `data_status` 怎么处理

规则：

- 没有 items：`NOT_PROVIDED`
- 评论样本少于 3 条：`DATA_INSUFFICIENT`
- 有真实评论数据：`REAL`
- 有摘要但真实评论不足：`PARTIAL`

### 是否复用了 `rough_token_count`

是。

`compression_meta.before_rough_tokens` 和 `compression_meta.after_rough_tokens` 都复用了 `rough_token_count()`。

## 七、摘要和过滤规则

### 高频需求怎么统计

对 demand item 的 `type/name` 计数。  
对 comment item 的 `demand_type` 计数。  
最后按 count 从高到低保留最多 5 类。

### 代表评论怎么选

先按需求分类找评论样本，再按 `like_count` 选代表评论。  
每个需求最多 2 条，总数最多 `top_k` 条。

### 转化信号怎么保留

对转化信号名称计数，最多保留 5 条。  
例如“求源码”“要资料”“想进群”等。

### 风险点怎么保留

对风险点名称计数，最多保留 5 条。  
例如“夸大收益”“强诱导评论”等。

### 评论样本不足怎么处理

如果评论样本少于 3 条：

- `summary.data_status = DATA_INSUFFICIENT`
- `compression_meta.warning = COMMENT_SAMPLE_INSUFFICIENT`
- `drop_reason.comment_sample_insufficient = 1`

这不是报错，而是告诉后续链路：评论洞察可参考，但样本不足。

### untrusted 怎么标记

有两层标记：

1. slot 层：`COMMENT_INSIGHT` 的 `trust_level=UNTRUSTED`；
2. 字段层：代表评论原文放在 `untrusted_text` 字段里。

这样模型看到评论时，会被上下文安全层包裹为不可信来源，不能把评论当系统指令执行。

## 八、重要 metadata 字段是什么意思

- `compressed`：是否做过摘要，本次为 `true`；
- `truncated`：是否截断原文，本次为 `false`；
- `compression_method`：摘要方法，本次为 `deterministic_comment_insight_summary`；
- `before_chars`：摘要前稳定 JSON 字符数；
- `after_chars`：摘要后稳定 JSON 字符数；
- `before_rough_tokens`：摘要前粗略 token 数；
- `after_rough_tokens`：摘要后粗略 token 数；
- `selected_count`：保留的代表评论数量；
- `dropped_count`：未进入代表评论的评论样本数量；
- `drop_reason`：丢弃或提示原因统计；
- `top_k`：最多保留几条代表评论；
- `summary_generated`：是否生成摘要，本次为 `true`，但这是规则摘要；
- `warning`：样本不足等提示。

## 九、数据流怎么走

`comment_demands / comment_examples / conversion_signals / risk_points / CompetitorComment`

→ 构造成 `comment_insight_items`

→ 加入 `COMMENT_INSIGHT` slot

→ `ContextManager`

→ `deterministic_comment_insight_summary`

→ `compression_meta`

→ 合并进 `budget_meta`

→ 写入 `ContextSnapshot / ContextSlotLog / PromptRunLog`

→ LLM structured call

## 十、这一步达到了什么效果

现在 `content_draft_v2` 可以使用评论洞察，但不会把评论原文无差别塞进上下文。

它会优先给模型：

- 用户主要在问什么；
- 哪些评论最有代表性；
- 有哪些转化信号；
- 有哪些风险点；
- 评论样本是否足够。

这样减少了 token 浪费，也降低了外部评论带来的 prompt injection 风险。

## 十一、这一步没有做什么

本次明确没有做：

- 没调用真实 LLM；
- 没新增数据库字段；
- 没新增 migration；
- 没替换硬编码领域词；
- 没实现 `DOMAIN_PROFILE` 自动生成；
- 没重构多 Agent；
- 没改 prompt 文案；
- 没改 LLMClient；
- 没做 LLM 摘要；
- 没改前端；
- 没改 `COMPETITOR_EVIDENCE` Top-K 规则；
- 没改 `STRATEGY_MEMORY` 筛选规则。

## 十二、测试命令和测试结果

已运行：

```powershell
.\.venv\Scripts\python.exe -m pytest backend/tests/test_comment_insight_summary.py -q -s -p no:cacheprovider --basetemp=.pytest_tmp
```

结果：`7 passed`

```powershell
.\.venv\Scripts\python.exe -m pytest backend/tests/test_context_compressor.py -q -s -p no:cacheprovider --basetemp=.pytest_tmp
```

结果：`6 passed`

```powershell
.\.venv\Scripts\python.exe -m pytest backend/tests/test_context_engineering.py -q -s -p no:cacheprovider --basetemp=.pytest_tmp
```

结果：`6 passed`

```powershell
.\.venv\Scripts\python.exe -m pytest backend/tests/test_content_draft_v2.py -q -s -p no:cacheprovider --basetemp=.pytest_tmp
```

结果：`6 passed, 1 warning`

```powershell
.\.venv\Scripts\python.exe -m pytest backend/tests -q -x -p no:cacheprovider --basetemp=.pytest_tmp
```

结果：`146 passed, 1 warning`

warning 来自 Starlette TestClient 的 `DeprecationWarning`，不是本次功能失败。

## 十三、下一步建议

下一步可以进入第 5.6：`ContextSnapshot` 对比报告。

重点统计优化前后：

- slot token；
- `selected_count`；
- `dropped_count`；
- `compression_method`；
- 各 slot 的压缩效果；
- 上下文治理带来的 token 节省。

这些指标后续可以直接沉淀为简历里的“上下文治理 / token budget / 可观测性”项目成果。
