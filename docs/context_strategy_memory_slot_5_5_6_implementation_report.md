# 第 5.5.6 实施报告：把真实 STRATEGY_MEMORY 接入 content_draft_v2 的 list[dict] slot

## 一、我这一步做了什么

第 5.5.6 是把真实策略记忆接入 `content_draft_v2` 的 `STRATEGY_MEMORY` slot。

这一步完成后，`content_draft_v2` 在构建 LLM context 时，会从数据库里的 `StrategyMemory` 表读取当前账号的真实策略记忆，把它整理成 `list[dict]`，再放进 `STRATEGY_MEMORY` slot。

因为第 5.5.5 已经让 `ContextManager` 支持 `STRATEGY_MEMORY` 的 `list[dict]` 筛选，所以这次接入后，真实草稿生成链路可以自动触发：

`deterministic_strategy_memory_filter`

也就是策略记忆的确定性筛选。 

## 二、为什么要做这一步

第 5.5.5 只是实现了筛选工具。  
如果 `content_draft_v2` 继续把 `strategy_memory_snapshot` 当普通 dict 塞进 context，那么筛选函数不会被触发。

原来的状态是：

- `strategy_memory_snapshot` 是 dict；
- 默认只有 `status=NOT_IMPLEMENTED_IN_ROUND_6`；
- 重生成时会附带 `previous_draft`；
- 真实策略记忆没有进入 `STRATEGY_MEMORY` 的 list slot；
- 所以第 5.5.5 的筛选能力无法作用到真实草稿生成。

本次就是补上真实链路接入，让策略记忆从“有筛选函数”变成“真实生成草稿时可以被筛选”。

## 三、我新增 / 修改了哪些文件

本次修改 / 新增了 3 个文件：

- `backend/app/services/content_draft_v2_sev.py`
- `backend/tests/test_content_draft_v2.py`
- `docs/context_strategy_memory_slot_5_5_6_implementation_report.md`

没有修改 prompt、LLMClient、前端、数据库字段或 migration。

## 四、每个文件改了什么

### `backend/app/services/content_draft_v2_sev.py`

主要改动：

- 引入 `StrategyMemory` 模型；
- 在 `_build_context()` 中读取当前账号可用策略记忆；
- 把真实策略记忆整理进 `strategy_memory_snapshot["items"]`；
- 在 `_build_llm_context()` 中让 `STRATEGY_MEMORY` slot 使用 `items: list[dict]`；
- 新增 `_list_strategy_memories()` 查询当前账号可用记忆；
- 新增 `_build_strategy_memory_items()` 把模型行转换成 slot item；
- 新增 `_strategy_memory_slot_items()` 从 snapshot 中提取 list；
- 新增 `_strategy_memory_query_context()` 给筛选函数提供当前选题、账号画像和领域关键词；
- 新增 `_strategy_memory_data_status()` 判断整个 slot 的数据状态；
- 新增 `_strategy_memory_item_data_status()` 判断单条 memory 的数据状态。

### `backend/tests/test_content_draft_v2.py`

主要改动：

- 新增 `create_strategy_memories()`，在测试数据库中创建真实 `StrategyMemory` 行；
- 在草稿生成测试里先创建真实策略记忆；
- 断言 `generation_context_record.strategy_memory_snapshot.items` 存在真实 memory item；
- 断言 `strategy_memory` slot 出现在 `ContextSnapshot.slot_token_breakdown`；
- 断言 `ContextSlotLog.metadata_payload["budget_meta"]` 中能看到：
  - `compressed=true`
  - `compression_method=deterministic_strategy_memory_filter`
  - `selected_count`
  - `dropped_count`
  - `top_k`
  - `drop_reason.low_confidence`
- 新增空策略记忆测试，确认空 snapshot 不会编造数据。

### `docs/context_strategy_memory_slot_5_5_6_implementation_report.md`

也就是本文档，记录本次实现原因、数据来源、字段设计、数据流、metadata 位置、测试结果和没有做的事情。

