# B4 Evidence Refresh / 证据刷新 V0

## 1. B4 目标

B4 实现用户手动触发的“证据刷新”。用户在 Agent Workbench 点击按钮后，系统基于当前账号数据库里已经存在的真实竞品数据，复用已有 `CompetitorReportService.create_report()` 生成或刷新：

- `CompetitorAnalysisReport`
- `ViralNoteBreakdown`
- `ContentOpportunity`

B4 不负责采集外部小红书数据，也不负责今日运营分析或草稿生成。

## 2. 为什么复用 CompetitorReportService

项目已有的 `CompetitorReportService.create_report()` 已经完成：

- 读取真实非 mock 的 `CompetitorNote`
- 读取对应 `CompetitorComment`
- 生成 `CompetitorAnalysisReport`
- 生成 `ViralNoteBreakdown`
- 生成 `ContentOpportunity`
- 在数据不足时抛出 `DataAvailabilityError`

B4 只增加运行记录和产品入口，不重写竞品分析逻辑。

## 3. EvidenceRefreshRun 和 DataRefreshRun 的区别

B3 `DataRefreshRun` 是数据刷新请求记录：

- 读取 B2 DataSourceConfig；
- 尝试复用 CrawlTask / Provider；
- Provider 未配置时只记录请求；
- 不生成报告和内容机会。

B4 `EvidenceRefreshRun` 是证据分析刷新记录：

- 不访问外部链接；
- 不调用 Provider；
- 基于已入库真实竞品数据；
- 复用 CompetitorReportService 输出报告、拆解和内容机会。

## 4. 后端新增内容

新增：

- `backend/app/models/account_evidence_refresh_run.py`
- `backend/app/schemas/evidence_refresh_run.py`
- `backend/app/repositories/evidence_refresh_run_repo.py`
- `backend/app/services/evidence_refresh_run_sev.py`
- `backend/app/api/evidence_refresh_run.py`
- `backend/alembic/versions/b4d5e6f7a8b9_add_account_evidence_refresh_run.py`
- `backend/tests/test_evidence_refresh_run_api.py`

## 5. 前端新增内容

Agent Workbench 新增“证据刷新”区域：

- 当前账号下触发证据刷新；
- 输入 `keyword`；
- 选择 `target_metric`；
- 设置 `limit`；
- 可选关联 B3 `data_refresh_run_id`；
- 展示本次状态、`report_id`、note/comment 数量、breakdown/opportunity 数量、data_quality 和 hint；
- 展示最近证据刷新记录。

新增：

- `frontend/src/api/evidenceRefreshRun.ts`
- `frontend/src/types/evidenceRefreshRun.ts`

## 6. 数据不足处理

当账号没有真实竞品笔记、只有 mock 笔记，或关键词没有命中真实笔记时，`CompetitorReportService.create_report()` 会抛出 `DataAvailabilityError`。

B4 捕获该异常并记录：

- `status=DATA_INSUFFICIENT`
- `error_code=payload.reason`
- `error_message=payload.message`
- `stats=payload`

这类情况 HTTP 仍返回 200，因为它是正常业务状态，不是系统异常。

## 7. Mock / 假成功防护

B4 不创建假竞品笔记，不创建假评论，也不会把 `SeedSampleProvider` 数据包装成真实成功。

`CompetitorReportRepository.list_competitor_notes()` 只读取 `is_mock=False` 的笔记。只有 mock 数据时会返回 `DATA_INSUFFICIENT`。

## 8. 为什么本阶段不调用 LLM

B4 的目标是把已有结构化竞品数据转成可追踪证据结构。当前已有规则分析能力足够完成 V0 闭环。

引入 LLM 会扩大风险面：

- 需要 prompt 和 schema 管理；
- 需要 provider 状态处理；
- 可能误把不可信评论当指令；
- 会扩大测试范围。

因此 B4 不调用 LLM / SDK。

## 9. 为什么本阶段不访问外部小红书

外部数据获取属于 B3 Data Refresh / Provider 能力，不属于 B4。B4 只消费数据库中已经存在的真实竞品数据。

这保证了：

- 证据来源可追踪；
- 不绕过 Provider 边界；
- 不在 API 层写爬虫；
- 不把 seed_urls 当成已采集内容。

## 10. 测试结果

覆盖重点：

- 无竞品笔记时返回 `DATA_INSUFFICIENT`
- 只有 mock 竞品笔记时返回 `DATA_INSUFFICIENT`
- 有真实 `CompetitorNote` 时创建 report
- 有真实评论时生成 comment demands
- 成功后写入 `EvidenceRefreshRun.report_id`
- 成功后生成 `ViralNoteBreakdown`
- 成功后生成 `ContentOpportunity`
- 样本不足时返回 `PARTIAL`
- `data_refresh_run_id` 不存在或账号不匹配时返回 400
- 可按账号查询列表
- 可查询详情
- 不调用 LLM
- 不访问外部链接

## 11. 本阶段没有做什么

B4 没有做：

- 真实小红书爬虫；
- 外部链接访问；
- LLM / SDK 调用；
- 今日运营分析；
- 草稿生成；
- 自动发布；
- 自动评论；
- 定时任务；
- mock 数据伪装成功；
- 重写 CompetitorReportService。

## 12. 下一步 B5 计划

B5 可以把 B3 数据刷新、B4 证据刷新和后续运营分析串成 Operation Run：

- 用户说“帮我跑今天的选题分析”；
- 系统检查账号、数据源和刷新状态；
- 必要时提示先刷新；
- 基于证据生成今日分析计划；
- 再进入内容机会或草稿链路。
