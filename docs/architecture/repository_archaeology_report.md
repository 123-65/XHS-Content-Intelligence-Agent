Phase 2.2D
STATUS = BLOCKED_BY_DRAFT_PERSISTENCE

Research Persistence  = READY
Strategy Persistence  = READY
Draft Persistence     = BLOCKED
Post-review Persistence = READY
Candidate Persistence = READY

Contract Tools    = 17
Implemented Tools = 12


# Repository Archaeology Report（D.1）

> 调查日期：2026-09-20  
> 调查范围：`xhs-growth-agent/` 全仓库，以及仓库根目录 `agent设计文档/` 中的当前设计书  
> 阶段约束：仅调查；未执行 KEEP/DELETE，未改动源码、测试、Migration、路由、依赖或数据库  
> 判定口径：Runtime Evidence > 文件名/历史文档；先 Root、再 Capability、再 Reachability；引用分为 `PRODUCTION_REFERENCE`、`EVAL_REFERENCE`、`TEST_REFERENCE`、`LEGACY_REFERENCE`、`MIGRATION_REFERENCE`。

## 调查方法与证据边界

- Production Root 来自 `docker-compose.yml` / Dockerfile 的实际命令、`app/main.py:create_app()` 的 `include_router`、`frontend/src/router/index.ts` 的正式 route，以及当前运行中的 Docker Compose 实例。
- 当前产品设计以 `agent设计文档/第 1、3—7、11、12、14 章` 为准。设计冻结为一个 Control Agent、五条独立 Workflow（`RESEARCH_V1`、`CONTENT_STRATEGY_V1`、`CONTENT_CREATION_V1`、`CONTENT_REFINEMENT_V1`、`POST_PUBLISH_REVIEW_V1`）和统一 Workbench；旧 README/阶段报告只作辅助证据。
- 后端静态扫描为 38 个 router 文件、115 个 endpoint decorator；运行中 OpenAPI 为 **119 个 HTTP operation**。多出的 4 个来自 `account_router` 同时按原 prefix 与 `/api` prefix 二次注册。它们均是“运行时已注册”，但不等于均符合目标设计；下文用 `ACTIVE` 与 `LEGACY_ACTIVE` 区分。
- 当前前端正式 route 只有 `/agent/workbench` 和 `/developer/agent-trace`。`AgentWorkbenchLegacy.vue` 无 route，故其引用是 `LEGACY_REFERENCE`，不是生产存活证据。
- 数据库只做只读调查。容器中的 `pg_stat_user_tables.n_live_tup` 用于判断“存在数据”的强信号，是 PostgreSQL 统计估算而非事务级精确计数；没有写数据库。

## Repository Map

| 目录 | 当前实际职责 | 生产代码 | 混合风险 |
|---|---|---:|---|
| `backend/app/api/` | FastAPI 注册面；同时容纳新统一 Agent API、旧 CRUD、V2 端点和阶段性 workflow-specific API | 是 | 高：新旧入口全部同时注册 |
| `backend/app/agent/product_entry/` | 当前正式自然语言入口、LLM Router、Planner、执行器、Action Registry、验证和 trace | 是 | 高：声明能力多于真实 handler，且执行器承担部分 Workflow 职责 |
| `backend/app/agent/`（除 `product_entry`） | 旧 `AgentRuntime`、Tool Registry、fallback、示例 Workflow | 否（仅测试/脚本可达） | 高：与新执行器重复 |
| `backend/app/analysis/competitor/` | 竞品 Evidence、结构化 LLM、规则基线、grounding、assembler | 是 | 高：Production 与 Eval baseline 可由同一 Service 选择 |
| `backend/app/services/` | 多代业务服务、阶段性流程编排、Agent handler 下游 | 是 | 高：多个 Capability 有 V0/V1/V2 owner，部分 Service 直接编排下游 Service |
| `backend/app/crawler/` | 旧 task/provider 采集链（MCP/read-only/manual） | `LEGACY_ACTIVE` | 与 `collectors/xhs/` 重复 |
| `backend/app/collectors/` | 当前 Agent workflow 的真实 XHS MCP + OCR 采集链 | 是 | 与 `crawler/`、`xhs_url_collect_sev.py` 重复 |
| `backend/app/context/` | Context slots、预算、压缩、sanitizer、snapshot/usage | 是 | Resolver 分散在 helper 与业务 handler，未形成设计书中的单一 owner |
| `backend/app/llm/` | Qwen/Zhipu/DeepSeek 真 Provider、Client、成本和错误 | 是 | 三 Provider 是正常扩展，不是重复 owner |
| `backend/app/mcp/` | 旧通用 MCP gateway | 否/旧 runtime 子图 | 设计明确不做通用插件系统 |
| `backend/evals/` | 数据集、runner、fake、历史报告 | 否 | 纯 Eval；禁止生产反向依赖 |
| `backend/tests/` | 测试与 fake | 否 | `competitor_analysis_fakes.py` 明确 `TEST_ONLY` |
| `backend/scripts/` | smoke/report/扫描/demo CLI | DEV/EVAL | 无 startup 注册；不是生产 root |
| `backend/app/models/`, `repositories/`, `alembic/` | 多代持久化模型、仓储和迁移 | 是/历史混合 | 不以代码不可达推断可删表 |
| `frontend/src/views/` | 当前 Workbench、开发 trace、无 route 的 Legacy Workbench | 是/Legacy 混合 | 两代 UI 共存 |
| `frontend/src/api/`, `types/` | 当前与旧 workflow-specific 客户端 | 混合 | 多数只被无 route 的 Legacy View 引用 |

# 1. Production Root Table

## 1.1 启动与前端 Root

| Root ID | 类型 | 文件/位置 | 入口 | 状态 | 证据 |
|---|---|---|---|---|---|
| PR-001 | Backend startup | `docker-compose.yml`, `backend/Dockerfile` | `uvicorn app.main:app --host 0.0.0.0 --port 8000` | ACTIVE | Compose 当前容器已运行；两处命令一致 |
| PR-002 | Backend app factory | `backend/app/main.py:create_app` | `app=create_app()` | ACTIVE | Docker/CLI 均加载该对象；38 个 router 被显式 `include_router` |
| PR-003 | Frontend startup | `docker-compose.yml`, `frontend/src/main.ts` | Vite 5173 / `mount('#app')` | ACTIVE | Compose 当前容器已运行；安装 Pinia、Router、ElementPlus |
| PR-004 | Frontend Route | `frontend/src/router/index.ts` | `/agent/workbench` | ACTIVE | `/` 重定向至此；lazy-load `AgentWorkbench.vue` |
| PR-005 | Frontend Route | `frontend/src/router/index.ts` | `/developer/agent-trace` | DEV_ONLY | route 已注册，读取 developer trace API |
| PR-006 | Frontend file | `frontend/src/views/AgentWorkbenchLegacy.vue` | NONE | DISABLED | 文件存在但 router 未注册；只能形成 Legacy root，不是 Production root |
| PR-007 | startup/lifespan | 全后端 | NONE | DISABLED | 未发现 FastAPI startup/lifespan 注册 |
| PR-008 | worker/scheduler/background | 全后端 | NONE | DISABLED | 未发现 Celery/APScheduler/worker entrypoint；`BackgroundTasks` 亦未注册 |

