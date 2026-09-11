# 第 5.1.1 LLM / Context / Workflow 入口扫描报告

## 1. 扫描目的

本报告用于在 Context Engineering 前搞清楚项目中所有 LLM、Prompt、Context、Workflow 入口，避免只优化草稿生成而漏掉竞品分析、评论洞察、审核报告、Agent workflow 等链路。

## 2. 扫描范围

扫描目录：

- backend/app/services
- backend/app/agent
- backend/app/context
- backend/app/llm
- backend/app/api
- backend/app/repositories

关键词类别：LLM 调用、Prompt、Context、Agent / Workflow、业务链路关键词。

本次静态扫描 Python 文件数：97。

## 3. 当前 Agent 形态判断

- 当前未发现多个成熟独立 Agent 类。
- 当前检测到 workflow 文件数：1。
- 当前工程形态更接近单 Agent Runtime + 多步骤 workflow + 多个 service/tool 的混合形态。
- 它可以作为多 Agent 系统的雏形，但不应在简历中夸大为多个成熟自治 Agent。

## 4. 入口总览表

| 模块 | 文件 | 分类 | 是否直接调用 LLM | 调用方式 | prompt_key / version | schema_model | context 来源 | 是否 workflow step | 是否进入后续 LLM | 5.2 优先级 | 说明 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| keyword_seed | backend/app/api/keyword_seed_rout.py, backend/app/repositories/keyword_seed_repo.py, backend/app/services/keyword_seed_sev.py | API_ENTRY, CONTEXT_BUILDER, ORDINARY_SERVICE, REPOSITORY | 否 | - | - | - | service 构造 dict / repository 数据 | 否 | 需确认 | P2 | 未发现直接 LLM 调用，需按上下游关系人工确认。 |
| crawler_collection | backend/app/api/crawler_collection_rout.py, backend/app/api/xhs_note_rout.py, backend/app/repositories/crawler_collection_repo.py, backend/app/repositories/xhs_note_repo.py, backend/app/services/crawler_collection_sev.py, backend/app/services/demo_sev.py, backend/app/services/xhs_note_sev.py | API_ENTRY, ORDINARY_SERVICE, PROMPT_BUILDER, REPOSITORY, WORKFLOW_STEP | 否 | - | - | - | service 构造 dict / repository 数据 | 否 | 需确认 | P2 | 未发现直接 LLM 调用，需按上下游关系人工确认。 |
| competitor_report | backend/app/api/competitor_report_rout.py, backend/app/repositories/competitor_report_repo.py, backend/app/services/competitor_report_sev.py | API_ENTRY, ORDINARY_SERVICE, REPOSITORY | 否 | - | - | - | service 构造 dict / repository 数据 | 否 | 是 | P1 | 竞品报告输出会进入实验和草稿上下文。 |
| competitor_analysis | backend/app/api/competitor_analysis_rout.py, backend/app/repositories/competitor_analysis_repo.py, backend/app/services/competitor_analysis_sev.py | API_ENTRY, ORDINARY_SERVICE, REPOSITORY | 否 | - | - | - | service 构造 dict / repository 数据 | 否 | 是 | P1 | 分析型 service，当前更偏规则和数据聚合。 |
| competitor_account | backend/app/api/competitor_rout.py | API_ENTRY | 否 | - | - | - | service 构造 dict / repository 数据 | 否 | 需确认 | P2 | 未发现直接 LLM 调用，需按上下游关系人工确认。 |
| competitor_note | NOT_FOUND | NOT_FOUND | 否 | - | - | - | service 构造 dict / repository 数据 | 否 | 需确认 | P2 | 未发现直接 LLM 调用，需按上下游关系人工确认。 |
| comment_insight | backend/app/services/competitor_report_sev.py, backend/app/agent/tools/fallback_registry.py | ORDINARY_SERVICE, PROMPT_BUILDER, WORKFLOW_STEP | 否 | - | - | - | service 构造 dict / repository 数据 | 否 | 是 | P1 | 未发现独立成熟实现，当前主要嵌在竞品报告的评论需求识别链路中。 |
| content_opportunity | NOT_FOUND | NOT_FOUND | 否 | - | - | - | service 构造 dict / repository 数据 | 否 | 需确认 | P2 | 未发现直接 LLM 调用，需按上下游关系人工确认。 |
| content_experiment | backend/app/agent/workflows/content_experiment.py, backend/app/api/content_experiment_rout.py, backend/app/repositories/content_experiment_repo.py, backend/app/services/content_experiment_sev.py | API_ENTRY, ORDINARY_SERVICE, REPOSITORY, WORKFLOW_STEP | 否 | - | - | - | service 构造 dict / repository 数据 | 是 | 是 | P1 | Agent workflow 使用的实验创建工具之一。 |
| content_experiment_v2 | backend/app/api/content_experiment_v2_rout.py, backend/app/repositories/content_experiment_v2_repo.py, backend/app/services/content_experiment_v2_sev.py | API_ENTRY, ORDINARY_SERVICE, REPOSITORY | 否 | - | - | - | service 构造 dict / repository 数据 | 否 | 是 | P1 | 未发现直接 LLM 调用，需按上下游关系人工确认。 |
| content_draft | backend/app/api/content_draft_rout.py, backend/app/repositories/content_draft_repo.py, backend/app/services/content_draft_sev.py | API_ENTRY, CONTEXT_BUILDER, LLM_CALLER, PROMPT_BUILDER, REPOSITORY | 是 | generate_structured | xhs_writer_draft_generation, v1 | DraftGenerateResult | service 构造 dict / repository 数据 | 否 | 是 | P0 | 旧草稿生成链路，直接产生用户可见内容。 |
| content_draft_v2 | backend/app/agent/tools/local_registry.py, backend/app/api/content_draft_v2_rout.py, backend/app/repositories/content_draft_v2_repo.py, backend/app/services/content_draft_v2_sev.py | API_ENTRY, CONTEXT_BUILDER, LLM_CALLER, PROMPT_BUILDER, REPOSITORY, WORKFLOW_STEP | 是 | generate_structured, generate_structured_with_context | - | DraftGenerateV2Result | ContextManager / BuiltContext / ContextSnapshot | 否 | 是 | P0 | 已有 ContextManager、PromptRunLog、ContextSnapshot，是 5.2 重点。 |
| review_report | backend/app/api/review_report_rout.py, backend/app/repositories/review_report_repo.py, backend/app/services/review_report_sev.py | API_ENTRY, CONTEXT_BUILDER, LLM_CALLER, PROMPT_BUILDER, REPOSITORY | 是 | generate_structured | content_reviewer, v1 | DraftReviewResult | service 构造 dict / repository 数据 | 否 | 是 | P0 | 审核报告链路，直接影响风险和修改建议。 |
| confirmation | backend/app/agent/policies/stop.py, backend/app/agent/tools/base.py, backend/app/agent/tools/mcp_registry.py, backend/app/api/confirmation_rout.py, backend/app/repositories/confirmation_repo.py, backend/app/services/confirmation_sev.py | API_ENTRY, CONTEXT_BUILDER, ORDINARY_SERVICE, REPOSITORY, WORKFLOW_STEP | 否 | - | - | - | service 构造 dict / repository 数据 | 否 | 需确认 | P2 | 未发现直接 LLM 调用，需按上下游关系人工确认。 |
| post_publish | backend/app/api/optimization_rout.py, backend/app/api/post_publish_review_rout.py, backend/app/api/private_conversion_rout.py, backend/app/api/published_note_rout.py, backend/app/repositories/post_publish_repo.py, backend/app/services/post_publish_sev.py | API_ENTRY, ORDINARY_SERVICE, REPOSITORY | 否 | - | - | - | service 构造 dict / repository 数据 | 否 | 是 | P2 | 发布后指标和复盘基础，当前先登记，第一轮不纳入 prompt/token 统计。 |
| strategy_memory | backend/app/repositories/agent_run_repo.py, backend/app/repositories/startup_strategy_repo.py, backend/app/services/startup_strategy_sev.py | CONTEXT_BUILDER, ORDINARY_SERVICE, REPOSITORY | 否 | - | - | - | service 构造 dict / repository 数据 | 否 | 是 | P1 | 策略沉淀/检索，未来是上下文来源。 |
| agent_runtime | backend/app/agent/runtime.py | CONTEXT_BUILDER, WORKFLOW_STEP | 否 | - | - | - | service 构造 dict / repository 数据 | 是 | 需确认 | P2 | 统一 runtime，不是多个独立 Agent。 |
| context_engineering | backend/app/api/agent_run_rout.py, backend/app/api/context_rout.py, backend/app/context/__init__.py, backend/app/context/context_budget.py, backend/app/context/context_builder.py, backend/app/context/context_compressor.py, backend/app/context/context_sanitizer.py, backend/app/context/context_slots.py, backend/app/context/context_snapshot.py, backend/app/context/context_usage_logger.py, backend/app/services/developer_trace_sev.py | API_ENTRY, CONTEXT_BUILDER, PROMPT_BUILDER, WORKFLOW_STEP | 否 | - | - | - | ContextManager / BuiltContext / ContextSnapshot | 否 | 需确认 | P1 | 上下文构建、预算、压缩、日志基础设施。 |
| llm_infra | backend/app/api/llm.py, backend/app/api/provider_health_rout.py, backend/app/llm/__init__.py, backend/app/llm/client.py, backend/app/llm/cost.py, backend/app/llm/errors.py, backend/app/llm/mock_client.py, backend/app/llm/providers/__init__.py, backend/app/llm/providers/base.py, backend/app/llm/providers/deepseek_provider.py, backend/app/llm/providers/mock_provider.py, backend/app/llm/providers/qwen_provider.py, backend/app/llm/router.py | API_ENTRY, CONTEXT_BUILDER, LLM_CALLER, LLM_INFRA, PROMPT_BUILDER | 是 | generate_structured, generate_structured_with_context, generate_text | provider_health_test_text, v1 | LLMTestAnalysisResult | service 构造 dict / repository 数据 | 否 | 需确认 | P2 | LLM provider/client 基础设施，不是业务 context 链路；后续只承担 token、latency、metadata 记录。 |

