# 第 5.5.4 实施报告：把真实竞品证据接入 content_draft_v2 的 COMPETITOR_EVIDENCE slot

## 1. 为什么做这一步

前面 5.5.1 已经让每个 context slot 都能记录 `budget_meta`，5.5.3 已经实现了 `COMPETITOR_EVIDENCE` 的确定性 Top-K。  
但是 `content_draft_v2` 生成草稿时，原来并没有把真实竞品证据放进 `COMPETITOR_EVIDENCE` slot。

也就是说：

- 系统有 slot 名称；
- 系统有预算统计；
- 系统有 Top-K 策略；
- 但草稿生成链路还没有真正把上游竞品证据接进来。

所以本次 5.5.4 的目标就是补上这段数据流，让 `content_draft_v2` 在生成草稿时可以使用上游竞品报告沉淀下来的真实证据。

## 2. 和 5.5.3 Top-K 的关系

5.5.3 做的是“筛选器”：给一组竞品证据，按可信度、相关性、互动表现、新鲜度等规则稳定选出 Top-K，并记录压缩元数据。

5.5.4 做的是“接线”：

1. 从 `content_draft_v2` 已有上下文里取真实证据；
2. 组装成 `COMPETITOR_EVIDENCE` slot；
3. 交给 `ContextManager`；
4. `ContextManager._prepare_slot()` 识别到该 slot 后，自动调用 5.5.3 的 `select_competitor_evidence_top_k()`。

所以这次没有重写 Top-K 算法，只是把真实数据送到已有 Top-K 通道。

## 3. 新增 / 修改文件

本次修改了 3 个文件：

- `backend/app/services/content_draft_v2_sev.py`
- `backend/tests/test_content_draft_v2.py`
- `docs/context_evidence_slot_5_5_4_implementation_report.md`

没有修改 prompt、LLMClient、前端、数据库字段或 migration。

## 4. 每个文件改了什么

### `backend/app/services/content_draft_v2_sev.py`

主要改动：

- 在 `_build_llm_context()` 中新增 `COMPETITOR_EVIDENCE` slot 注入；
- 新增 `_build_competitor_evidence_items()`，负责从草稿生成上下文里提取竞品证据；
- 新增 `_competitor_evidence_query_context()`，给 Top-K 提供当前账号、选题和内容方向的匹配信息；
- 新增 `_competitor_evidence_data_status()`，判断这批证据整体是 `REAL` 还是 `PARTIAL`；
- 新增 `_score_to_confidence()`，把可复制度分数转换成 0 到 1 的 confidence；
- 新增 `_compact_dict()` 和 `_non_empty_values()`，避免把空字段写入证据项；
- 扩展 `_opportunity_snapshot()`，把 `target_audience`、`content_pillar`、`comment_demand_type`、`risk_points` 也放进机会快照，方便后续证据映射。

### `backend/tests/test_content_draft_v2.py`

主要改动：

- 在原有草稿生成集成测试里，新增对 `competitor_evidence` 的断言；
- 断言它出现在 `ContextSnapshot.slot_token_breakdown`；
- 断言它出现在 `ContextSlotLog.metadata_payload["budget_meta"]`；
- 断言 `budget_meta` 中有 Top-K 元数据，例如：
  - `compressed=True`
  - `compression_method=deterministic_top_k`
  - `top_k=5`
  - `selected_count>=1`
- 断言该 slot 的 `trust_level` 是 `untrusted`；
- 新增空数据测试，确认没有上游证据时不会编造竞品证据。

### `docs/context_evidence_slot_5_5_4_implementation_report.md`

也就是本文档，用中文记录本次实现的原因、设计、数据流、测试结果和没有做的事情。

## 5. 重要函数 / 变量 / 字段怎么设计

### `_build_competitor_evidence_items()`

这个函数负责把已有上下文转换成 Top-K 可以处理的证据列表。

目前生成两类 item：

1. `content_opportunity` 主证据  
   来源于 `opportunity_snapshot`，重点字段包括：
   - `opportunity_title`
   - `suggested_angle`
   - `evidence_summary`
   - `content_pillar`
   - `target_audience`
   - `comment_demand_type`
   - `replicability_score`
   - `risk_level`

2. `content_experiment` 辅助证据  
   来源于 `experiment_snapshot`，重点字段包括：
   - `experiment_name`
   - `hypothesis`
   - `content_pillar`
   - `content_format`
   - `risk_level`

如果这两类数据都为空，函数返回空列表，不会生成假数据。

### `COMPETITOR_EVIDENCE` slot

新增 slot 的关键配置：

- `name=ContextSlotName.COMPETITOR_EVIDENCE`
- `source_type="competitor_report"`
- `trust_level=ContextTrustLevel.UNTRUSTED`
- `priority=78`
- `token_limit=1200`
- `metadata.top_k=5`
- `metadata.query_context=...`
- `metadata.data_status=REAL 或 PARTIAL`

这里把 `trust_level` 设为 `UNTRUSTED`，是因为竞品内容属于外部来源文本，只应该被模型当作参考资料，不能被当作系统指令执行。

### `query_context`

`query_context` 用来帮助 Top-K 判断相关性，包含：

- 当前机会标题或实验名称；
- 当前内容支柱；
- 账号内容领域；
- 账号定位；
- 目标受众。