## 1.2 已注册 Backend API Root（按 router family 分组）

> 计数口径：每个 HTTP method + path 是一个 Backend API root。静态 decorator 合计 115，运行中 OpenAPI 合计 **119**。表中“当前消费者”只表示仓库内消费者；外部消费者未知。

| Root ID | Router / prefix | Endpoint 数 | 状态 | 当前仓库内消费者与证据 |
|---|---|---:|---|---|
| PR-B01 | `health.py`（health） | 2 | ACTIVE | 运维健康检查；已注册 |
| PR-B02 | `account_rout.py`（`/accounts`，并额外注册 `/api/accounts`） | 4×2 实际路径 | ACTIVE | 当前 Workbench 调 `/accounts`；同 router 二次注册产生兼容 alias |
| PR-B03 | `agent_chat.py`（`/agent/chat`） | 3 | ACTIVE | 当前 Workbench 调 `/execute-workflow`；preview/readonly 只被 Legacy View 调用 |
| PR-B04 | `agent_conversation.py`（`/agent/conversations`） | 6 | ACTIVE | 当前 Workbench 创建会话、读取消息；状态 API 当前 UI 未见调用 |
| PR-B05 | `developer_rout.py`（`/api/developer`） | 5 | DEV_ONLY | `/developer/agent-trace` 调 latest run/steps |
| PR-B06 | `provider_health_rout.py` | 3 | DEV_ONLY | 已注册；当前正式 View 未调用 |
| PR-B07 | `agent_run_rout.py`（`/api/agent-runs`） | 4 | LEGACY_ACTIVE | 读取旧 `agent_run/agent_step`；无当前 UI 调用 |
| PR-B08 | `context_rout.py` | 2 | ACTIVE | trace/context 读取面；无当前 UI 调用但符合横向治理能力 |
| PR-B09 | `xhs_url_collect.py`（`/agent/xhs/url-collect`） | 3 | LEGACY_ACTIVE | 仅 Legacy View client；与当前 Agent collector 重复 |
| PR-B10 | `crawler_collection_rout.py`（`/api/crawler/tasks`） | 3 | LEGACY_ACTIVE | 旧 task/provider 采集入口；无当前 View 调用 |
| PR-B11 | `competitor_rout.py`（`/api/competitor`） | 2 | LEGACY_ACTIVE | 旧采集链的数据读取入口 |
| PR-B12 | `competitor_analysis_rout.py`（`/competitor-analysis`） | 3 | LEGACY_ACTIVE | V0 分析 CRUD；无当前 View 调用 |
| PR-B13 | `competitor_report_rout.py`（`/api/competitor/reports`） | 4 | LEGACY_ACTIVE | 当前 Agent handler 间接复用 Service，但前端不应直选该 endpoint |
| PR-B14 | `content_experiment_rout.py`（`/experiments`） | 5 | LEGACY_ACTIVE | V0 实验实现 |
| PR-B15 | `content_experiment_v2_rout.py`（`/api/experiments`） | 4 | LEGACY_ACTIVE | V2 实验卡实现；与 V0/operation experiment 重复 |
| PR-B16 | `content_draft_v2_rout.py`（`/api/drafts`） | 4 | LEGACY_ACTIVE | 旧/V2 草稿入口；当前 Workbench 不直调 |
| PR-B17 | `confirmation_rout.py`（`/api/confirmations`） | 4 | LEGACY_ACTIVE | 旧 runtime confirmation；目标设计仍需 Confirmation，但 owner 未冻结 |
| PR-B18 | `llm.py` | 3 | DEV_ONLY | LLM 直测/健康入口；不应作为用户业务 root |
| PR-B19 | `keyword_seed_rout.py` | 2 | LEGACY_ACTIVE | 历史启动策略/关键词能力，目标设计无独立 Capability |
| PR-B20 | `published_note_rout.py` | 3 | LEGACY_ACTIVE | 发布后链的数据入口，当前 UI 仅 Legacy View 间接使用 |
| PR-B21 | `private_conversion_rout.py` | 1 | LEGACY_ACTIVE | 私域指标读取；符合复盘数据但为 workflow-specific API |
| PR-B22 | `post_publish_review_rout.py` | 4 | LEGACY_ACTIVE | 早期复盘实现 |
| PR-B23 | `optimization_rout.py` | 2 | LEGACY_ACTIVE | 历史优化计划，目标五 Workflow 无独立 owner |
| PR-B24 | `data_source_config.py` | 5 | LEGACY_ACTIVE | 仅 Legacy View client |
| PR-B25 | `data_refresh_run.py` | 3 | LEGACY_ACTIVE | 仅 Legacy View client；Service→旧 crawler |
| PR-B26 | `evidence_refresh_run.py` | 3 | LEGACY_ACTIVE | 仅 Legacy View client |
| PR-B27 | `operation_run.py` | 3 | LEGACY_ACTIVE | 仅 Legacy View client；阶段性超级流程入口 |
| PR-B28 | `operation_experiment.py` | 2 | LEGACY_ACTIVE | 仅 Legacy View client；实验能力第三实现 |
| PR-B29 | `draft_context_preview.py` | 1 | LEGACY_ACTIVE | 仅 Legacy View client；Agent 内部已有同源 context preview handler |
| PR-B30 | `draft_generation.py` | 1 | LEGACY_ACTIVE | 仅 Legacy View client；正式 Workbench 尚未从统一 Agent 接通此 handler |
| PR-B31 | `draft_review.py` | 1 | LEGACY_ACTIVE | 仅 Legacy View client |
| PR-B32 | `draft_revision_plan.py` | 3 | LEGACY_ACTIVE | 仅 Legacy View client |
| PR-B33 | `draft_revision_apply.py` | 1 | LEGACY_ACTIVE | 仅 Legacy View client |
| PR-B34 | `publish_package.py` | 3 | LEGACY_ACTIVE | 仅 Legacy View client；人工发布包符合设计但入口形态旧 |
| PR-B35 | `manual_publish_backfill.py` | 3 | LEGACY_ACTIVE | 仅 Legacy View client；人工发布回填符合 V1 非自动发布边界 |
| PR-B36 | `post_publish_review_v0.py` | 3 | LEGACY_ACTIVE | 与早期复盘 router 并存；仅 Legacy View client |
| PR-B37 | `strategy_memory_confirmation.py` | 3 | LEGACY_ACTIVE | 仅 Legacy View client；目标设计需要人工确认记忆 |