## 五、重要函数怎么设计

### `_list_strategy_memories(account_id, limit=20)`

这个函数负责读取当前账号真实策略记忆。

查询条件：

- `StrategyMemory.account_id == 当前账号 id`
- `StrategyMemory.status in ("CANDIDATE", "VALIDATED")`

排序方式：

- `updated_at desc`
- `id desc`

最多取 20 条，避免无限制把长期记忆塞进当前草稿链路。

这里没有新增仓库方法，是为了保持本次改动最小，范围只落在 `content_draft_v2` 服务里。

### `_build_strategy_memory_items(memories)`

这个函数负责把真实 `StrategyMemory` 模型行整理成 `list[dict]`。

它不调用 LLM，不连接外部服务，不编造数据。  
只把模型里已经存在的字段和 `metadata_payload` 里已有的字段整理出来。

字段结构大致是：

```python
{
    "id": memory.id,
    "memory_type": memory.memory_type,
    "status": memory.status,
    "summary": memory.summary,
    "pattern": memory.pattern,
    "confidence": ...,
    "source": ...,
    "source_type": "strategy_memory",
    "source_review_report_id": ...,
    "support_count": ...,
    "evidence_count": ...,
    "risk_level": ...,
    "usage_snapshot": ...,
    "usage_reason": ...,
    "domain_profile_version": ...,
    "content_pillar": ...,
    "tags": ...,
    "success_or_failure": ...,
    "result_metric": ...,
    "result_value": ...,
    "verified": ...,
    "is_mock": ...,
    "data_status": ...,
    "created_at": ...,
    "updated_at": ...,
}
```

不存在的字段会被 `_compact_dict()` 去掉。  
未知值不会被填成 0。  
`is_mock` 只有在 metadata 里明确是布尔值时才写入，不确定时不乱写。

### `_strategy_memory_slot_items(context_payload)`

这个函数从 `context_payload.strategy_memory_snapshot` 中取出真正要进入 slot 的 `items`。

兼容两种输入：

- snapshot 本身就是 `list[dict]`；
- snapshot 是 dict，里面有 `items: list[dict]`。

如果没有 items，则返回空列表。

### `_strategy_memory_query_context(context_payload)`

这个函数给第 5.5.5 的筛选函数提供匹配依据，包括：

- 当前机会标题或实验名称；
- 当前内容支柱；
- 当前目标受众；
- 账号画像；
- 账号内容领域；
- 账号定位；
- 领域关键词。

筛选函数会用这些信息判断哪些策略记忆更贴合当前草稿生成任务。

### `data_status / source / is_mock` 怎么处理

单条 memory：

- `VALIDATED` -> `data_status="REAL"`
- `CANDIDATE` -> `data_status="PARTIAL"`
- 其他状态 -> `data_status="UNKNOWN"`

整个 slot：

- 只要有 `REAL`，slot 就是 `REAL`；
- 否则如果有 `PARTIAL`，slot 是 `PARTIAL`；
- 没有 items，就是 `NOT_PROVIDED`。

`source`：

- 优先使用 `metadata_payload["source"]`；
- 没有则使用 `"strategy_memory"`。

`source_type`：

- 固定为 `"strategy_memory"`，方便 budget 和日志识别来源。

`is_mock`：

- 只有 `metadata_payload["is_mock"]` 明确是布尔值时才写入；
- 不确定时不写，避免把未知误判成 mock 或非 mock。

### 空 memory 怎么处理

如果没有策略记忆：

- `strategy_memory_snapshot.status = "NOT_PROVIDED"`
- `strategy_memory_snapshot.count = 0`
- `strategy_memory_snapshot.items = []`
- `STRATEGY_MEMORY` slot 内容是空列表；
- 不编造 demo 数据；
- 不报错。

## 六、数据流怎么走

新的数据流是：

`StrategyMemory 数据库记录`

→ `_list_strategy_memories(account.id)`

