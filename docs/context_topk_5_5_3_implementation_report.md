 # 第 5.5.3 COMPETITOR_EVIDENCE 确定性 Top-K 实现报告

## 一、我这一步做了什么

本次完成第 5.5.3：实现 `COMPETITOR_EVIDENCE` 的确定性 Top-K。

简单说，就是当竞品证据很多时，系统不再需要无差别把所有证据都塞进 LLM 上下文，而是可以先用确定性规则筛选出更可信、更相关、互动更好、风险更低的证据。

本次实现的是规则函数和上下文构建接入口，不调用 LLM，不做 embedding，不连接数据库，不实现评论摘要，也不实现策略记忆筛选。

## 二、为什么要做这一步

竞品证据通常数量多、文本长，例如爆款笔记、标题模式、内容支柱、封面模式、评论线索等。如果全部塞进 LLM，会挤占：

- 账号画像。
- 任务说明。
- 风险约束。
- 输出结构。
- 用户本轮要求。

第 5.5.1 已经能通过 `budget_meta` 看见某个槽位是否超预算。第 5.5.2 已经设计出 `COMPETITOR_EVIDENCE` 应该优先做 Top-K。第 5.5.3 就是把这条设计落成确定性规则函数。

## 三、我新增 / 修改了哪些文件

本次修改文件：

- `backend/app/context/context_compressor.py`
- `backend/app/context/context_builder.py`
- `backend/app/context/context_budget.py`
- `backend/tests/test_context_engineering.py`

本次新增文件：

- `backend/tests/test_context_compressor.py`
- `docs/context_topk_5_5_3_implementation_report.md`

## 四、每个文件改了什么

### 1. `backend/app/context/context_compressor.py`

新增 `select_competitor_evidence_top_k` 函数。

它接收：

- `items: list[dict]`：候选竞品证据。
- `top_k: int`：最多保留几条。
- `query_context: dict | None`：当前选题、账号关键词、领域关键词等上下文。

它返回：

- `selected_items`：筛选后的竞品证据浅拷贝列表。
- `compression_meta`：本次 Top-K 的压缩元数据。

同时新增了一组内部辅助函数，用来处理过滤、评分、相关性匹配、互动表现计算、多样性限制和 metadata 构建。

### 2. `backend/app/context/context_builder.py`

在 `ContextManager._prepare_slot` 中增加一个很窄的接入口：

只有当槽位名是 `COMPETITOR_EVIDENCE`，并且内容是 `list` 时，才调用 `select_competitor_evidence_top_k`。

调用后会把：

- 筛选后的证据写回当前槽位内容。
- `compression_meta` 写入槽位 metadata。
- 再合并到 `budget_meta`。

这样后续 `ContextSnapshot` / `ContextSlotLog` 可以记录 Top-K 结果。

### 3. `backend/app/context/context_budget.py`

补充了几个中文来源标签：

- `competitor_report`：竞品报告。
- `competitor_analysis`：竞品分析。
- `rule_based`：规则输出。

这样后续竞品证据进入 `budget_meta` 时，中文报告里可以看到可读来源。

### 4. `backend/tests/test_context_compressor.py`

新增 Top-K 单元测试，覆盖：

- 能从多条竞品证据中选出指定数量。
- `is_mock=True` 不进入核心 Top-K。
- `data_status=FAILED` 不进入核心 Top-K。
- `risk_level=HIGH` 不进入核心 Top-K。
- 关键词命中的证据优先。
- 收藏、点赞、评论更高的真实证据优先。
- `compression_meta` 字段完整。
- 不修改原始输入对象。

### 5. `backend/tests/test_context_engineering.py`

新增一条上下文构建测试，验证：

- `COMPETITOR_EVIDENCE` 槽位会应用确定性 Top-K。
- mock 和高风险证据不会进入最终内容。
- `budget_meta` 中会记录 `compressed=true`、`compression_method=deterministic_top_k`、`selected_count`、`dropped_count`、`top_k`。

## 五、重要函数怎么设计

### 1. `select_competitor_evidence_top_k`

这是本次核心函数。

它做五件事：

1. 复制候选证据，避免修改原始输入。
2. 过滤不可进入核心证据的样本。
3. 根据可信度、相关性、互动表现、新鲜度、置信度打分。
4. 按分数排序并选择 Top-K。
5. 返回筛选结果和 `compression_meta`。

