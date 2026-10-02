# DEFECT-026 Account-Scoped Asset Index Final Report

## 1. RCA
核心 detail route 已存在，但没有 account-scoped list API、list route 和正式导航入口；用户必须知道内部 ID，Route exists 不等于 Product Entry exists。

## 2. API Design
新增只读 `GET /api/artifacts/research`、`/api/artifacts/strategy`、`/api/artifacts/draft`、`/api/publications`、`/api/reviews`，统一接收 `account_ref/page_no/page_size`。

## 3. Lightweight Summary Contract
各接口只返回导航所需 ref、名称/标题、状态、版本、时间及 lineage 摘要，不返回正文、Evidence、Prompt 或完整对象。

## 4. Pagination
默认 page_size=20，最大 100；数据库查询同时执行 account predicate、offset、limit 与 count。

## 5. Ownership
Repository 在 SQL 层按 account_id 过滤；不存在 Account 返回 `ACCOUNT_NOT_FOUND`。浏览器持久化值不是授权依据，detail/list API 仍携带 account_ref 并由后端校验。

## 6. Backend Implementation
沿用现有 repositories、`ProductReadService` 与 product-read router，分别增加最小 `list_*_by_account`，未建立通用 Asset 框架。

## 7. Frontend List Routes
新增 Research、Strategy、Draft、Published Content、Review 五个 dynamic-import list route，点击摘要进入既有 canonical detail route。

## 8. Navigation
左侧导航形成 Agent 对话、内容资产、发布与复盘、Trace 控制台的浅层结构；菜单通过 router name resolve，未复制路由配置。

## 9. Lazy Loading
五个 list view 与既有 detail view 均由 Vue Router dynamic import；列表不 eager import detail，也不预取 detail data。

## 10. Draft Discovery
真实 Edge：Account 8456 → Draft → 列表显示 Draft 2625 → 点击进入 `/agent/draft/2625`，无需手输 ID。

## 11. Publication Discovery
真实 Edge：Published Content 列表显示 canonical `Published Note 592`、Draft 与版本摘要；未修改 DEFECT-024。

## 12. Review Discovery
真实 Edge：Review 列表显示 `Review 2144` 并保留 published_note_ref；未修改 DEFECT-023 identity mapping。

## 13. Browser Verification
隔离 Edge 153 controlled 验收通过 Research、Strategy、Draft、Publication、Review 导航；Draft List→2625 Detail 成功；Network failures=[]，Console errors=[]，无 blank/404/500。

## 14. API Response Size
Account 8456、page_size=20：Research 2/720B；Strategy 1/287B；Draft 1/221B；Publication 1/266B；Review 2/298B。

## 15. Regression
Backend targeted 11 passed；backend full 667 passed/3 skipped；frontend 16 passed；vue-tsc 与 production build PASS；git diff --check PASS；Alembic `d8e9f0a1b2c3 (head)`；Migration=0。

## 16. DEFECT-026 Final Status
`FIXED / REGRESSION VERIFIED / REAL ACCOUNT-SCOPED ASSET DISCOVERY VERIFIED / FROZEN`。

## 17. E2E-012 Status
仍为 BLOCKED；DEFECT-021/022/023/024 未在本轮处理或降级。

## 18. 面试资产
更新既有 Q&A：产品入口需要 Account→Paginated List→Detail 的完整闭环，单有 detail route 不能构成可发现产品能力。

## 19. Next Step
按冻结顺序继续 DEFECT-021 browser verification；随后 DEFECT-023 + DEFECT-024，最后 DEFECT-022。不开始 Testing Track。

## 20. Git
未 commit、未 add、未 reset/restore/clean/stash；保留既有 dirty worktree。