→ `_build_strategy_memory_items(...)`

→ `strategy_memory_snapshot = {"status": ..., "count": ..., "items": [...]}`

→ `_strategy_memory_slot_items(context_payload)`

→ `STRATEGY_MEMORY slot` 使用 `list[dict]`

→ `ContextManager`

→ 第 5.5.5 的 `deterministic_strategy_memory_filter`

→ `compression_meta`

→ 合并进 `budget_meta`

→ 写入 `ContextSnapshot / ContextSlotLog / PromptRunLog`

→ LLM structured call

这条链路的关键变化是：  
`strategy_memory_snapshot` 仍然可以作为生成上下文快照保存，但真正给 `STRATEGY_MEMORY` slot 的内容变成了 `items: list[dict]`。

## 七、筛选 metadata 在哪里能看到

主要看两个地方：

### 1. `ContextSlotLog.metadata_payload["budget_meta"]`

这里能看到完整的 slot 级 metadata，包括：

- `compressed`
- `compression_method`
- `before_rough_tokens`
- `after_rough_tokens`
- `selected_count`
- `dropped_count`
- `drop_reason`
- `top_k`
- `summary_generated`

本次测试重点就是从这里断言 `strategy_memory` 的筛选结果。

### 2. `PromptRunLog.input_payload["_context"]["slot_budget_summary"]`

`PromptRunLog` 中也会保留 context 摘要，其中 `slot_budget_summary` 会带上每个 slot 的 `budget_meta`。

注意：API response 仍然不直接暴露内部 `_context`。  
内部上下文追踪应该通过日志表和快照表看。

### 3. `ContextSnapshot.slot_token_breakdown`

这里可以看到 `strategy_memory` slot 是否进入快照，以及它的 token / budget 统计概要。

## 八、这一步达到了什么效果

现在 `content_draft_v2` 不再只能把策略记忆作为普通 dict 快照。

它已经可以：

- 从真实 `StrategyMemory` 表读取当前账号策略记忆；
- 把策略记忆整理成 `list[dict]`；
- 作为独立 `STRATEGY_MEMORY` slot 注入 context；
- 自动触发第 5.5.5 的确定性筛选；
- 在 `budget_meta` 中记录筛选 metadata；
- 在 `ContextSnapshot / ContextSlotLog / PromptRunLog` 中可追踪；
- 空记忆时不报错、不编造数据。

这意味着后续草稿生成可以优先参考高质量策略记忆，减少旧记忆、低置信记忆和错领域记忆对生成结果的污染。

## 九、这一步没有做什么

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
- 没重构长期 Memory 系统；
- 没改 `COMPETITOR_EVIDENCE` Top-K 规则；
- 没连接外部服务；
- 没改前端。

## 十、测试结果

已运行：

```powershell
.\.venv\Scripts\python.exe -m pytest backend/tests/test_content_draft_v2.py -q -s -p no:cacheprovider --basetemp=.pytest_tmp
```

结果：`6 passed, 1 warning`

```powershell
.\.venv\Scripts\python.exe -m pytest backend/tests/test_strategy_memory_filter.py -q -s -p no:cacheprovider --basetemp=.pytest_tmp
```

结果：`10 passed`

```powershell
.\.venv\Scripts\python.exe -m pytest backend/tests/test_context_engineering.py -q -s -p no:cacheprovider --basetemp=.pytest_tmp
```

结果：`6 passed`

```powershell
.\.venv\Scripts\python.exe -m pytest backend/tests -q -x -p no:cacheprovider --basetemp=.pytest_tmp
```

结果：`139 passed, 1 warning`

warning 来自 Starlette TestClient 的 `DeprecationWarning`，不是本次功能失败。

## 十一、下一步建议

下一步可以做第 5.5.7：`COMMENT_INSIGHT` 的规则摘要与代表评论保留。

也可以进入第 5.6：`ContextSnapshot` 对比报告，让每次 context 改造前后的 token、slot、metadata 差异更容易被看见。