函数有中文 docstring，不调用 LLM，不连接数据库，不依赖第三方库。

### 2. 过滤函数

过滤逻辑会排除：

- `is_mock=True`
- `risk_blocked=True`
- `data_status=FAILED`
- `data_status=MOCK`
- `data_status=SEED_SAMPLE`
- `source_type=MOCK`
- `source_type=SEED_SAMPLE`
- `source_type=TEST`
- `source_type=DEMO`
- `provider_name=mock`
- `provider_name=seed_sample`
- `risk_level=HIGH`
- `risk_level=BLOCKED`

这些样本不会进入核心 Top-K，会进入 `drop_reason` 统计。

### 3. 评分函数

评分由五部分组成：

1. 数据可信度。
2. 关键词相关性。
3. 互动表现。
4. 新鲜度。
5. 置信度。

排序时按这个顺序比较，先看可信度，再看相关性，再看互动表现。

### 4. compression_meta 构建逻辑

Top-K 函数会记录：

- Top-K 前字符数。
- Top-K 后字符数。
- Top-K 前粗略 token。
- Top-K 后粗略 token。
- 保留了几条。
- 丢弃了几条。
- 丢弃原因。
- 本次 top_k 参数。
- 是否生成摘要。
- 是否截断。

本次没有生成摘要，所以 `summary_generated=false`。

### 5. 是否复用了 rough_token_count

是。`context_compressor.py` 复用了 `context_budget.py` 中的 `rough_token_count`，保证 Top-K 前后的 token 粗略估算口径和第 5.5.1 的 `budget_meta` 一致。

## 六、Top-K 排序和过滤规则

### 1. 数据可信度怎么判断

优先级从高到低：

1. `REAL`
2. `MANUAL`
3. `MCP`
4. `XHS_PUBLIC_READONLY`
5. `UNKNOWN`
6. `PARTIAL`

函数会从 `data_status`、`source_type`、`provider_name` 中读取这些信息。

### 2. 相关性怎么判断

如果传入 `query_context`，函数会读取：

- `selected_topic`
- `topic`
- `content_pillar`
- `account_keywords`
- `domain_keywords`
- `keywords`

然后在候选证据的以下字段中做简单字符串匹配：

- `title`
- `content`
- `summary`
- `evidence_summary`
- `content_pillar`
- `title_pattern`
- `tags`

本次只做简单字符串匹配，不做 embedding，不调用 LLM。

### 3. 互动表现怎么计算

互动分数为：

```text
collect_count * 3 + like_count * 2 + comment_count
```

也就是说收藏权重最高，其次点赞，再其次评论。

原因是收藏通常更能表示“用户觉得有用、以后还想看”，对内容选题参考价值更高。

### 4. mock / seed / failed / high risk 怎么处理

这些不会进入核心 Top-K：

- mock 数据。
- seed demo 数据。
- failed 数据。
- high risk 数据。
- risk blocked 数据。

它们不会被删除原始输入，只是在本次 Top-K 输出中不保留，并在 `drop_reason` 中记录原因。

### 5. 多样性有没有处理

有做轻量处理。

当前规则会限制同一个：

- `title_pattern`
- `content_pillar`
- `author_id` / `account_id`

不要无限重复进入 Top-K。默认同一类最多优先保留 2 条。如果候选不足，函数会回填少量重复类型证据，并在 `warning` 中说明。

这样做是折中：既避免 Top-K 全是同一种标题模式，也避免候选太少时输出为空。

## 七、重要 metadata 字段是什么意思

`compression_meta` 至少包含：

- `compressed`：是否做过筛选 / 压缩。本次 Top-K 后为 `true`。
- `truncated`：是否截断原文。本次不截断，所以是 `false`。
- `compression_method`：压缩方法。本次是 `deterministic_top_k`。
- `before_chars`：Top-K 前字符数。
- `after_chars`：Top-K 后字符数。
- `before_rough_tokens`：Top-K 前粗略 token 数。
- `after_rough_tokens`：Top-K 后粗略 token 数。
- `selected_count`：保留了多少条竞品证据。
- `dropped_count`：丢弃了多少条竞品证据。
- `drop_reason`：丢弃原因统计，例如 mock、高风险、失败数据、未进入 Top-K。
- `top_k`：最多保留几条。
- `summary_generated`：是否生成摘要。本次必须是 `false`。
- `warning`：多样性回填或风险说明。