### Root 数量结论

- 119 个注册 Backend HTTP root（115 个 decorator + `account_router` 二次注册产生的 4 个 alias operation）。
- 2 个注册 Frontend route root。
- 2 个进程启动 root（backend、frontend）。
- 合计 **123 个运行时 Production Root**（其中大量为 `LEGACY_ACTIVE`/`DEV_ONLY`）；PostgreSQL 是基础设施依赖，不计业务 Production Root。

# 2. Capability Inventory

| Capability ID | 业务职责（Input → Output / Side Effect / Consumer） | 当前实现候选 | Production 可达 | 实现数 | 目标设计存在 |
|---|---|---|---:|---:|---:|
| CAP-AGENT-RUNTIME | 用户 Turn → 编排执行与统一响应 | `product_entry/chat_service.py + executor.py`；旧 `agent/runtime.py` | 新：是；旧：否 | 2 | 是 |
| CAP-ROUTER | 用户输入 → Intent/Semantic Frame | `product_entry/llm_router.py` | 是 | 1 | 是 |
| CAP-CONTEXT-RESOLVER | 账号/会话/Artifact 引用 → 预算内上下文 | `context/*` + `business_handlers.py` + `draft_context_preview.py` | 是 | 3 个分散 owner | 是 |
| CAP-PLANNER | Semantic Frame → Plan | `product_entry/task_planner.py` | 是 | 1 | 是 |
| CAP-WORKFLOW | Plan → 五类可恢复业务流程 | 当前 `AgentChatWorkflowExecuteService` 只实现竞品采集+分析；阶段性 operation services；旧示例 `ContentExperimentWorkflow` | 部分 | 3 形态 | 是（五条） |
| CAP-TOOL-REGISTRY | Action → handler/effect/permission | `product_entry/registry.py + ActionHandlerRegistry`；旧 `agent/tools/*` | 新：是；旧：否 | 2 | 是 |
| CAP-XHS-COLLECTION | 用户授权 URL/账号 → 真实 Evidence + DB | `XhsCollectorService/XiaohongshuMcpProvider`；`XhsUrlCollectService/SimpleHttp`；`CrawlerCollectionService/providers` | 三者均由注册 API 可达；当前 Workbench 到第一套 | 3 | 是 |
| CAP-RESEARCH | Evidence → Research Artifact | `CompetitorReportService`/competitor analysis package；V0 `CompetitorAnalysisService` | 是 | 2+ | 是 |
| CAP-STRATEGY | Research/Growth Context → Strategy/Opportunity | `content_experiment_v2_sev.py`、`content_experiment_sev.py`、`operation_experiment_sev.py`、opportunity assembler | 是（旧 roots） | 3+ | 是 |
| CAP-DRAFT | Strategy/Experiment → Draft + Version | `draft_generation_sev.py`；`content_draft_v2_sev.py` | 是（旧 roots） | 2 | 是 |
| CAP-REVIEW | Draft → Review Report | `draft_review_sev.py`；V2 draft service 内相关生成逻辑 | 是（旧 roots） | 2 | 是 |
| CAP-REVISION | Draft + scope/feedback → 新 Version | `draft_revision_plan_sev.py` + `draft_revision_apply_sev.py`；V2 regenerate | 是（旧 roots） | 2 形态 | 是 |
| CAP-GROUNDING | 结论/引用 → Grounding 状态 | `analysis/competitor/grounding.py`；各 Service 的局部校验 | 是 | 分散 | 是 |
| CAP-MEMORY | Review/用户确认 → Strategy Candidate/Memory | `strategy_memory_confirmation_sev.py`；product entry 仅声明 `CREATE_CANDIDATE_MEMORY` 未注册 workflow handler | 部分 | 2 形态 | 是 |
| CAP-CONVERSATION | 会话/消息/当前状态持久化 | `agent_conversation_sev.py/repo/models` | 是 | 1 | 是 |
| CAP-TRACE | Run/Step/Prompt/MCP/Context trace | `product_entry/trace.py`、旧 `agent/observability.py`、developer/context services | 是/旧混合 | 2+ | 是 |
| CAP-LLM-PROVIDER | 结构化/文本生成 → 真 Provider 结果 | `llm/router.py` + qwen/zhipu/deepseek providers | 是 | 1 owner，3 adapter | 是 |
| CAP-XHS-PROVIDER | 公开 XHS 读取 → 标准采集结果 | MCP collector；crawler provider factory；simple HTTP | 是 | 3 owner 形态 | 是 |
| CAP-PUBLISH-PACKAGE | Draft → 人工发布材料 | `publish_package_sev.py` | 是（旧 root） | 1 | 是（人工发布辅助） |
| CAP-POST-PUBLISH | Published Note + metrics → Review/Candidate | `post_publish_review_v0_sev.py`；`post_publish_sev.py` + `post_publish_review_rout.py` | 是 | 2 | 是 |
| CAP-CONFIRMATION | 风险动作/记忆 → 人工决策 | product-entry confirmation card；DB confirmation service；strategy-memory confirmation | 是 | 3 层 | 是 |
| CAP-EVAL | dataset/runner → 评分报告 | `backend/evals/*`, `eval_sev.py` | Eval root / 注册业务 API 未见 | 1 | 是（横向） |
| CAP-HIST-VIRAL | 竞品笔记 → 爆款拆解/预测式产物 | `viral_note_breakdown`, old competitor report assembler | 旧链可达 | 1+ | 否（爆款概率预测 OUT_OF_SCOPE） |
| CAP-HIST-EXPERIMENT-PLATFORM | 多变量/指标目标/审批 → 实验卡 | V2 experiment + operation experiment | 旧链可达 | 2 | 否（严格 A/B 平台 OUT_OF_SCOPE） |
| CAP-HIST-STARTUP-STRATEGY | 关键词种子/启动策略 → 配置 | `startup_strategy_sev.py`, `keyword_seed_*` | keyword 部分可达；startup service 无 API | 2 | 否（应折入 Strategy/Context） |
| CAP-HIST-GENERIC-MCP | 动态 binding/tool gateway | `mcp/gateway.py`, `mcp_*` models, old tool registry | 旧 runtime 不可达；health/config 痕迹 | 1 | 否（通用插件系统 OUT_OF_SCOPE） |