## 5. 普通 Service / Workflow Step / LLM Caller 分类

### 5.1 普通 Service

- `backend/app/services/__init__.py`：模块 `unknown`；是否构造 context：False；是否调用 LLM：否；是否进入后续 LLM：需按上下游确认。
- `backend/app/services/account_sev.py`：模块 `unknown`；是否构造 context：False；是否调用 LLM：否；是否进入后续 LLM：需按上下游确认。
- `backend/app/services/agent_run_sev.py`：模块 `unknown`；是否构造 context：False；是否调用 LLM：否；是否进入后续 LLM：需按上下游确认。
- `backend/app/services/competitor_analysis_sev.py`：模块 `competitor_analysis`；是否构造 context：False；是否调用 LLM：否；是否进入后续 LLM：需按上下游确认。
- `backend/app/services/competitor_report_sev.py`：模块 `competitor_report`；是否构造 context：False；是否调用 LLM：否；是否进入后续 LLM：需按上下游确认。
- `backend/app/services/confirmation_sev.py`：模块 `confirmation`；是否构造 context：True；是否调用 LLM：否；是否进入后续 LLM：需按上下游确认。
- `backend/app/services/content_experiment_sev.py`：模块 `content_experiment`；是否构造 context：False；是否调用 LLM：否；是否进入后续 LLM：需按上下游确认。
- `backend/app/services/content_experiment_v2_sev.py`：模块 `content_experiment_v2`；是否构造 context：False；是否调用 LLM：否；是否进入后续 LLM：需按上下游确认。
- `backend/app/services/crawler_collection_sev.py`：模块 `crawler_collection`；是否构造 context：False；是否调用 LLM：否；是否进入后续 LLM：需按上下游确认。
- `backend/app/services/eval_sev.py`：模块 `unknown`；是否构造 context：False；是否调用 LLM：否；是否进入后续 LLM：需按上下游确认。
- `backend/app/services/keyword_seed_sev.py`：模块 `keyword_seed`；是否构造 context：True；是否调用 LLM：否；是否进入后续 LLM：需按上下游确认。
- `backend/app/services/post_publish_sev.py`：模块 `post_publish`；是否构造 context：False；是否调用 LLM：否；是否进入后续 LLM：需按上下游确认。
- `backend/app/services/provider_health_sev.py`：模块 `provider_health`；是否构造 context：False；是否调用 LLM：否；是否进入后续 LLM：否，作为健康检查登记对象。
- `backend/app/services/startup_strategy_sev.py`：模块 `strategy_memory`；是否构造 context：False；是否调用 LLM：否；是否进入后续 LLM：需按上下游确认。
- `backend/app/services/xhs_note_sev.py`：模块 `crawler_collection`；是否构造 context：False；是否调用 LLM：否；是否进入后续 LLM：需按上下游确认。

