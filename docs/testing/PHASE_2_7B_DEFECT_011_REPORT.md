# Phase 2.7B DEFECT-011 Fix / E2E-004 Verification Report

## 一、Expected

Conversation 874 使用正式 Workspace `draft_ref=2625` 和自然语言“把这个开头改得更直接一点，整体语气再自然一些，核心内容不要大改。”，解析到 Draft Root 2625 当前 V1 2082，执行 `CONTENT_REFINEMENT_V1` 并在同一 Root 追加 immutable V2，parent 精确指向 2082。

## 二、Actual

- Turn：96
- Client Request：`phase27b-e2e004-20260923-01`
- Run：`wfr_c469888935bb4419936ecc4675d3ab32`
- Latency：11,362 ms
- Semantic：`CONTENT_REFINE`，attempt 1
- Planner：`EXECUTE_PLAN / READY`
- Workflow：`CONTENT_REFINEMENT_V1 / FAILED`
- Failure stage：`evidence_retrieval`
- Error：`VALIDATION_ERROR / Opportunity Evidence 类型不可检索: content_opportunity`

## 三、Verified Before Failure

- Workspace 只包含 `draft_ref=2625`；没有完整 Draft JSON。
- Draft resolution：SUCCESS；Root 2625、latest/source Version 2082 / V1。
- Opportunity resolution：SUCCESS；Generated Opportunity 3956、Strategy 13、Research 2862、Source Opportunity 3923。
- 用户要求已进入正式 state：开头更直接、整体语气更自然、核心内容不要大改。
- Research typed projection 已存在：ACCOUNT 2914、NOTE 10998/10999/11000、COMMENT 11721..11742。

### 接管时已有 Diff

上一会话已编辑 `semantic_contracts.py`、`content_creation.py`、`content_refinement.py`，并新增/更新共享 `evidence_partition.py`、Creation workflow tests、Refinement workflow tests。接管检查确认代码已形成完整实现，没有语法/import/schema 半成品；本会话保留这些修改，没有覆盖或重写。

## 四、Frozen RCA

`CONTENT_REFINEMENT_V1._retrieval_refs()` 仍使用 DEFECT-010 修复前的旧式 assembly：遍历宽 Strategy `opportunity.evidence_refs`，只映射 `competitor_note`，因此把合法 `content_opportunity:3923` 当成不可检索类型并失败。Creation Workflow 已完成 typed partition，但 Refinement Workflow 尚未复用该合同。

Creation 与 Refinement 是兄弟 Workflow，却各自维护了相似的 Evidence assembly。DEFECT-010 只修复了 Creation，Refinement 因合同实现漂移继续沿用旧逻辑；单模块回归没有覆盖两条 Workflow 的 contract parity。

## 五、Minimal Fix / Contract Parity

- 把 Creation 已验证的 Evidence partition 提取为小型共享实现 `partition_opportunity_evidence()`。
- Creation 与 Refinement 都通过同一 partition 得到 grounding refs 和 retrieval refs。
- `research_report`、`content_opportunity` 保留为 lineage/grounding；只有 Research typed projection 中的 NOTE、COMMENT、ACCOUNT 进入 retrieval。
- Generated Opportunity、source Opportunity、Research lineage 明确进入 `ReviseDraftInput` 和持久化 context。
- 真正未知类型、cross-Research factual ref、空 factual projection 继续 fail fast，不 silent skip。
- 无新增 Route、Migration、Repository 或 Evidence 类型。

相同 mixed refs `research_report:11`、`content_opportunity:21`、`competitor_note:31` 在 Creation 与 Refinement workflow 测试中均得到 grounding `[research_report:11, content_opportunity:21]` 和 retrieval `[NOTE:31]`。

## 六、Regression

- 最小检查：39 passed。
- 定向回归：151 passed / 1 warning，覆盖 Creation、Refinement、Evidence Retrieval、Draft persistence/version、Grounding、DEFECT-008/009/010 路径。
- Backend full：600 passed / 3 skipped / 18 warnings。
- Frontend：7/7；`vue-tsc --noEmit` PASS；production build PASS（仅既有 chunk-size warning）。
- `git diff --check` PASS（仅既有 CRLF 提示）。
- Alembic current / heads：`c7d8e9f0a1b2`；Migration = 0；New Route = 0。