**核心 Capability 计数：**按目标设计和横向运行能力合并后为 **22 个**（表中前 22 行）；另识别 4 个历史 Capability。

# 3. File / Symbol Classification

## 3.1 重要文件与模块

| 文件/模块 | 分类 | Reference 类型 | 证据与 Candidate Decision |
|---|---|---|---|
| `backend/app/main.py` | PRODUCTION | PRODUCTION_REFERENCE | 唯一 FastAPI app factory；`KEEP_CANDIDATE`，但 router 注册清单需在 D.2 重新分层 |
| `frontend/src/router/index.ts`, `AgentWorkbench.vue` | PRODUCTION | PRODUCTION_REFERENCE | 当前 `/` 实际进入；`KEEP_CANDIDATE` |
| `frontend/src/views/DeveloperAgentTrace.vue` | PRODUCTION（DEV_ONLY root） | PRODUCTION_REFERENCE | 正式 router 注册的开发页面；`MOVE_CANDIDATE` 到明确 dev surface |
| `frontend/src/views/AgentWorkbenchLegacy.vue` | LEGACY_COMPAT | LEGACY_REFERENCE | 无 route，但保存整套旧 UI；`QUARANTINE_CANDIDATE` |
| `frontend/src/api/{agentChat,account,developerTrace}.ts` | PRODUCTION/MIXED | PRODUCTION_REFERENCE | agentChat 内 preview/readonly 仅 Legacy View；文件需 symbol-level `SPLIT_CANDIDATE` |
| 其余 `frontend/src/api/*.ts` | LEGACY_COMPAT | LEGACY_REFERENCE | 仅 `AgentWorkbenchLegacy.vue` 引用；`QUARANTINE_CANDIDATE`，不能据此删后端 |
| `backend/app/api/agent_chat.py` | MIXED | PRODUCTION_REFERENCE + LEGACY_REFERENCE | `/execute-workflow` 当前生产；preview/readonly 仅旧 UI/测试；`SPLIT_CANDIDATE` |
| `backend/app/agent/product_entry/*` | PRODUCTION（个别 MIXED） | PRODUCTION_REFERENCE | 当前 Control Agent 候选；Registry 声明了未接通能力；整体 `KEEP_CANDIDATE`，执行/Workflow 边界需拆 |
| `backend/app/agent/runtime.py` | FAILED_EXPERIMENT | TEST_REFERENCE | 仅旧 workflow、测试、扫描脚本引用，无注册 API；已被 `product_entry/executor.py` 替代；`QUARANTINE_CANDIDATE` |
| `backend/app/agent/workflows/content_experiment.py` | FAILED_EXPERIMENT | TEST_REFERENCE | 示例型单 workflow，仅测试可达，且不符合冻结的五 Workflow；`DELETE_CANDIDATE`（仅候选） |
| `backend/app/agent/tools/*`, `policies/*`, `mcp/gateway.py` | FAILED_EXPERIMENT / MIXED | TEST_REFERENCE + LEGACY_REFERENCE | 属于旧 runtime 子图；部分治理思想可能可复用；`QUARANTINE_CANDIDATE` |
| `backend/app/analysis/competitor/engine.py`, `llm_analyzer.py`, `grounding.py`, `evidence.py` | PRODUCTION | PRODUCTION_REFERENCE | 当前 Research 分析链；`KEEP_CANDIDATE` |
| `backend/app/analysis/competitor/rule_baseline.py` | EVAL_BASELINE | EVAL_REFERENCE + 非法 PRODUCTION_REFERENCE | 明确 Rule baseline，却可被生产 Service 选择；`MOVE_CANDIDATE` |
| `backend/app/services/competitor_report_sev.py` | MIXED | PRODUCTION_REFERENCE + EVAL_REFERENCE | 真 LLM 与 Rule baseline 同一 resolver；`SPLIT_CANDIDATE` |
| `backend/app/services/xhs_collector_sev.py`, `collectors/xhs/*` | PRODUCTION | PRODUCTION_REFERENCE | 当前统一 Workbench 的真实 MCP 路径；`KEEP_CANDIDATE` |
| `backend/app/services/xhs_url_collect_sev.py` | LEGACY_COMPAT | LEGACY_REFERENCE | 由注册旧 API 可达，使用 Simple HTTP；`REPLACE_CANDIDATE` |
| `backend/app/services/crawler_collection_sev.py`, `crawler/providers/*` | LEGACY_COMPAT | LEGACY_REFERENCE | 由 task API/data refresh 可达，与新 collector 重复；`REPLACE_CANDIDATE` |
| `backend/app/context/*` | PRODUCTION/MIXED | PRODUCTION_REFERENCE | 当前 handler、draft 和 trace 使用；`MERGE_CANDIDATE` 为单一 Context Resolver owner |
| `backend/evals/*` | EVAL_BASELINE | EVAL_REFERENCE | 独立 runner/dataset/fake；`KEEP_CANDIDATE`，需禁止生产 import |
| `backend/tests/*` | TEST_ONLY | TEST_REFERENCE | 测试证据；不作为生产 owner |
| `backend/tests/competitor_analysis_fakes.py` | TEST_ONLY | TEST_REFERENCE | 明确 fake；生产未引用 |
| `backend/scripts/create_demo_agent_trace.py` | TEST_ONLY/DEV_ONLY | TEST_REFERENCE | demo 数据脚本，无 startup；`MOVE_CANDIDATE` |
| `backend/alembic/*` | PRODUCTION（Migration） | MIGRATION_REFERENCE | 迁移历史；本阶段不提出删除 |

## 3.2 MIXED 文件的 Symbol Level 分类