### 5.2 Workflow Step / Tool

- `backend/app/agent/__init__.py`：分类 `WORKFLOW_STEP`；input/output 可能进入 Agent trace；需要记录 Context Snapshot：视是否接 LLM 而定。
- `backend/app/agent/observability.py`：分类 `WORKFLOW_STEP`；input/output 可能进入 Agent trace；需要记录 Context Snapshot：视是否接 LLM 而定。
- `backend/app/agent/policies/__init__.py`：分类 `WORKFLOW_STEP`；input/output 可能进入 Agent trace；需要记录 Context Snapshot：视是否接 LLM 而定。
- `backend/app/agent/policies/fallback.py`：分类 `WORKFLOW_STEP`；input/output 可能进入 Agent trace；需要记录 Context Snapshot：视是否接 LLM 而定。
- `backend/app/agent/policies/guardrail.py`：分类 `WORKFLOW_STEP`；input/output 可能进入 Agent trace；需要记录 Context Snapshot：视是否接 LLM 而定。
- `backend/app/agent/policies/stop.py`：分类 `WORKFLOW_STEP`；input/output 可能进入 Agent trace；需要记录 Context Snapshot：视是否接 LLM 而定。
- `backend/app/agent/runtime.py`：分类 `CONTEXT_BUILDER, WORKFLOW_STEP`；input/output 可能进入 Agent trace；需要记录 Context Snapshot：视是否接 LLM 而定。
- `backend/app/agent/tools/__init__.py`：分类 `WORKFLOW_STEP`；input/output 可能进入 Agent trace；需要记录 Context Snapshot：视是否接 LLM 而定。
- `backend/app/agent/tools/base.py`：分类 `WORKFLOW_STEP`；input/output 可能进入 Agent trace；需要记录 Context Snapshot：视是否接 LLM 而定。
- `backend/app/agent/tools/fallback_registry.py`：分类 `PROMPT_BUILDER, WORKFLOW_STEP`；input/output 可能进入 Agent trace；需要记录 Context Snapshot：视是否接 LLM 而定。
- `backend/app/agent/tools/local_registry.py`：分类 `CONTEXT_BUILDER, WORKFLOW_STEP`；input/output 可能进入 Agent trace；需要记录 Context Snapshot：是。
- `backend/app/agent/tools/mcp_registry.py`：分类 `WORKFLOW_STEP`；input/output 可能进入 Agent trace；需要记录 Context Snapshot：视是否接 LLM 而定。
- `backend/app/agent/tools/registry.py`：分类 `WORKFLOW_STEP`；input/output 可能进入 Agent trace；需要记录 Context Snapshot：视是否接 LLM 而定。
- `backend/app/agent/workflows/__init__.py`：分类 `WORKFLOW_STEP`；input/output 可能进入 Agent trace；需要记录 Context Snapshot：视是否接 LLM 而定。
- `backend/app/agent/workflows/content_experiment.py`：分类 `WORKFLOW_STEP`；input/output 可能进入 Agent trace；需要记录 Context Snapshot：视是否接 LLM 而定。
- `backend/app/context/context_builder.py`：分类 `PROMPT_BUILDER, CONTEXT_BUILDER, WORKFLOW_STEP`；input/output 可能进入 Agent trace；需要记录 Context Snapshot：是。
- `backend/app/context/context_compressor.py`：分类 `CONTEXT_BUILDER, WORKFLOW_STEP`；input/output 可能进入 Agent trace；需要记录 Context Snapshot：是。
- `backend/app/services/demo_sev.py`：分类 `PROMPT_BUILDER, WORKFLOW_STEP`；input/output 可能进入 Agent trace；需要记录 Context Snapshot：视是否接 LLM 而定。
- `backend/app/services/developer_trace_sev.py`：分类 `PROMPT_BUILDER, CONTEXT_BUILDER, WORKFLOW_STEP`；input/output 可能进入 Agent trace；需要记录 Context Snapshot：是。

### 5.3 直接 LLM Caller

