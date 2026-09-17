# PRODUCT RECOVERY SPRINT 3A 代码清理结果

## 结论

- 真实 XHS 采集与 Agent Workflow 主链路保留，`ANALYZE_COMPETITOR_DATA` 工具名未改变。
- 正式竞品分析默认使用 `LLM_STRUCTURED_V1`，通过统一 `LLMClient` 获取 Pydantic 结构化结果。
- 正式分析失败会显式返回 `ANALYSIS_PROVIDER_FAILED`、`ANALYSIS_SCHEMA_INVALID` 或 `ANALYSIS_GROUNDING_FAILED`，不会自动切换规则或 Mock。
- 旧语义规则已全部退出 `CompetitorReportService`，集中到显式 `RULE_BASELINE`。
- 未新增表、未修改数据库 schema、未新增 migration。

## 统计口径

- 文件数使用 `rg --files` 统计仓库文件，不含构建产物。
- Mock 引用数使用同一静态扫描表达式统计 `backend/app` 中命中的行：`\bmock\b|use_mock|mockprovider|mockllmprovider|seed_sample|\bdemo\b`。该数字包含“拒绝 Mock”的校验、历史字段和可观测性字段，不等于可执行 Mock 入口数。
- ORM 模型按 `__tablename__` 出现次数统计；48 个模型文件中有 49 个表模型。
- production-used table 从 `main.py` 已注册 Router、Agent Tool Registry、Service/Repository import 和模型直接引用反向核对。基础设施表 `alembic_version` 不计入业务模型。

## Before / After

| 指标 | Before | After |
| --- | ---: | ---: |
| backend Python 文件 | 393 | 384 |
| Service 文件 | 38 | 35 |
| API 文件 | 42 | 39 |
| `competitor_report_sev.py` 行数 | 462 | 132 |
| backend/app Mock/Demo 原始命中行 | 111 | 31 |
| 可执行生产 Mock/Demo 成功入口 | 8 | 0（真实 Agent/后端主链路） |
| 已删除文件 | 0 | 27 |
| 生产 Service 内散落语义规则文件 | 1 | 0 |
| 隔离后的规则基线文件 | 0 | 1 |
| 实际 DB table | 50 | 50 |
| SQLAlchemy table model | 49（48 个文件） | 49（48 个文件） |
| production-used table | 48 | 48 |
| legacy/unknown table | 1 | 1 |

剩余 31 行 Mock/Demo 命中均为拒绝规则、`is_mock`/metadata 可观测性、历史 schema 枚举或错误提示；不存在“真实 Provider 失败后返回 Mock 成功”的后端路径。

## 删除文件

共删除 27 个文件，其中 26 个在 Cleanup commit 删除，1 个 Agent 工作台 Demo fixture 在最终验收时删除。

### Production / Frontend

- `backend/app/api/content_draft_rout.py`
- `backend/app/api/demo_rout.py`
- `backend/app/api/review_report_rout.py`
- `backend/app/crawler/factory.py`
- `backend/app/crawler/mock_provider.py`
- `backend/app/crawler/provider.py`
- `backend/app/crawler/providers/manual.py`
- `backend/app/crawler/providers/seed_sample.py`
- `backend/app/crawler/providers/seed_sample_provider.py`
- `backend/app/crawler/xhs_public_crawler.py`
- `backend/app/llm/mock_client.py`
- `backend/app/llm/providers/mock_provider.py`
- `backend/app/repositories/content_draft_repo.py`
- `backend/app/repositories/review_report_repo.py`
- `backend/app/schemas/content_draft.py`
- `backend/app/schemas/review_report.py`
- `backend/app/services/content_draft_sev.py`
- `backend/app/services/demo_sev.py`
- `backend/app/services/review_report_sev.py`
- `frontend/src/api/crawler.ts`
- `frontend/src/api/draft.ts`
- `frontend/src/mock/agentChatDemo.ts`

### Dev / Test / Artifact

- `backend/scripts/agent_entry_preview_demo.py`
- `backend/tests/test_content_draft.py`
- `backend/tests/test_review_report.py`
- `backend/tests/test_xhs_public_crawler.py`
- `docs/demo_agent_entry_preview_result.json`