| 文件 / Symbol | Capability | 分类 | 当前调用来源 | Candidate Decision |
|---|---|---|---|---|
| `agent_chat.py:execute_workflow` | Agent Runtime | PRODUCTION | 当前 `AgentWorkbench.vue` | KEEP_CANDIDATE |
| `agent_chat.py:preview`, `execute_readonly` | Agent preview | LEGACY_COMPAT | Legacy View + tests | QUARANTINE_CANDIDATE |
| `chat_service.py:AgentChatWorkflowExecuteService` | Agent Runtime/Workflow | MIXED | 当前 execute-workflow | SPLIT_CANDIDATE：Control Agent 与 RESEARCH workflow 分离 |
| `chat_service.py:AgentChatPreviewService`, `AgentChatReadonlyExecuteService` | Preview/read-only | LEGACY_COMPAT | 旧 endpoints/tests | QUARANTINE_CANDIDATE |
| `business_handlers.py:collect_xhs_notes_handler`, `collect_xhs_accounts_handler` | XHS Collection | PRODUCTION | 当前 competitor workflow registry | KEEP_CANDIDATE |
| `business_handlers.py:analyze_competitor_data_handler` | Research | PRODUCTION/MIXED | 当前 competitor workflow registry | SPLIT_CANDIDATE：handler 手工拼 report metadata，承担 Workflow/Assembler 职责 |
| `business_handlers.py:query_*` | Context/Artifact query | PRODUCTION | readonly registry；draft preview 等链使用 | MERGE_CANDIDATE 到统一 Context Resolver/Tool owner |
| `registry.py:ACTION_REGISTRY` 中 collection/analyze actions | Tool Registry | PRODUCTION | 当前 Router/Planner/Workflow | KEEP_CANDIDATE |
| `registry.py` 中 `GENERATE_*`, `REVIEW_DRAFT`, `REFINE_DRAFT`, `CREATE_CANDIDATE_MEMORY`, `QUERY_ANALYTICS` | 声明但未完整执行 | UNKNOWN | Planner 可规划，但 workflow registry 未注册对应 handler | `UNKNOWN_REASON`: 声明与执行面不一致；`NEXT_CHECK`: D.2 前逐 Action 做端到端契约测试 |
| `competitor_report_sev.py:_resolve_analyzer` LLM branch | Research | PRODUCTION | Agent handler/报告 API | KEEP_CANDIDATE |
| `competitor_report_sev.py:_resolve_analyzer` Rule branch | Eval baseline | EVAL_BASELINE（边界违规） | 生产 API 可通过 request 选择 | MOVE_CANDIDATE |
| `rule_baseline.py:RuleBaselineCompetitorAnalyzer` | Rule baseline | EVAL_BASELINE | Eval + 生产 resolver | MOVE_CANDIDATE 至 eval-only |
| `agent/runtime.py:AgentRuntime` | 旧 Runtime | FAILED_EXPERIMENT | tests/旧 workflow | QUARANTINE_CANDIDATE |
| `agent/tools/fallback_registry.py:*` | 旧 fallback | FAILED_EXPERIMENT | 仅旧 Runtime | QUARANTINE_CANDIDATE；其 fallback 返回 `ok=True` 但标注无 mock，需防止未来重接 |

## 3.3 UNKNOWN 清单

| 对象 | UNKNOWN_REASON | NEXT_CHECK |
|---|---|---|
| 当前 115 endpoints 的外部消费者 | 仓库内只能证明前端消费者，无法证明是否有脚本/用户直接调用 | 查 API access log、反向代理日志、客户端版本/调用方登记 |
| `ACTION_REGISTRY` 中未有 workflow handler 的 8+ actions | Router/Planner 可生成，但 execute-workflow registry 只注册 collection/account-analysis 子集 | 为每个 Action 构造端到端请求，核对 blocked/failed 是否被 UI 正确呈现 |
| `manual_snapshot` / `readonly_xhs` provider 的真实运维用途 | 注册在旧 provider chain，但当前 Workbench 用另一套 MCP provider | 查生产环境配置和 provider health/access log |
| `mcp_server_config`, `mcp_tool_binding`, `prompt_template`, `trace_retention_policy` | 当前统计为空且代码路径有限，但可能是预留/部署差异 | 查各环境数据库与部署配置；不可据本地空表下结论 |
| `startup_strategy` | 表为空，Service/Repo 存在，未发现 API；但可能有历史离线导入 | 查历史部署日志/业务数据归档 |
| 数据库各表精确真实行数 | 本报告使用 `n_live_tup` 估算，仅证明存在性强信号 | 如 D.2 需要迁移，另行在一致性快照执行精确只读 count 与 FK/lineage 审计 |

## 3.4 Database Model/Table 特别报告

> 不给出删表结论。下面按用途簇汇总；“有数据”来自运行中 Postgres 的只读统计。

| 表簇 | Production Code Reachable | 是否存在真实数据 | 当前用途 |
|---|---:|---:|---|
| `account_profile` | 是 | 是（约 6332） | 当前 Workbench 账号上下文 |
| `agent_conversation*` | 是 | 是（约 334/192） | 当前会话与消息 |
| `agent_run`, `agent_step` | 新 trace/API 与旧 runtime 混合可达 | 是（约 742/1888） | 运行轨迹；需区分代际 lineage |
| `competitor_account/note/comment`, `xhs_note_snapshot` | 是 | 是（约 2449/9592/9815/745） | 当前 Research Evidence 与旧采集共享 |
| `competitor_analysis_report`, `content_opportunity`, `viral_note_breakdown` | 是 | 是（约 2564/3476/3319） | Research 结果；后者含历史 Viral 语义 |
| `content_experiment`, `experiment_variable`, `experiment_metric_target` | 是（多代 API） | 是（约 3969/336/336） | Strategy/历史实验卡 |
| `content_draft`, `content_draft_version`, `draft_generation_context`, `draft_revision_plan`, `review_report` | 是 | 是 | Draft/Review/Revision 与上下文 lineage |
| `publish_package`, `published_note`, `public_metric_snapshot`, `private_conversion_snapshot` | 是（旧 roots） | 是 | 人工发布与发布后复盘 |
| `strategy_memory`, `strategy_memory_usage`, `memory_evidence` | 是 | 是 | 候选/已确认策略记忆与证据 |
| `context_snapshot`, `context_slot_log`, `prompt_run_log`, `mcp_tool_call_log` | 是 | 是 | Trace/Context/Provider 可观测性 |
| `account_*_run/config` | 旧 registered APIs 可达 | 是 | Legacy Workbench 阶段性流水线状态 |
| `confirmation_*` | 是（旧 confirmation API） | 是 | 通用确认记录 |
| `eval_run`, `eval_case` | Eval/服务可达 | run 有（约 18），case 统计为空 | Eval 结果/用例 |
| `startup_strategy` | 未发现 Production root | 统计为空 | 历史启动策略 |
| `mcp_server_config`, `mcp_tool_binding` | 旧 MCP 代码可读，旧 Runtime 不可达 | 统计为空 | 通用 MCP 动态配置预留 |
| `prompt_template`, `trace_retention_policy`, `note_comment_snapshot` | 局部模型/读取逻辑 | 统计为空 | 模板/保留策略/历史快照预留 |
| 所有 Alembic migration | MIGRATION_REFERENCE | 不适用 | 数据库历史与可升级性；不得删除 |

