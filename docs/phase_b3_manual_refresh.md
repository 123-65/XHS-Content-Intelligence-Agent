# B3 Manual Refresh / 用户触发数据刷新 V0

## 1. 本阶段目标

B3 让用户在 Agent Workbench 中点击一次“刷新今日数据”，系统读取 B2 的账号级数据源配置，创建一条 `DataRefreshRun` 运行记录，并记录本次刷新使用了多少关键词、竞品账号和种子链接。

本阶段只做用户触发式刷新记录，不做定时任务，不做证据分析，不生成报告、内容机会或草稿。

## 2. 为什么 B3 做用户触发式刷新，而不是定时任务

当前项目还处在 Agent 产品入口和数据闭环建设阶段。用户触发式刷新更适合作为第一步：

- 用户明确知道什么时候刷新；
- 系统可以先验证 B2 配置是否可用；
- Provider 未配置时可以清楚反馈，不伪造采集结果；
- 避免过早引入 Scheduler、后台队列和自动运行状态管理。

定时任务需要更完整的调度、失败重试、频控、告警和权限策略，不属于 B3。

## 3. B3 和 B2 DataSourceConfig 的关系

B2 保存长期配置：

- `keywords`
- `competitor_accounts`
- `note_urls`
- `refresh_policy`
- `status`

B3 只读取 `status=ACTIVE` 的配置。没有启用配置时，系统会创建失败的刷新记录并返回：

```text
NO_ENABLED_DATA_SOURCE
```

如果配置中只有关键词、竞品账号和链接，而没有可供现有 Provider 消费的真实快照 payload，B3 不访问外部链接，也不伪造采集结果。

## 4. RefreshRun 表设计

新增表：

```text
account_data_refresh_run
```

字段：

- `id`
- `account_id`
- `data_source_config_id`
- `trigger_type`
- `status`
- `refresh_scope_days`
- `started_at`
- `finished_at`
- `stats`
- `error_code`
- `error_message`
- `created_at`
- `updated_at`

`stats` 使用 JSONB，保存轻量统计，不保存网页正文、raw html、Cookie、Token 或 API Key。

## 5. RefreshRun 状态流转

状态：

- `PENDING`
- `RUNNING`
- `SUCCESS`
- `PARTIAL`
- `FAILED`
- `PROVIDER_NOT_CONFIGURED`

当前 V0 的主要路径：

```text
USER_CLICK
-> 读取 ACTIVE DataSourceConfig
-> 创建 RefreshRun
-> 如果没有启用配置：FAILED / NO_ENABLED_DATA_SOURCE
-> 如果没有真实 Provider payload：PROVIDER_NOT_CONFIGURED
-> 如果后续接入真实 Provider：SUCCESS 或 PARTIAL
```

## 6. 如何复用已有 CrawlTask / Provider

项目已有：

- `CrawlTask`
- `CrawlerCollectionService`
- `BaseCrawlerProvider`
- `MCPXhsProvider`
- `ReadOnlyXhsProvider`
- `ManualSnapshotProvider`
- `SeedSampleProvider`

B3 不重写这些能力。当前实现仅在配置中存在人工整理的真实快照 payload 时，才会创建 `CrawlTask` 并调用现有 `CrawlerCollectionService`。

普通 `note_urls` 只是配置，不等于已经采集的数据；B3 不会根据 URL 直接访问外部页面。

## 7. Provider 未配置时如何处理

当前没有可直接基于 B2 配置访问外部小红书并返回真实数据的 Provider。

因此默认结果是：

```text
status=PROVIDER_NOT_CONFIGURED
error_code=PROVIDER_NOT_CONFIGURED
```

用户会看到：本次刷新请求已记录，但没有伪造采集结果。

## 8. 为什么不能伪造采集成功

伪造成功会污染后续链路：

- 竞品证据会混入假数据；
- 内容机会会被错误输入驱动；
- 策略记忆会沉淀错误结论；
- 用户无法判断系统是否真的刷新了数据。

所以 B3 宁可明确返回 `PROVIDER_NOT_CONFIGURED`，也不把 mock、seed sample 或空结果包装成真实成功。

## 9. 前端如何触发刷新

Agent Workbench 新增“数据刷新”区域：

- 显示当前 `account_id`；
- 提供“刷新今日数据”按钮；
- 调用 `POST /agent/data-refresh/runs`；
- 展示本次刷新状态；
- 展示最近刷新记录；
- Provider 未配置时显示明确提示。

## 10. 本阶段没有做什么

B3 没有做：

- 定时任务；
- Scheduler；
- 自动每日分析；
- 外部链接访问；
- 竞品报告生成；
- 内容机会生成；
- 评论洞察生成；
- 草稿生成；
- LLM / SDK 调用；
- Agent Orchestrator 接入；
- LangChain / LangGraph / Mem0 接入；
- mock 成功结果。

## 11. 测试结果

本阶段测试覆盖：

- `account_id` 不存在；
- 没有启用 DataSourceConfig；
- 有启用 DataSourceConfig 时创建刷新运行；
- `keyword_count` / `competitor_account_count` / `seed_url_count` 统计；
- Provider 未配置时返回 `PROVIDER_NOT_CONFIGURED`；
- 不创建假 `CrawlTask`；
- 不创建假 note；
- 不创建假 comment；
- 不生成竞品报告；
- 不生成内容机会；
- 可查询 run 列表；
- 可查询 run 详情；
- B2 DataSourceConfig 仍可用。

已执行验证：

```text
docker compose exec backend alembic upgrade head
结果：通过

docker compose exec backend python -m pytest tests/test_data_refresh_run_api.py -q -s -p no:cacheprovider --basetemp=.pytest_tmp
结果：7 passed

docker compose exec backend python -m pytest tests/test_data_source_config_api.py -q -s -p no:cacheprovider --basetemp=.pytest_tmp
结果：6 passed

docker compose exec backend python -m pytest tests/test_agent_conversation_api.py tests/test_agent_chat_conversation_flow.py -q -s -p no:cacheprovider --basetemp=.pytest_tmp
结果：18 passed

docker compose exec frontend ./node_modules/.bin/vue-tsc --noEmit
结果：通过

docker compose exec frontend npm run build
结果：通过，仅有既有 Vite 大 chunk warning
```

## 12. 下一阶段：B4 Evidence Refresh

B4 可以在 B3 的刷新运行记录基础上继续做 Evidence Refresh：

- 读取真实刷新结果；
- 构建 evidence snapshot；
- 标注数据来源和可信状态；
- 为后续分析和 Agent 编排提供可追踪证据。

B4 之前仍不应该把“帮我跑今天的选题分析”直接接进 Agent Orchestrator；这会留到后续 Operation Run 阶段统一编排。
