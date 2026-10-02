# Phase 2.7B E2E-008 Manual Publish Exact Draft Version

## 1. Contract

用户在 Draft Detail 显式选择 `draft_version_id`。系统只生成供人工复制的 PublishPackage，不调用自动发布；PublishedNote 登记只能继承 Package lineage，不能再次选择版本。

## 2. Implementation

- `GET /api/artifacts/draft/{ref}` 返回每个 DraftVersion 的 immutable snapshot 内容。
- `POST /api/publish-packages` 接收 `account_id + draft_version_id`。
- `POST /api/published-notes` 接收 `account_id + publish_package_ref + publish_url + published_at`。
- PublishPackage 持久化 `draft_id / draft_version_id / version_number / title / body / tags`。
- PublishedNote 持久化 `draft_id / draft_version_id`，版本仅从 Package 继承。
- Draft Detail 增加版本下拉、对应版本预览、生成发布包、复制内容、人工发布说明和登记入口。

## 3. Real Input

- Account: 8456
- Draft root: 2625
- Selected UI version: V2
- Canonical `draft_version_id`: 2087
- Parent: V1 / 2082
- Source: USER_REVISION

HTTP Draft Detail 返回 V1=2082、V2=2087，且每个版本均携带自身 snapshot。V2 同时是 latest，但请求明确提交 2087；服务不读取 latest 来决定发布版本。

## 4. Real HTTP Result

`POST /api/publish-packages` 请求提交 `account_id=8456, draft_version_id=2087`，返回：

- PublishPackage: 511
- draft_id: 2625
- draft_version_id: 2087
- version_number: 2
- auto_publish: false

`POST /api/published-notes` 只提交 Package 511 和人工登记字段，返回：

- PublishedNote: 592
- draft_id: 2625
- draft_version_id: 2087
- version_number: 2
- registration_source: USER_PROVIDED

验收 URL 使用明确的测试标识 `e2e-008-manual-2625-v2`；本轮未调用小红书 Provider、浏览器自动发布或自动发帖。

## 5. Snapshot Verification

数据库逐字段比较 Package 与 ContentDraftVersion 2087：

- title match: true
- body match: true
- tags match: true

Package 与 PublishedNote 的 `draft_id`、`draft_version_id` 完全一致。登记阶段未读取 Draft root version，也未接受 DraftVersion 参数，因此无法产生 Package(V2) → PublishedNote(V3) 的 mismatch。

## 6. Latest Independence

选择的 canonical identity 是 2087。Repository 通过该主键读取 ContentDraftVersion，并从 `draft_snapshot` 冻结内容。Draft root 的 current/latest 字段只用于详情元数据，不参与 Package 版本选择或 PublishedNote 登记。

## 7. Side Effects

Draft 2625 在验收后仍只有：

- 2082 / V1 / GENERATED
- 2087 / V2 / USER_REVISION

未创建 V3/V4，未执行 E2E-011，未产生 WorkflowRun、checkpoint、Pending、LLM 或 XHS Provider 调用。

## 8. Verification

- Targeted backend: 21 passed
- Frontend tests: 7 passed
- Frontend production build/typecheck: PASS
- Full backend first run: 639 passed / 3 skipped / 7 failed（legacy fake 缺少新字段）
- 修复兼容读取后，失败集合定向回归：21 passed
- 最终完整 backend 回归：646 passed / 3 skipped / 18 warnings
- Alembic current/head: `d8e9f0a1b2c3`
- `git diff --check`: PASS（仅既有 CRLF 提示）

## 9. Status

- `DEFECT-016 = FIXED / REGRESSION VERIFIED / REAL EXACT-VERSION PATH VERIFIED / FROZEN`
- `E2E-008 = PASS / USER-SELECTED V2 EXACT LINEAGE VERIFIED / FROZEN`

## 10. E2E-011

保留。E2E-008 只证明用户选择 V2 后 Package 与 PublishedNote 精确绑定 V2；未验证后续 Draft 演进至 V4 后 Post Publish Review 仍读取 V2。

## 11. Git

未执行 commit、reset、restore、clean、stash、`git add .` 或 `git add -A`。工作树原有大量用户改动均保留。