# 4. Canonical Owner Candidate Table

> 仅提出候选，不冻结 Owner。

| Capability | 候选实现 | Production Reachable | Design Fit | 真实 Provider | Tests | Mock/Fallback | 职责混合程度 | Candidate Decision |
|---|---|---:|---|---:|---:|---|---|---|
| Agent Runtime | `product_entry/chat_service + executor` | 是，当前 UI | 中高：统一入口，但 workflow 不完整 | 是 | 多 | 无 mock success；异常转 FAILED | 高 | **Canonical Owner Candidate A**；SPLIT_CANDIDATE |
| Agent Runtime | `agent/runtime.py` | 否，仅测试 | 低：旧 tool runtime + 示例 workflow | 可接 provider | 有 | fallback tool 可返回成功 | 高 | QUARANTINE_CANDIDATE |
| XHS Collection | `XhsCollectorService + XiaohongshuMcpProvider` | 是，当前 UI | 高：用户授权 URL/账号、真实 MCP | 是 | 有含 real integration | 失败显式返回 | 中 | **Candidate A** |
| XHS Collection | `XhsUrlCollectService + SimpleHttpXhsProvider` | 注册旧 API | 中 | HTTP 真读取 | 有 | 未见 mock success | 中 | Candidate B / REPLACE_CANDIDATE |
| XHS Collection | `CrawlerCollectionService + providers.factory` | 注册旧 API | 低中：多 provider task 链 | MCP/read-only/manual | 有 | provider chain 容易形成隐式替代 | 高 | Candidate C / REPLACE_CANDIDATE |
| Research Analysis | `CompetitorAnalysisEngine + Structured LLM + Grounding` | 是 | 高 | 是 | 有 | 无 fake success | 中 | **Candidate A** |
| Research Analysis | `RuleBaselineCompetitorAnalyzer` | 可由生产 resolver 到达 | 低（只应 eval） | 否 | 有/AB eval | 规则 baseline | 低 | MOVE_CANDIDATE 到 Eval |
| Research Analysis | `CompetitorAnalysisService` V0 | 注册旧 API | 低 | 无/规则式组装 | 有 | 规则猜测 | 高 | Candidate C / DEPRECATE_CANDIDATE |
| Strategy/Experiment | `ContentExperimentV2Service` | 注册 API | 中：结构化卡片但偏 A/B 平台 | LLM | 有 | 有 fallback 字段 | 高 | Candidate A/B，需人工决定是否收缩为 Strategy Artifact |
| Strategy/Experiment | `ContentExperimentService` V0 | 注册 API | 低：规则猜 topic/angle | 否 | 有 | 默认文案形成“成功式”产物 | 中 | DEPRECATE_CANDIDATE |
| Strategy/Experiment | `OperationExperimentService` | 注册旧 API | 低：绑定 operation run | 可能 | 有 | 阶段性流程 | 高 | MERGE_CANDIDATE |
| Draft | `draft_generation_sev.py` | 注册旧 API | 高：符合 creation workflow | 是 | 有 | 显式错误 | 中 | **Candidate A** |
| Draft | `content_draft_v2_sev.py` | 注册 API | 中 | 是 | 有 | schema 含 fallback 标志 | 高 | Candidate B / MERGE_CANDIDATE |
| Post-publish | `post_publish_review_v0_sev.py` | 注册 API | 中高，贴近当前闭环 | 依实现 | 有 | 未见 mock success | 中 | Candidate A |
| Post-publish | `post_publish_sev.py + post_publish_review_rout.py` | 注册 API | 中 | 局部 | 有 | 旧路径 | 高 | Candidate B / MERGE_CANDIDATE |
| Context Resolver | `context/*` | 是 | 高：slots/budget/compression/sanitizer | 不适用 | 多 | 阻断 mock/seed_sample | 中 | **Candidate A（核心算法）** |
| Context Resolver | `business_handlers.py:query_*` + draft preview | 是 | 中：业务查询正确但 owner 分散 | 不适用 | 多 | 数据不足显式 | 高 | MERGE_CANDIDATE 到 Candidate A |
| Trace | `product_entry/trace.py` | 是，当前 Agent | 高 | 不适用 | 有 | 敏感信息 mask | 中 | Candidate A |
| Trace | `agent/observability.py` + `agent_run` API | 旧 runtime/读 API | 中低 | 不适用 | 有 | 兼容两种 fallback 标记 | 高 | Candidate B / MERGE_CANDIDATE |

### 需要人工冻结的 Owner

1. Agent Runtime：`product_entry` 执行器是否直接演进为 Control Agent，还是先抽出独立五 Workflow contract。
2. XHS Collection：MCP collector、Simple HTTP、旧 crawler provider chain 哪个保留为唯一生产 owner；其他是否仅作 adapter/迁移兼容。
3. Strategy：V2 实验卡是否收缩成 Strategy/Opportunity Artifact，还是另建符合设计书的 owner。
4. Draft/Review/Post-publish：阶段性 B8—B15 services 中哪些成为五 Workflow 的 canonical tools。
5. Trace：新 product-entry trace 与旧 agent_run/step 数据模型如何合并且保留历史 lineage。

# 5. Legacy Subgraph Report

## LS-01：无 route 的旧前端超级工作台

```text
AgentWorkbenchLegacy.vue (Legacy Root, no frontend route)
  -> agentChat preview/readonly/workflow
  -> dataSourceConfig -> dataRefreshRun -> evidenceRefreshRun
  -> operationRun -> operationExperiment
  -> draftContextPreview -> draftGeneration -> draftReview
  -> draftRevisionPlan -> draftRevisionApply
  -> publishPackage -> manualPublishBackfill
  -> postPublishReview -> strategyMemoryConfirmation
```

- Root 状态：前端 `DISABLED`，但所有对应后端 router 仍 `LEGACY_ACTIVE`。
- 不能存活的理由：链内 API/client/service 互相引用均属于 `LEGACY_REFERENCE`。
- Shared Canonical Candidate：账号、Conversation、Context slots、Draft/Review/Revision、人工发布包、复盘、策略记忆的数据模型和部分 Service 仍与目标五 Workflow 一致，不能随 UI 子图整体处置。
- Candidate：UI 与专用 client `QUARANTINE_CANDIDATE`；共享业务能力 `MERGE_CANDIDATE` 到五 Workflow。

