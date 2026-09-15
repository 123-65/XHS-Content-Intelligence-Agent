# B2 Account Setup Check + Data Source Config / 数据源配置 V0

## 目标

B2 先确认用户已经创建或选择一个真实存在的 `AccountProfile`，再让用户为该账号保存长期关注的数据源配置，包括：

- 关注关键词；
- 固定竞品账号；
- 参考笔记链接；
- 平台范围，目前默认小红书 `xhs`；
- 配置状态和最小刷新策略标记。

这些配置必须绑定到明确存在的 `account_id`，不会立即触发采集或分析。后续 B3 Manual Refresh 可以读取配置，再创建手动刷新任务。

## AccountProfile 审计结论

现有项目已经具备后端账号画像能力：

- Model：`AccountProfile`
- Schema：`AccountProfileCreate`、`AccountProfileUpdate`、`AccountProfileResponse`
- Repository：`AccountProfileRepository`
- Service：`AccountProfileService`
- API：`POST /accounts`、`GET /accounts`、`GET /accounts/{account_id}`、`PUT /accounts/{account_id}`

审计发现前端已有 `/account` 页面，但当前页面使用本地 store/mock 保存，不会调用后端创建真实 `AccountProfile`，因此不能作为 B2 数据源配置的可靠账号入口。

B2 的处理方式是：

- 不重复造账号系统；
- 复用现有 AccountProfile 后端 API；
- 在 Agent Workbench 增加最小账号画像创建 / 选择入口；
- DataSourceConfig 保存前必须要求用户选择或创建账号画像；
- 如果没有 `account_id`，前端提示“请先创建或选择账号画像”；
- 后端继续校验 `account_id` 是否真实存在，不存在返回 404。

## 不允许的默认绑定

B2 不允许假设系统已经预置账号定位。

- 不把任何账号定位写死为系统默认账号；
- 不把前端 demo、示例按钮或默认配置绑定到 `account_id=1`；
- 不把“27届双非本上岸 Agent 开发”写死为默认账号画像；
- 不把用户提供的考公小红书链接绑定到 Agent 求职账号；
- 链接只能作为 `seed_urls` / `note_urls` 测试样本，并且必须绑定到用户选择的账号画像；
- 不访问外部链接，不分析链接内容。

## 为什么需要这一层

B1 已经提供 Conversation + Current State V0，7.x 已经提供只读查询 Action，但系统仍不知道用户每天固定想关注什么。

如果没有数据源配置，用户每次都要重新输入关键词、竞品账号和链接。B2 把这些长期关注对象沉淀为账号级配置，让之后的“刷新今日数据”或“帮我跑今天选题分析”有明确输入来源。

## 与已有表的关系

项目已有：

- `keyword_seed`：规则生成或沉淀的关键词种子；
- `competitor_account`：采集结果中的竞品账号快照；
- `crawl_task`：一次采集任务；
- `xhs_note_snapshot`：笔记快照。

B2 新增 `account_data_source_config`，原因是它保存的是“用户长期关注哪些来源”的配置，不是一次任务，也不是一次采集结果。这样可以避免把配置和执行状态混在一起。

## 新增后端能力

- 新增模型：`AccountDataSourceConfig`
- 新增 Schema：`DataSourceConfigUpsert`、`DataSourceConfigUpdate`、`DataSourceConfigResponse`
- 新增 Repository：`DataSourceConfigRepository`
- 新增 Service：`DataSourceConfigService`
- 新增 API：`/agent/data-source-configs`
- 新增 Alembic migration：`b2c3d4e5f6a7_add_account_data_source_config.py`

API 能力：

- `POST /agent/data-source-configs`：按 `account_id + platform` upsert 配置；
- `GET /agent/data-source-configs?account_id=...`：查询账号配置列表；
- `GET /agent/data-source-configs/by-account/{account_id}?platform=xhs`：按账号和平台读取配置；
- `GET /agent/data-source-configs/{config_id}`：按 ID 读取配置；
- `PUT /agent/data-source-configs/{config_id}`：更新状态和来源配置。

## 新增前端能力

Agent Workbench 增加轻量“数据源配置”区域：

- 支持加载已有账号画像；
- 支持创建最小账号画像并自动选择；
- 使用当前 `account_id`；
- 支持保存/加载 `platform`、`status`、`keywords`、`competitor_accounts`、`note_urls`；
- 页面明确标注 `B2 Config Only`；
- 只保存配置，不提供真实采集或刷新按钮。

## 安全边界

B2 不做：

- 真实爬虫；
- 外部小红书调用；
- 自动定时任务；
- 数据刷新；
- 竞品报告生成；
- 内容机会生成；
- 草稿生成；
- LLM 调用；
- LangChain / LangGraph / Mem0 接入；
- Router / Planner / Validator / Orchestrator 重写；
- Conversation 重写。

## 给 B3 的接口约定

B3 Manual Refresh 可以按以下方式读取配置：

1. 根据用户当前账号读取 `GET /agent/data-source-configs/by-account/{account_id}?platform=xhs`；
2. 如果配置不存在，要求用户先补充数据源；
3. 如果配置 `status=DISABLED`，不创建刷新任务；
4. 只把 `keywords`、`competitor_accounts`、`note_urls` 作为候选输入；
5. 再由 B3 创建刷新任务或 dry-run 任务。

## 测试重点

本阶段测试覆盖：

- 创建配置；
- 同一账号和平台重复保存时 upsert；
- 按账号查询；
- 按 ID 查询；
- 更新配置状态和来源；
- 账号不存在返回 404；
- 配置不存在返回 404；
- 保存配置不会创建 `CrawlTask`。

## 结论

B2 是 Agent 从“能对话、能只读查询”走向“知道用户长期关注什么”的配置层。账号画像必须由用户创建或选择，数据源配置必须绑定到真实 `account_id`。它不执行采集，不生成分析结果，只为后续 B3 Manual Refresh 提供稳定、可校验、可复用的数据源输入。