- `backend/app/api/llm.py`：调用方式 `generate_structured, generate_text`；schema_model `LLMTestAnalysisResult`；prompt_key `-`；已由 LLMClient 结构化校验兜底：是；是否进入 5.2：视入口性质登记。
- `backend/app/api/provider_health_rout.py`：调用方式 `generate_text`；schema_model `-`；prompt_key `provider_health_test_text`；已由 LLMClient 结构化校验兜底：是；是否进入 5.2：视入口性质登记。
- `backend/app/llm/client.py`：调用方式 `generate_structured, generate_structured_with_context, generate_text`；schema_model `-`；prompt_key `-`；已由 LLMClient 结构化校验兜底：是；是否进入 5.2：视入口性质登记。
- `backend/app/llm/mock_client.py`：调用方式 `generate_structured, generate_structured_with_context, generate_text`；schema_model `-`；prompt_key `-`；已由 LLMClient 结构化校验兜底：是；是否进入 5.2：视入口性质登记。
- `backend/app/llm/providers/base.py`：调用方式 `generate_structured, generate_text`；schema_model `-`；prompt_key `-`；已由 LLMClient 结构化校验兜底：是；是否进入 5.2：视入口性质登记。
- `backend/app/llm/providers/mock_provider.py`：调用方式 `generate_structured, generate_text`；schema_model `-`；prompt_key `-`；已由 LLMClient 结构化校验兜底：是；是否进入 5.2：视入口性质登记。
- `backend/app/services/content_draft_sev.py`：调用方式 `generate_structured`；schema_model `DraftGenerateResult`；prompt_key `xhs_writer_draft_generation`；已由 LLMClient 结构化校验兜底：是；是否进入 5.2：是。
- `backend/app/services/content_draft_v2_sev.py`：调用方式 `generate_structured, generate_structured_with_context`；schema_model `DraftGenerateV2Result`；prompt_key `-`；已由 LLMClient 结构化校验兜底：是；是否进入 5.2：是。
- `backend/app/services/review_report_sev.py`：调用方式 `generate_structured`；schema_model `DraftReviewResult`；prompt_key `content_reviewer`；已由 LLMClient 结构化校验兜底：是；是否进入 5.2：是。

## 6. 未来适合拆成 Agent 的模块