## LS-02：旧 AgentRuntime / Tool Registry 子图

```text
tests/test_agent_runtime.py (TEST root)
  -> ContentExperimentWorkflow
  -> AgentRuntime
  -> ToolRegistry
     -> LocalToolRegistry -> services/repositories/models
     -> MCPToolRegistry -> MCPGateway -> mcp bindings/logs
     -> FallbackToolRegistry
  -> GuardrailPolicy / StopPolicy / FallbackPolicy
  -> AgentRunRepository -> agent_run / agent_step
```

- 无 Backend API、Frontend route、startup 或 registry 从当前 Production root 进入 `AgentRuntime.run()`。
- `scripts/context_entrypoint_scan.py` 对其文本扫描是 `EVAL/DEV_REFERENCE`，不是运行引用。
- Shared Canonical Candidate：Guardrail/Stop/trace 数据合同、`agent_run/agent_step` 历史数据可能值得合并；旧 Runtime 与示例 Workflow 本身为 `FAILED_EXPERIMENT` 候选。
- 主要风险：fallback registry 将信息性降级包装为 `ToolResult(ok=True)`；若未来误接生产，会造成 fake/empty success 语义。

## LS-03：三代竞品研究与实验链

```text
/competitor-analysis (V0)
  -> CompetitorAnalysisService -> competitor_analysis_report
  -> /experiments (V0) -> ContentExperimentService (rule guesses)

/api/crawler/tasks + /api/competitor/reports (V2)
  -> CrawlerCollectionService/providers
  -> CompetitorReportService
     -> Structured LLM OR RuleBaseline
     -> Grounding/Assembler
  -> /api/experiments -> ContentExperimentV2Service
  -> /api/drafts -> ContentDraftV2Service

/agent/chat/execute-workflow (current)
  -> product_entry workflow service
  -> XhsCollectorService/MCP
  -> analyze_competitor_data_handler
  -> CompetitorReportService (shared)
```

- 前两条是 `LEGACY_ACTIVE`，第三条是当前产品链。
- Shared Canonical Candidate：`CompetitorReportService` 的 Structured LLM、Evidence、Grounding、Assembler；但 Rule baseline 必须从共享 Service 分离。
- 该子图证明“有引用”不等于有三个 Production Owner 的合理性；当前确有三个已注册入口 owner。

## LS-04：阶段性 Operation 超级流程链

```text
/agent/data-source-configs
 -> /agent/data-refresh/runs -> CrawlerCollectionService
 -> /agent/evidence-refresh/runs
 -> /agent/operation-runs
 -> /agent/operation-runs/{id}/experiments
 -> draft/review/revision/publish/backfill/post-review/memory endpoints
```

- 由旧 Workbench 曾直接逐步驱动，当前 route 已移除，但后端仍全部注册。
- 与设计书“五条独立 Workflow，由 Planner 组合；不要一个从研究跑到复盘的超级 Workflow”冲突。
- Shared Canonical Candidate：各阶段的原子 Service、Repository、Model、数据 lineage；Operation orchestration 本身为 `DEPRECATE_CANDIDATE`。

## LS-05：旧通用 MCP / 动态 Tool 子图

```text
AgentRuntime -> ToolRegistry -> MCPToolRegistry -> MCPGateway
 -> mcp_server_config / mcp_tool_binding / mcp_tool_call_log
```

- 当前仅旧 Runtime/test 可达；配置/绑定表统计为空，call log 有历史数据。
- 目标设计明确 `Tool Marketplace`、动态安装和通用插件系统 OUT_OF_SCOPE。
- Shared Canonical Candidate：MCP call log、Provider adapter 的错误/trace 契约；动态通用 registry 不是当前设计 owner。

**主要 Legacy Subgraph：5 条。**

# 6. Boundary Violation & Cleanup Candidate Report

## P0

| ID | 违规 | 证据 | 风险 | Candidate Decision |
|---|---|---|---|---|
| P0-01 | Production → Eval Baseline | `CompetitorReportService._resolve_analyzer()` 直接 import/返回 `RuleBaselineCompetitorAnalyzer`，且报告 API request 可选 engine | 规则 baseline 成为生产成功路径，污染质量与语义 | `SPLIT_CANDIDATE` + `MOVE_CANDIDATE` |
| P0-02 | 多 Production Owner：XHS Collection | 三套已注册入口/Service/provider；当前 Agent 用 MCP collector，旧 API 用 Simple HTTP/crawler chain | 数据语义、错误码、去重和 lineage 分裂 | `REPLACE_CANDIDATE`，人工冻结 owner |
| P0-03 | 多 Production Owner：Research | V0 competitor analysis、V2 report、当前 Agent handler 同时运行 | 同一 Evidence 可生成不同 schema/质量结论 | `MERGE_CANDIDATE` |
| P0-04 | 多 Production Owner：Strategy/Experiment | V0 experiments、V2 experiments、operation experiments 均已注册 | 目标 Strategy 被历史 A/B 实验语义绑架 | `MERGE_CANDIDATE` / `DEPRECATE_CANDIDATE` |
| P0-05 | 多 Production Owner：Draft/Post-review | V2 draft 与 B8 draft；两套 post-publish review | 版本 lineage 和后续 memory 来源不唯一 | `MERGE_CANDIDATE` |
| P0-06 | 统一 Agent 声明能力大于实际执行能力 | `ACTION_REGISTRY` 声明 draft/review/refine/memory/analytics，execute-workflow registry 只注册账号、采集、竞品分析 | Planner 可能产出合法 Plan，执行时 handler missing；统一入口表面成功能力不完整 | `REPLACE_CANDIDATE`（补齐五 Workflow 前须显式 BLOCKED，而非假成功） |
| P0-07 | Production → Legacy | 当前 Agent Research handler 直接复用多代混合的 `CompetitorReportService`；部分阶段 service 调旧 crawler | 新入口继承旧边界与 baseline 分支 | `SPLIT_CANDIDATE` |
| P0-08 | Production Mock/Fake Success（潜在重接风险） | 旧 fallback tools 返回 `ok=True`、`mock_used=False` 的说明性结果；当前旧 Runtime 不可达 | 目前不是现行生产事故，但若注册即形成成功假象 | `QUARANTINE_CANDIDATE` |

### Mock/Fake 核查结论

