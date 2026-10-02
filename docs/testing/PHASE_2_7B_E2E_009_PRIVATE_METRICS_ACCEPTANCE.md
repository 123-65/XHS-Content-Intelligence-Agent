# DEFECT-017 修复与 E2E-009 Private Metrics Final Report

## 1. Frozen Contract

Private Metrics 是用户手工提供的匿名聚合指标。UNKNOWN 不等于 0；缺失字段保持 UNKNOWN，显式 0 是有效业务值。验收 fixture 使用长度不超过 16 的 `E2E009_ACCEPT`，不修改数据库字段。

## 2. Canonical HTTP Entry

新增 production route：`POST /api/published-notes/{published_note_ref}/private-metrics`。它是 deterministic form write，直接复用现有 PrivateMetricsService/Repository，不经过 Agent、Workflow 或 LLM。

## 3. Request Contract

请求包含 account_id、label、window_start、window_end，以及可选 dm_count、wechat_add_count、consultation_count、deal_count、revenue。至少提交一个指标；客户端不能提交 provenance；时间窗口必须满足 start < end。

## 4. Ownership

Service 在写入前读取 PublishedNote 并验证 Account ownership。跨账号、不存在 Note、空指标和非法窗口均 fail closed，不产生 Snapshot。

## 5. UNKNOWN Semantics

Repository 的兼容物理列仍用 0 存储，但 raw snapshot 的 `provided_fields` 是语义权威。Canonical read 只对 provided fields 返回真实值，其他字段返回 null，不把兼容零误读为业务零。

## 6. Provenance

服务端统一设置 `USER_ATTRIBUTED`。请求 schema extra=forbid，因此客户端不能伪造 MEASURED 或 DERIVED。

## 7. Targeted Regression

16 passed。覆盖 partial、缺失字段、显式 0、全缺失拒绝、非法窗口、label 长度、跨账号、provenance 和 read compatibility。

## 8. Full Regression

- Backend：650 passed / 3 skipped / 18 warnings
- Frontend：7 passed
- Frontend typecheck/build：PASS
- Migration：0
- Alembic head 保持 `d8e9f0a1b2c3`

首次完整回归发现严格窗口使旧 refresh helper 构造零长度窗口；修复为 1 微秒合法窗口后，相关定向 5 passed，最终完整回归通过。

## 9. Initial UNKNOWN

真实写入前 `GET /api/publications/592?account_ref=8456` 返回 `private_metrics_status=UNKNOWN`、`private_metrics=[]`，Note 592 Private Snapshot 数量为 0。

## 10. Acceptance Test Input

明确标记为 E2E ACCEPTANCE TEST DATA，不代表真实运营事实：Account 8456、PublishedNote 592、label `E2E009_ACCEPT`、窗口 2026-09-25T00:00:00Z 至 2026-09-26T00:00:00Z、dm_count=3、wechat_add_count=1；其余指标未提交。

## 11. HTTP Write Result

Production HTTP 返回 201：Snapshot 416、PublishedNote 592、label `E2E009_ACCEPT`、provenance `USER_ATTRIBUTED`。响应 metrics 为 DM=3、微信新增=1，其余三项 null。

## 12. Read-Back Result

Canonical Publication Detail 返回 `private_metrics_status=AVAILABLE`，Snapshot 416 的 values 为 dm_count=3、wechat_add_count=1、consultation_count=null、deal_count=null、revenue=null，source_type=`USER_ATTRIBUTED`。

## 13. Missing Fields Verification

数据库兼容列 consultation/deal/revenue 为 0，但 `raw_snapshot.provided_fields=[dm_count,wechat_add_count]`。Canonical read 将三个未提供字段恢复为 null/UNKNOWN，没有把物理零泄漏为业务事实。

## 14. Public / Private Isolation

PublicMetricSnapshot 保持 464/max464。未调用 XHS Provider，未从点赞、收藏或评论推导私域指标；唯一来源是本次 USER_ATTRIBUTED 验收输入。

## 15. Lineage / Side Effects

PrivateConversionSnapshot 从 415/max415 增至 416/max416，仅新增预期 Snapshot 416。PublishedNote 592 仍为 Draft 2625 / DraftVersion 2087。Draft、DraftVersion、Operation、PromptRunLog、MCP Call 的验收基线均未因真实 HTTP 写入改变。

## 16. DEFECT-017 Final Status

`DEFECT-017 = FIXED / REGRESSION VERIFIED / REAL PRIVATE METRICS WRITE PATH VERIFIED / FROZEN`

## 17. E2E-009 Final Status

`E2E-009 = PASS / PRIVATE METRICS UNKNOWN-PARTIAL CONTRACT VERIFIED / FROZEN`

## 18. 面试资产

新增 1 个 Q&A：UNKNOWN 与显式 0 的区别，以及测试 fixture 与产品数据库约束冲突时应调整 fixture 而非无业务需求地扩表。

## 19. 下一步

E2E-010 Post Publish Review。不要开始 Testing Track。

## 20. Git

未 commit、reset、restore、clean、stash、`git add .` 或 `git add -A`。工作区原有用户改动保留。