## 保留的 Legacy / Unknown

| 文件 | 分类 | 保留原因 |
| --- | --- | --- |
| `backend/app/api/post_publish_review_v0.py` | PRODUCTION_USED | `main.py` 仍注册，现有发布后复盘流程调用。 |
| `backend/app/services/post_publish_review_v0_sev.py` | PRODUCTION_USED | 上述 Router 与策略记忆确认流程仍引用；会拒绝 Mock 指标。 |
| `backend/app/schemas/post_publish_review_v0.py` | PRODUCTION_USED | v0 API 的现行请求/响应契约。 |
| `backend/app/agent/tools/fallback_registry.py` | PRODUCTION_USED | Agent Registry 仍引用；只生成失败/人工补充提示，不生成伪数据成功结果。 |
| `backend/app/agent/policies/fallback.py` | PRODUCTION_USED | 当前 Agent 降级决策依赖，降级状态显式暴露。 |
| `backend/scripts/create_demo_agent_trace.py` | TEST_ONLY | 仅被 `test_developer_trace.py` 用作 trace fixture，不从正常 API/UI 自动进入。 |
| `backend/app/models/trace_retention_policy.py` | DEFERRED_LEGACY_TABLE | 当前业务代码无直接引用；本 Sprint 冻结 migration 和删表，保留待统一 schema maintenance 处理。 |
| `frontend/src/mock/{account,experiments,metrics,notes,strategy,workflow}.ts` | LEGACY_UI | 仍被已注册的辅助页面直接引用，无法满足“无生产引用”删除条件；不在 Agent Workflow 主路径，列为未解决技术债。 |

## Semantic Rules

- 之前位置：`backend/app/services/competitor_report_sev.py`。
- 当前位置：`backend/app/analysis/competitor/rule_baseline.py`。
- `CompetitorReportService`、Evidence Builder、Report Assembler 均不再包含内容关键词表或 persona/content pillar 推理规则。
- 正式默认 Engine：`LLM_STRUCTURED_V1`。
- `RULE_BASELINE` 只能由请求或测试显式选择，无自动 fallback。

## LLM Analysis

- 统一入口：`backend/app/llm/client.py::LLMClient.generate_structured`。
- Structured schema：`CompetitorSemanticResult` 及其 persona、content pillars、audience demands、patterns、style、follow recommendation、opportunities、data gaps 子结构。
- Grounding：校验 ACCOUNT、NOTE、COMMENT、METRIC、OCR 引用以及结果中的 note/comment ID 集合。
- Prompt 将账号简介、笔记、评论和 OCR 标记为不可信数据，只允许分析已提供 evidence，并明确“相关性不等于因果”。
- Provider、schema、grounding 三类失败均显式透传到 Agent 执行结果。

## Agent / Mock

- `ANALYZE_COMPETITOR_DATA` 仍注册且由 Planner/Workflow 自动调用，无需用户手工触发工具。
- Agent 工作台“加载本地 Demo 数据”按钮及 fixture 已删除。
- 后端正式 Workflow 无 Mock Provider、Seed Sample 或规则自动降级。
- 测试 Fake 位于 `backend/tests` 与 `backend/evals/fakes.py`，不进入生产依赖图。

## 验证

- Backend：`485 passed, 1 skipped`。
- 新增竞品分析测试：Evidence Builder、LLM Analyzer、Grounding 均通过。
- Collector / Agent：包含既有真实 Collector 与 Agent Workflow 回归测试，完整测试集通过。
- Frontend：`vue-tsc --noEmit && vite build` 通过；仅保留既有 chunk size 警告。
- Diff：`git diff --check` 无 whitespace error，仅有 Windows LF/CRLF 提示。

## 未解决技术债

- 六个辅助前端页面仍由 `frontend/src/mock` 提供静态数据；它们不影响真实 Agent Workflow，但仍属于 production build 可达的 Legacy UI。
- `trace_retention_policy` 表模型当前只有 ORM 注册，无业务直接引用；因本 Sprint 禁止删表和 migration，标记为 `DEFERRED_LEGACY_TABLE`。
- 前端构建仍有两个约 1 MB 的 chunk，Vite 给出 chunk size warning；本轮未做前端性能重构。