- 当前正式 `product_entry` + `XhsCollectorService` + LLM providers 未发现用 mock 数据伪造业务成功；provider 缺配置/失败会显式失败。
- `evals/fakes.py` 与测试 fake 未被生产 import。
- 真正 P0 是 Rule baseline 可作为 production analyzer，以及旧 Runtime fallback 的“成功式降级”若被重新接线的高风险。

## P1

| ID | 问题 | 证据 | Candidate Decision |
|---|---|---|---|
| P1-01 | 重复 Agent Runtime | 新 `ExecutionOrchestrator` vs 旧 `AgentRuntime` | 旧链 `QUARANTINE_CANDIDATE` |
| P1-02 | 5 条 Legacy Subgraph 仍大量注册 | 119 个运行时 operations 中仅小部分由当前 UI 使用 | router families `DEPRECATE_CANDIDATE`，共享服务另审 |
| P1-03 | Failed Experiment 代码仍在主 app 包 | 旧 Runtime、示例 Workflow、通用 MCP registry | `QUARANTINE_CANDIDATE` |
| P1-04 | OUT_OF_SCOPE 的严格实验平台语义仍在生产路径 | experiment variables/metric targets/approve APIs；设计明确严格 A/B 平台不做 | `DEPRECATE_CANDIDATE` 或收缩为 Strategy Artifact |
| P1-05 | 前端直接选择 workflow-specific endpoint（遗留） | Legacy View 串联十余专用 API client | UI `QUARANTINE_CANDIDATE`；后端逐能力合并 |
| P1-06 | Workflow → Router / Service→Service 控制权逆流 | operation/data refresh service 直接决定下一阶段并调用 crawler；product-entry chat service 内嵌 competitor workflow | `SPLIT_CANDIDATE` |
| P1-07 | Tool/handler 承担 Workflow/Assembler 职责 | `analyze_competitor_data_handler` 创建 report、查 comments、拼 evidence/metadata | `SPLIT_CANDIDATE` |
| P1-08 | 旧 Viral capability 与目标 Research 混合 | `viral_note_breakdown` 有大量数据并由旧 report 输出使用 | `MERGE_CANDIDATE`（保留证据价值，不保留爆款预测 owner） |

## P2

| ID | 混合职责 | 证据 | Candidate Decision |
|---|---|---|---|
| P2-01 | `business_handlers.py` 混合 Context Query、Collection、Research Assembly | 多个 Capability 的 handler 同文件 | `SPLIT_CANDIDATE` |
| P2-02 | `chat_service.py` 混合 preview、readonly、production workflow | 三种执行模式和会话持久化同文件 | `SPLIT_CANDIDATE` |
| P2-03 | `CompetitorReportService` 混合生产 analyzer 选择与 eval baseline | 单 resolver 两种身份 | `SPLIT_CANDIDATE` |
| P2-04 | `AgentWorkbenchLegacy.vue` 是超大单页控制器 | UI、流程控制、十余 API 集成同文件 | `QUARANTINE_CANDIDATE` |
| P2-05 | Context Resolver owner 分散 | context helpers、draft preview、business handlers 各自解析/压缩 | `MERGE_CANDIDATE` |

## Candidate Decision 汇总（非最终决策）

| Candidate | 对象 |
|---|---|
| KEEP_CANDIDATE | 当前 startup/app factory、当前 Workbench、新 Router/Planner/validator、真实 LLM providers、MCP collector、Evidence/Grounding 核心、Conversation/数据库 lineage |
| MOVE_CANDIDATE | Rule baseline → eval-only；developer/demo surface → dev-only |
| MERGE_CANDIDATE | Context Resolver、三代 Research/Strategy/Draft/Post-review、两套 Trace 数据合同 |
| SPLIT_CANDIDATE | `chat_service.py`、`business_handlers.py`、`CompetitorReportService`、混合 agentChat client/API |
| REPLACE_CANDIDATE | 旧 Simple HTTP/crawler owner 由人工选定的 XHS provider owner 替换；未实现 Action 显式阻断 |
| QUARANTINE_CANDIDATE | Legacy Workbench/client、旧 AgentRuntime/tool/MCP/fallback 子图 |
| DEPRECATE_CANDIDATE | 旧 CRUD/V0/V2/operation workflow-specific endpoints、严格实验平台语义 |
| DELETE_CANDIDATE | 仅旧 `ContentExperimentWorkflow` 示例等无生产/迁移/Eval 价值项；必须留到 D.2 且再核外部消费者 |

# Executive Summary

- **Production Root：123 个**：119 个已注册 Backend HTTP operation、2 个 Frontend route、2 个进程启动 root。另确认 startup/lifespan/background worker/scheduler 为 NONE。Root 数量高不代表均应保留；多数后端 endpoint 属于 `LEGACY_ACTIVE`。
- **核心 Capability：22 个**；另发现 4 个历史 Capability（Viral、严格实验平台、Startup Strategy、通用动态 MCP）。
- **多个 Production Owner 的 Capability：**Agent Runtime（现行 + 旧测试型实现）、Context Resolver、XHS Collection、Research Analysis、Strategy/Experiment、Draft、Review/Revision、Post-publish、Trace/Confirmation。其中当前真正由多个已注册生产入口承载的重点是 XHS Collection、Research、Strategy/Experiment、Draft、Post-publish。
- **主要 Legacy Subgraph：5 条**：旧超级工作台、旧 AgentRuntime/Tool Registry、三代竞品研究与实验、阶段性 Operation 超级流程、旧通用 MCP/动态 Tool。
- **P0：**Production→Rule Eval Baseline；XHS/Research/Strategy/Draft/Post-review 多 owner；统一 Agent 声明与真实 handler 不一致；新入口复用混合 Legacy Service；旧 fallback 存在成功式降级重接风险。
- **P1：**重复 Agent Runtime；大量旧 endpoint 仍注册；Failed Experiment 留在主 app；严格 A/B 语义 OUT_OF_SCOPE；Legacy 前端直选 workflow endpoints；控制权逆流；handler 过度编排；Viral 历史语义混入 Research。
- **需要人工决定的 Canonical Owner Candidate：**Control Agent Runtime、唯一 XHS Collection owner、Research analyzer、Strategy Artifact/实验卡关系、Draft/Review/Post-publish tools、Trace 数据合同。
- **UNKNOWN：**119 个运行时 operations 的外部消费者；声明但未接通的 Action 实际用户行为；manual/readonly provider 的部署用途；若干空表在其他环境的状态；startup_strategy 的历史离线用途；数据库精确行数与跨代 lineage。

本报告到 D.1 为止；未执行任何 Candidate Decision，未开始 D.2 Cleanup。