## 七、Version Chain Automated Verification

- 同一 Draft Root 追加下一版本；V1→V2、V2→V3、V8→V9 均通过。
- 新版本 `parent_draft_ref` 精确指向执行时 latest/source version。
- `action=APPEND`、`created_from=USER_REVISION` 由服务端固定。
- stale base version 拒绝分叉；原版本不被覆盖；持久化返回 identity 不一致时失败。

## 八、E2E-004 Retry

- Account / Conversation：8456 / 874。
- Workspace：`draft_ref=2625`。
- Client Request：`phase27b-e2e004-defect011-retry-20260924-01`。
- Turn：103；耗时约 91.8 秒。
- Semantic：`CONTENT_REFINE`。
- Actual：`CLARIFY / WAITING_USER`，reason=`draft_ref`，`run_ref=null`。
- 持久化 request payload 明确包含 `workspace_selection.draft_ref=2625`，因此不是客户端漏传。
- 新增 `CONTENT_REFINEMENT_V1` Run：0；Operation Ledger：0；Evidence Retrieval / Revision / Persistence 均未开始。

该结果在 DEFECT-011 Evidence 路径之前暴露了新的 Context/Planner 缺陷，登记为 DEFECT-012；按 Stop Point 不继续静默修复或再次重试。

## 九、V1 / V2 State

- Revision：NOT_STARTED
- Draft Version Persistence：NOT_STARTED
- Review：当前冻结 Refinement Workflow 不包含 Review step；正式链路为 Revise → Persist。
- Draft Root：仍为 2625
- Version count：1
- Latest：2082 / V1
- V2：0
- V1 body MD5：`4004ba8f766c34feffa900b8e38af716`，未变化
- Operation Ledger：0

Retry 后只读核对仍为：Root 2625 仅 V1 2082，`version=1`、`parent=null`、`created_from=GENERATED`、body length 626、body MD5 `4004ba8f766c34feffa900b8e38af716`。V2 未创建，因此没有可验收的 Exact Parent 或 Product Read V2。

## 十、Reuse

- 历史失败 Turn 96 新增 `CONTENT_REFINEMENT_V1` Run：1；本次 Turn 103 retry 新增：0
- 新增 `RESEARCH_V1`：0
- 新增 `CONTENT_STRATEGY_V1`：0
- 新增 `CONTENT_CREATION_V1`：0
- 新增 Research Artifact：0
- 新增 Strategy Artifact：0
- 新增 Draft Root：0
- 新增 Draft Version：0
- 新增 XHS crawl task：0

Turn 103 没有创建任何 Workflow Run、Draft Version 或 Ledger；也没有重跑 Research、Strategy、Creation 或 XHS collection。

## 十一、Interview Asset

`docs/interview/INTERVIEW_QA.md` 新增 1 条高价值 Q&A：为什么同一个 Evidence Contract Bug 会在 Creation 修复后继续出现在 Refinement。由于真实 V2 尚未创建，不新增“immutable revision 已获真实 E2E 验证”的问答。

## 十二、Status / Next Step / Git

`DEFECT-011 = FIXED / VERIFIED / FROZEN`

`DEFECT-012 = FIXED / VERIFIED / FROZEN`

`E2E-004 = PASS`

Turn 110 / Run `wfr_d87115e85b3243d19986790c15a53848` 已真实验证 Refinement typed partition：grounding 保留 Source Opportunity 3923 / Research 2862，retrieval 仅含 ACCOUNT/NOTE/COMMENT。Root 2625 追加 V2 2087，version=2、parent=2082、created_from=USER_REVISION；V1 MD5 保持不变；Ledger 仅一条成功 persistence；Product Read latest=V2 并保留 V1/V2 lineage。

下一步：`E2E-005 Pending Resume`。

未执行 E2E-005、Testing Track、Allure 或 Schemathesis。

Git：保留既有 dirty worktree；未 reset / restore / clean / stash / commit。