Top-K 会用这些关键词和证据项里的标题、摘要、标签、内容方向等字段做相关性匹配。

## 6. 竞品证据从哪里来

这次没有新查外部服务，也没有伪造生产数据。

证据来自已有业务链路：

1. 测试或业务侧先创建竞品账号、竞品笔记、竞品评论；
2. `/api/competitor/reports` 生成竞品分析报告；
3. `/api/experiments/generate` 基于报告生成内容机会和实验；
4. `ContentOpportunity.evidence_summary` 等字段被保存；
5. `content_draft_v2` 生成草稿时，通过 experiment 找到对应 opportunity；
6. `_opportunity_snapshot()` 把 opportunity 里的证据字段带入上下文；
7. `_build_competitor_evidence_items()` 再把它映射成 `COMPETITOR_EVIDENCE` slot。

所以本次接入的是已经沉淀到内容机会里的真实上游证据摘要，而不是临时 mock 文案。

## 7. 怎么映射到 COMPETITOR_EVIDENCE slot

映射关系如下：

- `opportunity.opportunity_title` -> `title`
- `opportunity.suggested_angle` -> `summary`
- `opportunity.evidence_summary` -> `evidence_summary`
- `opportunity.content_pillar` -> `content_pillar`
- `opportunity.target_audience` -> `target_audience`
- `opportunity.comment_demand_type` -> `comment_demand_type`
- `opportunity.replicability_score` -> `confidence`
- `opportunity.risk_level` -> `risk_level`

实验信息作为辅助证据：

- `experiment.experiment_name` -> `title`
- `experiment.hypothesis` -> `summary`
- `experiment.content_pillar` -> `content_pillar`
- `experiment.content_format` -> `content_format`
- `experiment.risk_level` -> `risk_level`

没有明确来源的互动数没有乱填。比如不知道点赞数就不写 `like_count=0`，因为 0 应该代表真实的 0，而不是未知。

## 8. content_draft_v2 context 数据流怎么变化

修改前：

`experiment -> opportunity -> context_payload -> prompt -> built_context`

其中 `built_context` 里没有单独的 `COMPETITOR_EVIDENCE` slot，证据只可能混在 workflow state 里。

修改后：

`experiment -> opportunity -> context_payload -> competitor_evidence_items -> COMPETITOR_EVIDENCE slot -> Top-K -> built_context -> ContextSnapshot / ContextSlotLog`

也就是说，竞品证据现在有了独立 slot，后续可以单独看预算、是否压缩、选择了几条、丢弃了几条、来源是什么。

## 9. Top-K metadata 在哪里看到

可以在 `ContextSlotLog.metadata_payload["budget_meta"]` 里看到。

本次测试断言了这些字段：

- `source="competitor_report"`
- `data_status="REAL"`
- `compressed=True`
- `compression_method="deterministic_top_k"`
- `top_k=5`
- `selected_count>=1`

同时，`ContextSnapshot.slot_token_breakdown` 里也能看到 `competitor_evidence` 这个 slot 的预算统计。

## 10. 达到什么效果

现在 `content_draft_v2` 生成草稿时，不再只是依赖账号信息、实验状态和用户补充要求，还能把上游竞品报告沉淀出的真实证据以独立 slot 注入 LLM context。

这带来几个好处：

- 草稿生成有更明确的竞品依据；
- 竞品证据有独立预算，不会和 workflow state 混在一起；
- Top-K 压缩元数据可追踪；
- 没有证据时不会伪造；
- 外部来源文本被标记为 `untrusted`，降低 prompt injection 风险。

## 11. 没做什么

本次没有做这些事：

- 没有调用真实 LLM；
- 没有修改 prompt；
- 没有修改 LLMClient；
- 没有新增 Agent；
- 没有新增数据库字段；
- 没有新增 migration；
- 没有修改前端；
- 没有调用外部服务；
- 没有伪造生产竞品数据；
- 没有改旧版 `content_draft` 或 `review_report`；
- 没有改 `COMMENT_INSIGHT`、`STRATEGY_MEMORY`、`DOMAIN_PROFILE` 等其他 slot 策略；
- 没有重写 5.5.3 的 Top-K 算法。

## 12. 测试命令和结果

已运行：

```powershell
.\.venv\Scripts\python.exe -m pytest backend/tests/test_content_draft_v2.py -q -s -p no:cacheprovider --basetemp=.pytest_tmp
```

结果：`5 passed, 1 warning`

```powershell
.\.venv\Scripts\python.exe -m pytest backend/tests/test_context_budget.py -q -s -p no:cacheprovider --basetemp=.pytest_tmp
```

结果：`5 passed`

```powershell
.\.venv\Scripts\python.exe -m pytest backend/tests/test_context_engineering.py -q -s -p no:cacheprovider --basetemp=.pytest_tmp
```

结果：`6 passed`

```powershell
.\.venv\Scripts\python.exe -m pytest backend/tests/test_context_compressor.py -q -s -p no:cacheprovider --basetemp=.pytest_tmp
```

结果：`6 passed`

```powershell
.\.venv\Scripts\python.exe -m pytest backend/tests -q -x -p no:cacheprovider --basetemp=.pytest_tmp
```

结果：`128 passed, 1 warning`

warning 来自 Starlette TestClient 的 `DeprecationWarning`，不是本次功能失败。