这些字段会合并进槽位的 `budget_meta`，后续可以通过已有 JSON metadata 进入上下文快照和槽位日志。

## 八、数据流怎么走

当后续真实 `COMPETITOR_EVIDENCE` 槽位接入后，数据流是：

```text
COMPETITOR_EVIDENCE 槽位
→ 判断内容是否为 list[dict]
→ 执行确定性 Top-K
→ 过滤不可用证据
→ 计算可信度、相关性、互动表现、新鲜度、置信度
→ 排序
→ 选择 Top-K
→ 生成 compression_meta
→ 写入 slot metadata
→ 合并进 budget_meta
→ ContextSnapshot / ContextSlotLog 记录 metadata
```

当前 `content_draft_v2` 还没有真实 `COMPETITOR_EVIDENCE` 生产来源接入。本次已经完成工具函数和 `ContextManager` 接入口，并用单元测试验证规则。后续只要真实竞品证据以 `COMPETITOR_EVIDENCE` 槽位传入，就会自动应用这套 Top-K。

## 九、这一步达到了什么效果

本次完成后，系统已经具备确定性筛选竞品证据的能力。

效果是：

1. mock、seed、failed、高风险证据不会进入核心 Top-K。
2. 可信、相关、高互动证据会优先保留。
3. Top-K 前后的字符数和粗略 token 数会记录下来。
4. 选中数量、丢弃数量、丢弃原因会记录下来。
5. 后续 `content_draft_v2` 可以优先保留高价值竞品证据，为减少噪声和控制 token 做准备。

## 十、这一步没有做什么

本次明确没有做：

- 没调用真实 LLM。
- 没新增数据库字段。
- 没新增 migration。
- 没做 `COMMENT_INSIGHT` 摘要。
- 没做 `STRATEGY_MEMORY` 筛选。
- 没替换硬编码领域词。
- 没实现 `domain_profile` 自动生成。
- 没重构多 Agent。
- 没改 prompt 文案。
- 没改 LLMClient。
- 没连接真实外部服务。
- 没大改旧 `content_draft` / `review_report`。

## 十一、测试结果

### 1. COMPETITOR_EVIDENCE Top-K 测试

命令：

```bash
.\.venv\Scripts\python.exe -m pytest backend/tests/test_context_compressor.py -q -s -p no:cacheprovider --basetemp=.pytest_tmp
```

结果：

```text
6 passed
```

### 2. Context Engineering 测试

命令：

```bash
.\.venv\Scripts\python.exe -m pytest backend/tests/test_context_engineering.py -q -s -p no:cacheprovider --basetemp=.pytest_tmp
```

结果：

```text
6 passed
```

### 3. Context Budget 测试

命令：

```bash
.\.venv\Scripts\python.exe -m pytest backend/tests/test_context_budget.py -q -s -p no:cacheprovider --basetemp=.pytest_tmp
```

结果：

```text
5 passed
```

### 4. content_draft_v2 测试

命令：

```bash
.\.venv\Scripts\python.exe -m pytest backend/tests/test_content_draft_v2.py -q -s -p no:cacheprovider --basetemp=.pytest_tmp
```

结果：

```text
4 passed, 1 warning
```

### 5. 全量测试

命令：

```bash
.\.venv\Scripts\python.exe -m pytest backend/tests -q -x -p no:cacheprovider --basetemp=.pytest_tmp
```

结果：

```text
127 passed, 1 warning
```

warning 来自 `starlette.testclient` 的 `DeprecationWarning`，不是本次 Top-K 实现导致的失败。

## 十二、下一步建议

下一步有两个可选方向：

1. 如果当前最需要让草稿生成用上真实竞品证据，可以先把 `COMPETITOR_EVIDENCE` 接入 `content_draft_v2` 的真实 slot。
2. 如果当前更想继续完善压缩体系，可以做第 5.5.4：实现 `STRATEGY_MEMORY` 的确定性筛选。

不建议下一步一次性实现 `COMMENT_INSIGHT` 摘要、`STRATEGY_MEMORY` 筛选和 LLM 摘要。应该继续保持小步、确定性、可测试。