| 候选 Agent | 当前代码位置 | 当前形态 | 为什么适合拆 | 输入 | 输出 | 是否需要 LLM | 优先级 |
|---|---|---|---|---|---|---|---|
| Research / Collection Agent | app/services/crawler_collection_sev.py, app/crawler/* | 普通 service / provider 调度 | 需要根据数据来源、权限和质量决定采集策略，输出会进入竞品分析和内容机会链路。 | 账号、关键词、采集目标、provider 状态 | 竞品账号、笔记、评论、采集状态 | 未来可能需要 | P1 |
| Competitor Analysis Agent | app/services/competitor_report_sev.py, app/services/competitor_analysis_sev.py | 规则分析 service | 消费竞品账号、笔记、评论，输出会影响机会生成和草稿上下文。 | 竞品账号、竞品笔记、评论样本 | 报告、标签、标题模式、内容洞察 | 适合引入 | P1 |
| Viral Note Analysis Agent | app/services/competitor_report_sev.py | 报告 service 的一部分 | 爆款拆解有明确输入输出，适合独立评测结构化结果。 | 高互动竞品笔记 | 标题模式、内容结构、爆点、可复用套路 | 适合引入 | P1 |
| Comment Insight Agent | app/services/competitor_report_sev.py | 报告 service 的一部分，未发现独立成熟实现 | 评论需求识别会影响内容机会和草稿角度。 | 评论样本 | 痛点、疑问、购买/收藏动机 | 适合引入 | P1 |
| Opportunity Agent | app/services/content_experiment_v2_sev.py, app/services/competitor_report_sev.py | 普通 service / 规则生成 | 负责把分析结果转成可执行选题机会，输出进入实验和草稿。 | 竞品报告、账号定位、历史表现 | 内容机会、证据、风险和优先级 | 适合引入 | P1 |
| Experiment Planning Agent | app/agent/workflows/content_experiment.py, app/services/content_experiment*_sev.py | Agent workflow step + 普通 service | 实验设计是明确决策点，有目标、变量和成功标准。 | 账号、竞品笔记、内容机会 | 内容实验、假设、指标、目标值 | 未来可能需要 | P0/P1 |
| Writer Agent | app/services/content_draft_sev.py, app/services/content_draft_v2_sev.py | 直接 LLM caller | 直接生成用户可见内容，已有 schema、prompt、context 和失败不入库测试。 | 账号、实验、机会、用户要求、策略记忆 | 结构化草稿 | 是 | P0 |
| Reviewer Agent | app/services/review_report_sev.py | 直接 LLM caller | 决定风险、分数和修改建议，直接影响发布前确认。 | 草稿、账号、实验 | 审核报告 | 是 | P0 |
| Post-publish Analytics Agent | app/services/post_publish_sev.py | 普通 service / 指标回采 | 复盘需要结合发布后指标和目标，未来适合形成策略建议。 | 发布后指标、实验目标、审核记录 | 复盘结论、优化建议 | 未来可能需要 | P2（5.2 先登记） |
| Memory Agent | app/services/startup_strategy_sev.py, local_registry strategy_memory tools | 普通 service / tool | 策略沉淀和检索会成为后续上下文的重要来源。 | 复盘结果、策略、历史内容表现 | 可检索策略记忆 | 未来可能需要 | P1/P2 |

## 7. 第 5.2 建议统计范围

### P0

- `content_draft_v2`：V2 草稿生成使用 ContextManager、PromptRunLog、ContextSnapshot，最适合做 token/context 基线。
- `content_draft`：旧草稿生成直接调用 LLM structured，直接产生用户可见内容。
- `review_report`：审核报告直接调用 LLM structured，决定风险和修改建议。

说明：`LLMClient` / `llm_infra` 不是业务 P0 统计对象。它是统一调用基础设施，后续负责记录 token、latency、model、provider、metadata、error 等调用观测字段，但不代表一个独立业务 context 链路。

### P1

- `competitor_report`：竞品报告当前未发现直接 LLM 调用，但输出进入实验和草稿上下文。
- `competitor_analysis`：竞品分析结果影响后续机会和草稿，需要登记上下游字段。
- `content_experiment`：ContentExperimentWorkflow 串联账号、竞品笔记和实验创建，是 workflow step 基线。
- `content_experiment_v2`：实验/机会链路输出进入草稿生成，当前未发现直接 LLM 调用但应统计输入输出。
- `comment_insight`：评论需求识别当前主要嵌在 `competitor_report` 中，需登记其结构化字段和硬编码来源。
- `strategy_memory`：策略记忆会成为 Writer/Reviewer 上下文来源。
- `context_engineering`：ContextManager、budget、snapshot 是 5.2 统计的承载基础，但不作为业务入口单独计算产出质量。

### P2

- `crawler_collection`：采集链路主要是 provider/数据状态治理，暂未发现直接 LLM 调用。
- `keyword_seed`：关键词种子当前更像规则/CRUD 输入准备。
- `confirmation`：人工确认是治理节点，不是 LLM 调用入口。
- `post_publish`：发布后指标、复盘和优化计划当前先登记，第一轮不做 prompt/token 统计。
- `API route`：只登记入口和上下游关系。
- `repository`：只登记数据来源和字段，不做第一轮统计。
- `provider_health`：健康检查入口，不作为业务 context 链路。
- `llm_infra`：LLMClient / providers / router / cost / errors 只登记基础设施观测字段。

竞品分析和同行账号是否需要统计：当前未发现直接 LLM 调用；但 `competitor_report` / `competitor_analysis` 存在硬编码领域规则，并且其输出会进入内容实验、机会判断和草稿上下文，因此不能忽略。第 5.2 先登记其输出字段、硬编码来源、样本量、数据状态和下游使用位置。如果后续接入 LLM 分析，再升级为 P0。

## 8. 第 5.2 统计口径确认

第 5.2 第一版只做统计口径落地，不解决硬编码领域词，不设计或实现 `domain_profile` / `domain_vocabulary`。领域词动态化放到第 5.3。

P0 统计 prompt/token/context：

- `content_draft_v2`
- `content_draft`
- `review_report`

P1 统计上游结构化字段和是否进入下游 context：

- `competitor_report`
- `competitor_analysis`
- `content_experiment`
- `content_experiment_v2`
- `comment_insight`：当前主要嵌在 `competitor_report` 的评论需求识别中，没有独立成熟 service，但其输出会影响 opportunity、experiment 和 draft。
- `strategy_memory`
- `context_engineering`

P2 只登记，不做第一轮统计：

- `crawler_collection`
- `keyword_seed`
- `confirmation`
- `post_publish`
- `API route`
- `repository`
- `provider_health`
- `llm_infra`

`competitor_report` / `competitor_analysis` 虽然当前没有直接调用 LLM，但包含标题模式、内容支柱、人设、评论需求、机会生成等硬编码领域规则。第 5.2 必须记录这些字段是否进入后续 context，尤其是是否通过 analysis report、content opportunity、experiment snapshot、strategy memory 进入草稿生成和审核报告。

## 9. 风险和疑问

- competitor_report / competitor_analysis 当前未发现直接 LLM 调用，但其输出会进入实验和草稿上下文，需人工确认第 5.2 是否纳入 P1 字段基线。
- comment_insight 未发现独立成熟 service，可能嵌在竞品报告或评论处理逻辑中。
- content_draft_sev.py 使用 prompt_key，但未记录 ContextSnapshot；content_draft_v2_sev.py 已记录 PromptRunLog 和 ContextSnapshot。
- api/llm.py 与 provider_health_rout.py 是测试/健康检查入口，不应当算入业务 Agent，但应登记为 LLM 调用入口。
- 当前未发现多个成熟独立 Agent 类；不要在简历中夸大为多个自治 Agent。
- 未发现独立 content_opportunity service 文件，机会生成可能在 experiment/report 链路中，需要人工确认。

## 10. 硬编码账号领域假设扫描

本节只做静态扫描、分类和可行性评估，不把规则改成固定的 `DOMAIN_TITLE_PATTERNS` 字典，也不新增任何 LLM 调用或数据库字段。

### 10.1 分类标准

- A. 通用内容结构规则：可暂时保留，例如数字清单型、方法教程型、避坑警示型、路线步骤型、对比型。
- B. 当前账号领域词：不应长期写死，例如大学生、双非、Agent、项目、简历、面试、上岸、求职。
- C. Prompt 中写死的账号定位：后续应从 account_profile / domain_profile 注入。
- D. 测试数据 / demo 数据：可以保留，但必须标记为 test/demo，不进入生产默认链路。

### 10.2 硬编码位置明细

| 文件 | 函数/位置 | 硬编码内容 | 所属模块 | 是否通用 | 是否依赖当前账号赛道 | 是否进入 LLM context | 影响下游 | 风险 | 建议处理方式 |
| -- | ----- | ----- | ---- | ---- | ---------- | ---------------- | ---- | -- | ------ |
| `backend/app/services/competitor_report_sev.py` | `COMMENT_DEMAND_RULES` | 项目、实战、作品、案例、源码、代码、github、课程、咨询、普通本科、没基础、割韭菜等 | 评论需求识别 / 竞品报告 | 部分通用 | 是，`PROJECT`、`SOURCE_CODE`、`ANXIETY` 更偏学习/项目赛道 | 是，报告和 opportunity 会进入后续草稿 context | comment_demands、content_opportunity、experiment、draft | 摄影接单评论里的“报价、档期、客片、修图、地点”可能识别不足，反而把“项目/课程”权重放大 | 短期保留通用需求类型；领域词后续迁移到动态 `domain_profile`，由账号画像和真实样本校正 |
| `backend/app/services/competitor_report_sev.py` | `TITLE_PATTERN_RULES` | 人群痛点型：普通、大学生、小白、新手、零基础；项目求职型：项目、实战、简历、面试、求职 | 标题模式识别 / 爆款拆解 | 部分通用 | 是 | 是，`title_patterns` 会写入报告并被草稿读取 | title_patterns、viral_breakdown、content_insights、draft prompt | 摄影账号的“客片展示、价格说明、拍前准备、成都约拍”不会被识别，标题模式会偏向学习求职 | A 类结构词保留；B 类人群/求职词改为动态配置，不要手写行业字典 |
| `backend/app/services/competitor_report_sev.py` | `CONTENT_PILLAR_RULES` | 学习路线、项目实战、求职简历、资源工具、避坑复盘 | 竞品笔记分析 / 内容支柱 | 部分通用 | 是 | 是，content_pillars 会进入 opportunity 和 experiment | 内容机会生成、实验设计、草稿上下文 | 摄影账号会被错分成学习路线/项目实战，漏掉客片、约拍、场景、价格、妆造、修图 | 后续把 pillar 候选从 `domain_profile.title_pattern_keywords / pain_point_keywords` 生成 |
| `backend/app/services/competitor_report_sev.py` | `_detect_persona` | 项目学姐/学长、求职导师、资源整理号、实战教程号 | 同行账号分析 | 否 | 是 | 间接进入报告输出 | persona_patterns、竞品报告摘要 | 兼职摄影师同行会被误归到知识分享号，无法识别本地摄影师、客片摄影、约拍档期号 | 改为由账号领域动态生成 persona labels，真实竞品样本二次校正 |
| `backend/app/services/competitor_report_sev.py` | `_detect_cover_pattern` | 结果展示封面：简历、项目、作品；路线承诺封面：路线、步骤、顺序 | 爆款拆解 / 封面模式 | 部分通用 | 是 | 是，viral_breakdown 会进入报告详情和后续参考 | 爆款拆解、草稿封面提示 | 摄影“作品/客片”可能偶然命中，但“简历/项目”语义不适配，会影响封面建议 | 保留“结果展示”这种结构名，关键词改由 domain_profile 提供 |
| `backend/app/services/competitor_report_sev.py` | `_detect_content_structure` | 项目-拆解-求职表达：项目、拆解、简历 | 爆款拆解 / 内容结构 | 否 | 是 | 是，breakdown / insights 可作为下游 context | 爆款拆解、内容机会、草稿结构 | 摄影内容更常见“客片-场景-报价/预约”或“问题-准备-成片”，当前会失效 | 结构标签保留为可扩展槽位，领域词动态生成 |
| `backend/app/services/competitor_report_sev.py` | `_build_opportunities` fallback | 默认 `学习路线` | 内容机会生成 | 否 | 是 | 是，opportunity 进入 experiment 和 draft v2 context | content_opportunity、content_experiment_v2、draft_v2 | 无样本或弱样本时，摄影账号会退回学习路线机会 | fallback 改造时从 account_profile/domain_profile 取默认 pillar |
| `backend/app/services/competitor_report_sev.py` | `_high_note_reason` / `_build_suggestions` | 标题包含路线、项目或求职信号；评论需求里出现资源、项目、咨询信号 | 爆款拆解 / 建议 | 部分通用 | 是 | 是，report suggestions 可进入草稿 context | report suggestions、draft | 摄影账号的“价格、档期、客片、修图、地点”不会形成建议 | 将“转化信号”拆成通用类型 + 领域关键词 |
| `backend/app/services/competitor_analysis_sev.py` | `_detect_title_patterns` | 普通、大学生、小白、新手、零基础、项目、实战、简历、面试 | 旧竞品分析 / 标题模式识别 | 部分通用 | 是 | 是，旧 analysis_report 会被草稿读取 | content_experiment、content_draft | 摄影账号标题会被误判或落入普通表达型，实验角度偏差 | 与 V2 统一为动态 domain_profile；旧链路至少标注低置信 |
| `backend/app/services/competitor_analysis_sev.py` | `_build_suggestions` | 学习类账号的转化行为 | 旧竞品分析 / 建议 | 否 | 是 | 是，suggestions 进入旧草稿 context | content_draft | 摄影接单账号转化目标是咨询/约拍/报价，不是学习收藏 | 后续从 account.primary_goal / monetization_goal 注入，不写死学习类 |
| `backend/app/services/keyword_seed_sev.py` | `KEYWORD_TEMPLATES` | 学习路线、项目实战、项目模板、简历项目、求职作品集、普通大学生、转码初学者、零基础、应届生 | 关键词种子 | 部分通用 | 是 | 间接进入采集、竞品报告和下游 context | crawler_collection、competitor_report、draft | 摄影账号会生成完全错误的关键词，导致采集样本源头偏掉 | 保留模板机制，但模板内容应由 domain_profile 动态生成或人工确认 |
| `backend/app/services/content_experiment_sev.py` | `_format_keyword_topic` | `{keyword} 学习路线` | 内容实验设计 | 否 | 是 | 是，selected_topic 进入草稿 context | content_experiment、content_draft | 摄影关键词会被包装成“摄影 学习路线”，不符合接单目标 | fallback topic 从账号目标和 domain_profile 的 title pattern 生成 |
| `backend/app/services/content_experiment_v2_sev.py` | `EXPERIMENT_VARIANTS` | 痛点标题 + 路线图、问题-步骤-总结、普通学生视角 | 内容实验设计 V2 | 部分通用 | 是 | 是，experiment_snapshot 进入 draft_v2 context | experiment_v2、draft_v2 | 摄影账号需要客片展示、价格说明、拍前准备、预约转化，而不是普通学生视角 | 保留“变量”框架，format_hint 从 domain_profile 注入 |
| `backend/app/services/content_draft_sev.py` | `_mock_generate_result` | 普通大学生、AI Agent、项目实战、大学生求职、简历、项目拆解 | 草稿生成 mock | 否 | 是 | 仅 `use_mock=True` 时进入 draft | 草稿生成 / demo | 如果生产显式误开 use_mock，会输出 Agent 求职内容；默认治理后风险降低 | D 类保留，但继续确保 mock 只能显式启用，并在报告/trace 标记 mock |
| `backend/app/services/review_report_sev.py` | `_mock_review_result` | 学习类账号定位、学习顺序、项目路线 | 审核报告 mock | 否 | 是 | 仅 `use_mock=True` 时进入 review result | 审核报告 / demo | 摄影草稿被 mock 审核时会按学习类账号给建议 | D 类保留，但标记 mock/demo；真实审核 prompt 应依赖 account_profile |
| `backend/app/prompts/xhs_writer.py` | `XHS_WRITER_SYSTEM_PROMPT` 第 8 条 | 适合普通大学生、自学者或账号目标用户理解 | Prompt 模板 / 旧草稿生成 | 部分通用 | 是 | 是，直接进入 LLM system prompt | content_draft | 摄影账号会被系统 prompt 拉向“学生/自学者”语气 | C 类，后续改为从 account_profile.target_audience 注入，不写死学生 |
| `backend/app/prompts/xhs_draft_v2.py` | `SYSTEM_PROMPT` | job offers、knowledge-account | Prompt 模板 / V2 草稿生成 | 部分通用 | 轻度依赖知识账号 | 是，直接进入 LLM system prompt | content_draft_v2 | 摄影接单账号不是纯知识号，`knowledge-account` 会约束内容形态 | C 类，后续让账号类型决定 writer role；风险约束保留为通用/可配置 |
| `backend/app/prompts/content_reviewer.py` | `CONTENT_REVIEWER_SYSTEM_PROMPT` | 包就业、焦虑营销等风险 | Prompt 模板 / 审核报告 | 部分通用 | 轻度依赖求职赛道 | 是，直接进入 LLM system prompt | review_report | 对摄影账号仍需要“虚假客片、价格误导、肖像授权”等风险，目前缺失 | C 类，基础风险保留，领域风险从 domain_profile.risk_keywords 注入 |
| `backend/app/crawler/providers/seed_sample.py` | `collect` / `_build_note` | AI Agent、项目学姐、学习路线、项目实战、求职经验、普通大学生、简历项目 | Seed/demo 采集样本 | 否 | 是 | 如果进入报告会影响下游；当前已治理为非生产默认 | crawler_collection、competitor_report | 作为真实样本会污染摄影账号分析 | D 类保留，仅测试/demo 显式启用，trace 标记 `source_type=SEED_SAMPLE` / `is_mock=True` |
| `backend/app/crawler/mock_provider.py` | `crawl_note` | 普通大学生、AI Agent、项目实战、大学生求职、学习路线 | Mock 采集样本 | 否 | 是 | 如果 mock 结果入库并参与报告会影响下游；当前应显式 mock | crawler_collection、xhs_note、competitor_analysis | 摄影账号会收到完全错误样本 | D 类保留，仅接口联调/演示，生产默认不得使用 |
| `backend/app/llm/mock_client.py` | mock structured result | AI Agent project、backend project、content growth、FastAPI | Mock LLM 输出 | 否 | 是 | 仅 mock LLM 路径 | content_draft / review 测试 | 生产误用 MockLLMProvider 会污染草稿 | D 类保留，生产默认不得 fallback 到 MockLLMProvider |
| `backend/tests/*.py` | 测试 fixture / 断言样本 | 双非、27届、AI Agent、简历、面试、求职、学习路线等 | 测试数据 | 否 | 是 | 不进入生产链路 | 测试覆盖 | 可读性上容易让人误以为产品只支持该赛道 | D 类保留，但后续新增摄影/本地服务类测试覆盖泛化能力 |

### 10.3 模块覆盖判断

- 标题模式识别：`competitor_report_sev.py`、`competitor_analysis_sev.py` 存在明显赛道词。
- 同行账号分析：`competitor_report_sev.py::_detect_persona` 存在项目/求职人设。
- 竞品笔记分析：`CONTENT_PILLAR_RULES`、`_detect_content_structure` 存在学习/项目/求职偏置。
- 爆款拆解：`_build_breakdowns` 使用标题、封面、结构、评论需求规则，受上述词表影响。
- 评论需求识别：`COMMENT_DEMAND_RULES` 有通用需求，但项目/源码/课程/普通本科偏学习赛道。
- 内容机会生成：`_build_opportunities` 默认学习路线，并使用 content_pillars/comment_demands。
- 内容实验设计：旧版 `_format_keyword_topic` 和 V2 `EXPERIMENT_VARIANTS` 存在学习路线/普通学生视角。
- 草稿生成：旧 `content_draft_sev.py` mock 和 `xhs_writer.py` prompt 有学生/自学者定位；V2 主要依赖上游 context。
- 审核报告：真实 prompt 有求职风险约束但尚可通用；mock 审核写死学习类账号。
- 发布后复盘：未发现明显当前账号赛道词，主要是指标和策略记忆逻辑。
- 策略记忆：服务本身未写死赛道，但会保存上游复盘/实验产生的领域偏差。
- prompt 模板：旧 writer 明显写死学生，自 V2 起更通用但仍有 knowledge-account 假设。
- context 构造：`ContextManager` 和 slot 定义本身通用；`content_draft_v2_sev.py` 会把 account、experiment、opportunity、strategy_memory 注入，所以会放大上游硬编码结果。

### 10.4 摄影师接单账号的失效点

如果用户不是“27届双非本上岸 Agent 开发”，而是“兼职摄影师想通过小红书接单”，当前会出现这些失效：

- 关键词源头会偏：`keyword_seed_sev.py` 会生成学习路线、项目实战、简历项目、求职作品集，而不是成都约拍、情侣写真、毕业照、客片、价格、档期、拍前准备。
- 竞品标题模式会偏：摄影标题常见的客片展示型、价格说明型、地点场景型、拍前准备型无法被稳定识别。
- 同行人设会偏：本地摄影师、约拍摄影师、客片号、写真工作室不会被 `_detect_persona` 识别。
- 评论需求会偏：摄影用户更关注价格、档期、地点、修图、出片周期、风格、服装妆造、隐私授权，当前规则主要识别项目、源码、课程、咨询。
- 内容机会会偏：fallback 到“学习路线”会直接错题，导致实验和草稿方向跑偏。
- 实验变量会偏：`普通学生视角`、`路线图` 不适合接单转化；摄影更需要客片信任、价格透明、预约动作和本地搜索。
- 旧草稿和旧 writer prompt 会偏：学生/自学者语气会影响商业接单文案。
- 审核风险会漏：摄影账号需要关注虚假客片、价格误导、肖像授权、过度修图承诺、未成年人拍摄合规等领域风险，目前缺失。

## 11. 账号领域词动态生成方案可行性

目标不应该是手写 `agent_career`、`photography_client`、`fitness_coach`、`beauty`、`local_life` 等固定词表，而是让系统基于用户账号画像和真实样本生成统一的领域词配置。

### 11.1 建议的统一变量

建议未来统一成一个可版本化的 `domain_profile`，形态类似：

```json
{
  "domain_keywords": [],
  "audience_keywords": [],
  "pain_point_keywords": [],
  "conversion_keywords": [],
  "title_pattern_keywords": {},
  "risk_keywords": [],
  "negative_keywords": []
}
```

### 11.2 当前可直接接收的模块

- `content_draft_v2_sev.py`：已经有 `ACCOUNT_PROFILE`、`WORKFLOW_STATE`、`STRATEGY_MEMORY`、`RISK_CONSTRAINTS`、`OUTPUT_SCHEMA` slot，后续可新增或复用 context slot 注入 `domain_profile`。
- `ContextManager` / `ContextSlot`：本身是通用上下文容器，可以承载动态领域词，不需要先大改框架。
- `content_draft_sev.py` / `review_report_sev.py`：已通过 context dict 构造 prompt，后续可以把 `domain_profile` 放入 context。
- `content_experiment_v2_sev.py`：实验卡构造已经消费 opportunity/account 字段，后续可读取动态 title patterns、conversion keywords、risk keywords。
- `competitor_report_sev.py`：规则入口集中在几个字典和 `_detect_by_rules`，从工程形态看适合替换为配置输入，但需要改造函数签名和数据来源。

### 11.3 需要改造才能接收的模块

- `keyword_seed_sev.py`：当前模板写死在 `KEYWORD_TEMPLATES`，需要从静态模板改成“通用槽位模板 + domain_profile 词项”。
- `competitor_analysis_sev.py`：旧链路规则散在函数中，需要统一抽出配置来源。
- `competitor_report_sev.py`：需要把 `COMMENT_DEMAND_RULES`、`TITLE_PATTERN_RULES`、`CONTENT_PILLAR_RULES`、persona、cover、structure 等规则改为可注入配置，并保留通用结构规则作为 fallback。
- `content_experiment_sev.py`：旧版 topic fallback 需要从 `学习路线` 改为账号目标/领域配置。
- prompt 模板：旧 writer / reviewer 需要把账号定位、人群和领域风险从变量注入，而不是 system prompt 写死。
- 测试体系：需要增加非 AI Agent 赛道 fixture，例如兼职摄影师、本地服务、健身教练，用来防止回归。

### 11.4 变量放在哪里

推荐分层：

- `account_profile`：保存用户原始账号画像，例如 account_type、goal、target_audience、city、content_style。
- `domain_profile`：保存从账号画像和样本中生成的领域词配置，是业务可复用的派生画像。
- `context slot`：LLM 调用时注入 `domain_profile`，建议新增 `DOMAIN_PROFILE` slot 或放入 `ACCOUNT_PROFILE` 的子字段；从可观测性上独立 slot 更清晰。
- `strategy memory`：不适合作为唯一来源，但适合沉淀已验证有效/无效的领域表达。
- `prompt input`：每次 LLM 调用应显式传入当前版本的 `domain_profile` 摘要和版本号。

### 11.5 是否入库、人工确认、版本号和样本校正

- 是否入库：建议入库。原因是要可复现、可回滚、可审计；否则同一账号每次生成的领域词可能漂移。
- 是否需要人工确认：建议需要。尤其是起号定位、转化词、风险词，应该由用户确认后进入生产默认链路。
- 是否需要版本号：需要。建议至少记录 `domain_profile_version`、生成来源、确认状态、更新时间、样本范围。
- 是否需要和真实竞品样本校正：需要。仅根据账号画像生成会有主观偏差，真实竞品标题、评论、标签、私信/线索反馈应参与校正。
- 是否需要 LLM：未来适合由 LLM 生成候选，但本阶段不新增调用。生产实现时应使用严格 schema，并标记 `generated_by`、`source_samples`、`human_confirmed`。

### 11.6 对后续 prompt/token 统计的影响

- 第 5.2 第一版不引入 `domain_profile_tokens`、`domain_profile_version`、`domain_profile_source`、`human_confirmed` 等新字段，只记录硬编码领域词是否进入后续 context。
- 第 5.3 设计 `domain_profile` / `domain_vocabulary` 后，再考虑单独统计 `DOMAIN_PROFILE` slot 的 tokens，避免和 account profile 混在一起。
- 对 `competitor_report` / `content_experiment_v2`，第 5.2 先统计“硬编码规则影响了哪些结构化输出字段”，不实现领域配置替换。
- 对 prompt 成本，动态领域词会增加输入 tokens，但可以替代大量散落规则和 prompt 里的重复解释，长期更利于压缩。
- 对评估，第 5.3 后需要区分“通用结构规则命中”和“领域词配置命中”，否则无法判断规则是否真的泛化。

### 11.7 本阶段结论

动态 `domain_profile` 方案可行，而且比手写多行业词表更适合当前项目。但第 5.2 不实现它，只记录硬编码领域词是否进入 context；第 5.3 再设计统一 schema、确认状态、版本号和 context slot 统计口径。

## 12. 结论

- 当前不是多个成熟独立 Agent 类，而是 1 个 AgentRuntime + 1 个已发现 workflow + 多个 tool/service 的形态。
- 第 5.2 P0 业务统计入口为 content_draft_v2、content_draft、review_report。
- 第 5.2 P1 登记上游影响源：competitor_report、competitor_analysis、content_experiment、content_experiment_v2、comment_insight、strategy_memory、context_engineering。
- 第 5.2 P2 只登记 crawler_collection、keyword_seed、confirmation、post_publish、API route、repository、provider_health、llm_infra。
- 第 5.3 再设计 `domain_profile` / `domain_vocabulary`，并考虑从 SYSTEM_RULES、TASK_INSTRUCTION、ACCOUNT_PROFILE、WORKFLOW_STATE、USER_INPUT、OUTPUT_SCHEMA、STRATEGY_MEMORY 等 Context Slot 扩展。
