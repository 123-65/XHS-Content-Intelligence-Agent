# Phase 2.7B Real E2E Acceptance 完成报告

## Control Semantic Model Routing / E2E-005 最新状态

- 最小路由：仅 TaskSemanticFrame 使用 `qwen3.8-flash` 和 per-call `enable_thinking=false`；默认 `qwen3.8-2.4t-a95b` 及其他生成节点行为不变。
- Regression：定向 44 passed；backend 620 passed / 3 skipped / 18 warnings；此前 frontend 7/7、typecheck/build、Alembic current=head、diff check 均 PASS；Migration=0，New Route=0。
- Controlled Semantic：真实 Qwen、is_mock=false、timeout=30、SDK retry=0；首轮 8124 ms SUCCESS，TaskSemanticFrame validation PASS，intent=RESEARCH，OBS 2097。
- Latency comparison：默认强模型相同 workload 约 92482 ms；flash model 8124 ms。
- ENV-005：`CONTROL_SEMANTIC_MODEL_LATENCY RESOLVED BY MODEL ROUTING`；历史 APIConnectionError 与 transport evidence 保留。
- E2E-005 Turn 1：Turn 124 / request `phase27b-e2e005-turn1-fastqwen-20260924-02`；OBS 2098 / 6189 ms / attempt 1 SUCCESS。
- Product result：`RESEARCH / EXECUTE_PLAN / FAILED`，warning=`多目标包含非 Workflow Intent`；Run/Pending/checkpoint 均为空，因此未执行 Turn 2 Resume。
- DEFECT-013：NOT REGISTERED；失败未进入 WAITING_USER/Pending/Resume 产品路径。

## DEFECT-014 Mixed-Goal Contract / E2E-005 Retry

- Contract：Workflow primary 下只允许 Workflow sub-goals；Semantic post-parse validation 是第一业务边界，Planner 保留 fail-closed safety net。
- Regression：定向 81 passed；backend 629 passed / 3 skipped / 18 warnings；frontend 7 passed；typecheck/build/diff/Alembic PASS；Migration=0，New Route=0。
- Turn 128：首轮 OBS 2104 SUCCESS 但包含非法 `QUERY_PROFILE`；OBS 2105 记录 `POST_PARSE_BUSINESS_VALIDATION / retryable=true`；第二轮 OBS 2106 SUCCESS，合法 RESEARCH Frame 进入 Planner。
- Real path：Planner READY，创建 `RESEARCH_V1` Run `wfr_801e92daac554ed9920927377da55997`；DEFECT-014 FIXED / VERIFIED。
- New blocker：XHS Provider 在 `collection_accounts` 返回 `XSEC_TOKEN_REQUIRED`；Run FAILED / checkpoint 3，Evidence Gate 未开始，Pending=null，Operation=0。
- E2E-005：BLOCKED BY ENV-006；未执行 Turn 2；DEFECT-013 NOT REGISTERED。

## 一、执行状态

- 主题：大学生/应届生考公考编内容研究；仅使用用户授权的 3 条 Note URL、2 条 Profile URL，未全站发现。
- Real Acceptance：`BLOCKED / NOT ACCEPTED`；Mock：0。

## 二、测试环境

- 2026-09-23，Asia/Shanghai；Phase 2.7A frozen SUT。
- Backend / Frontend / PostgreSQL 正常；Alembic current/head 均为 `c7d8e9f0a1b2`。
- Qwen `qwen-plus`、XHS read-only Provider 均 `is_mock=false`；Qwen 在 E2E-002 返回 `403 AccessDenied.Unpurchased`。
- Phase 2.7B Migration = 0，New Route = 0。

## 三、Acceptance Cases

| Case | Result | Evidence |
|---|---|---|
| E2E-001 Research | PASS WITH WARNINGS | conversation 874；turn 45；run `wfr_e5945bf23a4048a1b0f7fc7f215fc1be`；research 2862；PARTIAL_SUCCESS |
| E2E-002 Strategy | BLOCKED | Qwen 403；未创建 Strategy Run |
| E2E-003/004 Draft/Refine | BLOCKED | upstream |
| E2E-005 Resume | BLOCKED | ENV-004 nested retry 已修复；controlled Semantic 单请求仍 >30s；ENV-005；未执行 E2E Turn 1 |
| E2E-006 Idempotency | PASS | replay 136 ms，仍为 turn 45 / 同一 Run / 同一 artifact |
| E2E-007 Account Boundary | PASS | Research/Run/Conversation/messages/cursor 对 B 均拒绝；DEFECT-003 FIXED / VERIFIED |
| E2E-008 Publication | BLOCKED | upstream |
| E2E-009 Metrics | PARTIAL | automated evidence only |
| E2E-010 Review | BLOCKED | upstream |
| E2E-011 Version | PARTIAL | automated evidence only |
| E2E-012 Frontend | PARTIAL | 7/7 tests + build；browser trace pending |

## 四、Research

前两次分别暴露 DEFECT-001（materials 未进入语义输入）和 DEFECT-002（URL 被误判为 references）；均先记录证据再做最小修复。最终真实 Research 得到 3/3 Note、1/2 Profile、0 comments；Research 2862 可经 Product Read API 读取，Chat 只保存摘要。Warnings：`PARTIAL_XHS_COLLECTION`、`COMMENTS_PARTIAL_AFTER_TIMEOUT`、`PROVIDER_TIMEOUT_RETRIED`、`OCR_OCR_PROVIDER_NOT_CONFIGURED`、`COMMENTS_PARTIAL_FROM_PROVIDER`、`INSUFFICIENT_COMMENT_SAMPLE`。

## 五、Strategy

同一 conversation 发送“根据刚才那个研究帮我做选题”，真实 LLM 返回 403，未重跑 Research，未创建 Strategy Run。

## 六、Draft / Refinement

上游阻塞，未执行。

## 七、Pending Resume

未在 Provider 不稳定时构造伪真实链路，BLOCKED。

## 八、Idempotency

E2E-001 客户端 300 秒超时后未重发新请求；服务端同一 Run 最终完成。以相同 request ID/payload 回放，136 ms 返回原结果，无重复写入。

## 九、Account Boundary

- Research 2862 / Account 8602：403 `RESEARCH_ACCOUNT_MISMATCH`。
- Run / Account 8602：403 `RUN_ACCOUNT_MISMATCH`。
- Conversation 874 detail/messages（含 cursor）对 Account 8602 返回 403 `CONVERSATION_ACCOUNT_MISMATCH`。

## 十、Publication / Metrics / Review

真实链路被阻塞。自动回归证据不声明 Real PASS。

## 十一、Frontend

`npm test` 7/7；容器内 production build PASS。宿主机中文路径/沙箱异常由容器结果排除为产品问题。

## 十二、Defects

- DEFECT-001，P1，FUNCTIONAL / AI_BEHAVIOR：materials 未进入语义解析。最小修复后关闭。
- DEFECT-002，P1，AI_BEHAVIOR / CONVERSATION_CONTEXT：URL 被误解析为引用。最小修复后关闭。
- DEFECT-003，P0，SECURITY / API_CONTRACT：canonical ownership guard 已覆盖 detail/messages/state/cursor。FIXED / VERIFIED。
- ENV-002，ENVIRONMENT：Qwen `AccessDenied.Unpurchased`。OPEN。

## 十三、Warnings

- THIRD_PARTY / DEPRECATION：1 类 Starlette warning，后续升级。
- TEST_ENVIRONMENT：9 次 Pydantic Decimal serializer warning，Testing Track 处理。
- PROJECT：0 类。

## 十四、Latency Baseline

- LLM smoke：465 ms provider / 548 ms HTTP。
- E2E-001 failed attempt：29,132 ms；成功服务端链约 486,000 ms；客户端 300,059 ms 超时。
- Idempotent replay：136 ms；E2E-002 provider denial：1,831 ms。

## 十五、Regression

- 修复后完整回归：572 passed, 3 skipped, 18 warnings；新增计数来自安全测试触发既有 TEST_ENVIRONMENT Decimal serializer warning，无新增 warning 类。
- Frontend：7 passed；production build PASS。
- `git diff --check` PASS（仅既有 CRLF 提示）；Alembic current/head 一致。

## 十六、Acceptance Conclusion

`BLOCKED / NOT ACCEPTED`。E2E-001 真实完成但有 Partial warnings；E2E-002 起被真实 LLM 权限阻塞，并存在 P0 Conversation boundary gap。Automated Regression PASS 不等于 Real Acceptance PASS。

## 十七、CURRENT_PHASE.md

保持 Phase 2.7B BLOCKED，不写 COMPLETE；不进入 Allure / Schemathesis。

## 十八、Git

保留原有 Phase 2.x dirty worktree；未 reset / restore / clean / stash。本阶段仅改最小缺陷代码、测试和验收文档。

## Phase 2.7B Continuation：DEFECT-005 / 006 / 007

- DEFECT-005：Research Query Projection 遗漏 canonical Opportunity identity 3923，LLM 生成 `source_opportunity_id=1`，Repository 正确拒绝。Query boundary 修复后 `FIXED / VERIFIED`，原失败事务无 partial data。
- DEFECT-006：Planner 无条件把 semantic missing_info 升级为 blocker。Resolver/Planner 按 canonical resolution 与 typed input requiredness 最小修复，定向 66 passed、完整 backend 579 passed / 3 skipped，真实 turn 65 已创建 CONTENT_STRATEGY_V1 Run，`FIXED / VERIFIED`。
- E2E-002 最新结果：conversation 874 / turn 65 / run `wfr_f780fb64e168446786896cf4ccbb5b36` / Research 2862；在 `strategy_generation` 出现新的 `VALIDATION_ERROR`。
- DEFECT-007：`OPEN`；Strategy Artifact、Derived Opportunity、Operation Ledger 均为 0。已按 Stop Point 停止，未继续 E2E-003 或 Testing Track。

## Phase 2.7B Continuation：E2E-002 最终只读验收

- Workflow：conversation 874 / turn 76 / `wfr_2193edf65ec14dcfba2f224df3642406`；`CONTENT_STRATEGY_V1 / SUCCESS`；`error_snapshot=null`、warnings 为空，四个 step 均 SUCCESS。
- Lineage：Run 输入、状态与结果均解析到 Research 2862；Strategy 13 为 Account 8456 / Research 2862；Opportunity 3956 为 Strategy 13 的唯一派生项，`source_opportunity_id=3923`、`report_id=2862`。
- Evidence：Strategy 与 Opportunity 的正式 EvidenceRef 仅为 `research_report:2862`、`content_opportunity:3923`。既有回归证明只授权当前输入中的 canonical Opportunity，并拒绝未授权的 300、400、999。
- OBS-001：本次两次 structured 调用分别留下 Control 与 Strategy SUCCESS 记录；每次均首轮成功（实际 attempt count 1；`attempt_total=2` 是配置上限），`is_mock=false`；raw prompt/output 均未保存，structured candidate 的字符串被 hash 脱敏。
- Research reuse：Run 时间窗内 RESEARCH_V1 Run、Research Artifact、crawl task、refresh run、competitor account/note/comment 新增数均为 0；Research 2862 创建于 `2026-09-23 03:28:27`，早于本次 Strategy Run。
- Ledger：仅一条 `create_content_strategy_artifact:singleton` 成功记录，指向 Strategy 13 与 Opportunity 3956；数据库计数均为 1。
- Product Read：`GET /api/artifacts/strategy/13?account_ref=8456` 正常返回 typed contract 和 Opportunity 3956，不暴露 raw LLM response、secret 或 trace；既有自动回归覆盖 Strategy detail 跨 Account 拒绝。
- Conclusion：`DEFECT-007 = FIXED / VERIFIED`；`E2E-002 = PASS`。历史 Turn 65 / Turn 69 失败证据继续保留；未执行 E2E-003、Allure 或 Schemathesis。

## Phase 2.7B Continuation：E2E-003 / DEFECT-008

- 前置只读检查 PASS：Strategy 13 属于 Account 8456 / Research 2862；generated Opportunity 3956 属于 Strategy 13，source 为 3923；Product Read 正常。
- 正式请求：conversation 874，workspace 只保存 `opportunity_ref=3956`，自然语言“用这个写一篇，语气自然一点。”，client request `phase27b-e2e003-20260923-01`。
- 实际结果：AgentTurn 77 / FAILED；HTTP 500，349 ms；无 Run Ref。
- Failure stage：`UnifiedAgentService._workspace -> RepositoryContextIdentityReader.get_identity`。Adapter 对 `ContentOpportunity` 读取不存在的 `account_id`，抛出 `AttributeError`。
- Semantic / Planner：均未开始；因此不能声称 CONTENT_CREATE、约束保留或 READY Plan 已得到真实验证。
- Partial data：只有 FAILED 幂等记录；用户/助手消息、Content Creation Run、Draft Root/V1、Ledger、prompt evidence 均为 0。
- Reuse：执行窗口内新增 RESEARCH_V1、CONTENT_STRATEGY_V1、Research Artifact、Strategy Artifact、crawl task 与竞品采集均为 0。
- 判定：登记 `DEFECT-008 = OPEN / RCA CONFIRMED / NOT FIXED`；`E2E-003 = FAILED / BLOCKED BY DEFECT-008`。未重试、未连续修复、未执行 E2E-004、Allure 或 Schemathesis。

## Phase 2.7B Continuation：DEFECT-008 Fix / E2E-003 Retry

- Minimal Fix：Opportunity ownership 改为显式 type-specific resolution；generated Opportunity 沿 Strategy，historical Opportunity 沿 Research 获取 canonical Account。没有新增字段、Migration、Route、Repository，也不信任客户端 Account。
- Regression：定向 57 passed + 84 passed；完整 backend 588 passed / 3 skipped / 18 warnings；frontend 7/7；typecheck 与 production build PASS；Alembic current/head 均为 `c7d8e9f0a1b2`；diff check 无 whitespace error。
- Idempotency：旧 Turn 77 与失败 request 保留；修复后用新 client request 创建 Turn 84。
- DEFECT-008 verification：Turn 84 已通过 Opportunity 3956 Workspace ownership，真实 LLM 首轮返回 CONTENT_CREATE。`DEFECT-008 = FIXED / VERIFIED`。
- New defect：Resolver 没有把“这个”绑定到唯一 Workspace Opportunity 3956，返回 `REFERENCE_CONTEXT_MISSING`；Action/Status 为 CLARIFY/WAITING_USER，无 Run。
- Partial data：Turn 84 与两条消息存在；Draft、Version、Ledger、Content Creation Run 均为 0；Research/Strategy/XHS 无新增。
- Final：登记 `DEFECT-009 = OPEN / RCA EVIDENCE CAPTURED / NOT FIXED`；`E2E-003 = FAILED / BLOCKED BY DEFECT-009`。未执行 E2E-004。

## Phase 2.7B Continuation：DEFECT-009 Fix / E2E-003 Retry

- RCA：Turn 84 的 Semantic Reference 是 `UNKNOWN / 这个`；Workspace Opportunity 3956 在 Resolver input 中，但旧 Resolver 在候选枚举前因 UNKNOWN 无 TYPE_MAP 映射而直接 unresolved。
- Minimal Fix：仅在 Resolver 对有限 deictic UNKNOWN 使用 Intent 对应 expected reference type，再走冻结 priority 与 canonical identity；不修改 Prompt、Planner、Workflow、Repository、priority 或 Account Boundary。
- Regression：定向 82 passed；完整 backend 598 passed / 3 skipped / 18 warnings；frontend 7/7；typecheck、production build、diff check、Alembic current/head PASS。
- Retry：Turn 91 / client request `phase27b-e2e003-defect009-retry-20260923-01`；7,640 ms；Control Semantic attempt 1。
- Context/Planner：CONTENT_CREATE / EXECUTE_PLAN；启动 `CONTENT_CREATION_V1` Run `wfr_02c20c262f3c40a68e1fc94705b1741b`；Strategy 13、Opportunity 3956、Research 2862 与 source 3923 正确。
- DEFECT-009：`FIXED / VERIFIED`。
- New defect：Workflow 在 `evidence_retrieval` 返回 `VALIDATION_ERROR / Opportunity Evidence 类型不可检索: content_opportunity`。Draft generation/persistence/review NOT_STARTED，无 Draft、Version 或 Ledger。
- Final：登记 `DEFECT-010 = OPEN / RCA EVIDENCE CAPTURED / NOT FIXED`；`E2E-003 = FAILED / BLOCKED BY DEFECT-010`。未执行 E2E-004。

## Phase 2.7B Continuation：DEFECT-010 Fix / E2E-003 PASS

- Frozen RCA：Classification B。`content_opportunity:3923` 是 Source Opportunity lineage/grounding reference，不属于 NOTE/COMMENT/ACCOUNT retrieval contract；第一次不一致在 CONTENT_CREATION_V1 Evidence input assembly。
- Canonical projection：复用 Research 2862 的 `CompetitorAnalysisReport` 与 `CompetitorReportRepository`，typed 投影 ACCOUNT、NOTE、COMMENT；没有新 Repository、Route、Migration 或 Evidence 系统。
- Typed partition：Strategy 13 / Generated Opportunity 3956 保持 Business Context；Research 2862 / Source Opportunity 3923 保持 lineage/grounding；retrieval 只收到 `ACCOUNT:2914`、`NOTE:10998/10999/11000`。未知类型、cross Research、cross Account 继续拒绝。
- Regression：定向 122 passed；backend 600 passed / 3 skipped / 18 warnings；frontend 7/7；typecheck、production build、diff check、Alembic current/head PASS。
- Retry：Turn 95 / client request `phase27b-e2e003-defect010-retry-20260923-01` / 71,908 ms；Control Semantic、Draft Generation、Draft Review 均 attempt 1。
- Result：`CONTENT_CREATE / EXECUTE_PLAN`；Run `wfr_466d50889d364b74a098013a0256a4a0` / `CONTENT_CREATION_V1 / SUCCESS`。
- Draft：Root 2625；Version 2082 / V1；account 8456；strategy 13；selected opportunity 3956；parent null；created_from GENERATED；Product Read PASS；Ledger 167。
- Review：PASS；无 warnings。
- Final：`DEFECT-010 = FIXED / VERIFIED / FROZEN`；`E2E-003 = PASS`。未执行 E2E-004、Testing Track、Allure 或 Schemathesis。

## Phase 2.7B E2E-004：Draft Refinement / DEFECT-011

- Precondition：Draft Root 2625；V1 2082；version 1；parent null；account 8456；strategy 13；selected opportunity 3956；Product Read PASS。V1 title/body length 22/626，body MD5 `4004ba8f766c34feffa900b8e38af716`。
- Workspace：正式 contract 只提交 `draft_ref=2625`；没有完整 Draft JSON。当前 Workspace 不支持 version ref，Workflow 起始读取 latest V1 2082。
- Request：Turn 96 / client request `phase27b-e2e004-20260923-01` / 11,362 ms。
- Semantic / Planner：`CONTENT_REFINE / EXECUTE_PLAN`；用户的“开头更直接、语气更自然、核心内容不要大改”进入正式 state；启动 `CONTENT_REFINEMENT_V1` Run `wfr_c469888935bb4419936ecc4675d3ab32`。
- Verified lineage：Draft 2625 / source V1 2082、Strategy 13、Generated Opportunity 3956、Research 2862、Source Opportunity 3923 均正确。
- Failure：Refinement 仍使用旧 `_retrieval_refs()`，把合法 grounding ref `content_opportunity:3923` 当成 retrievable evidence，`evidence_retrieval=FAILED`。
- Partial data：revision/persistence NOT_STARTED；Root 2625 仍只有 V1；V1 hash 不变；V2=0；Ledger=0。
- Reuse：仅新增 CONTENT_REFINEMENT_V1 Run 1；Research/Strategy/Creation Run、Research/Strategy Artifact、Draft Root、Draft Version、XHS crawl 均新增 0。
- LLM：只有 Control Semantic，qwen/deepseek-v4-flash-0731，attempt 1 / 11,244 ms；Revision LLM 未调用。
- Final：`DEFECT-011 = OPEN / RCA EVIDENCE CAPTURED / NOT FIXED`；`E2E-004 = FAILED / BLOCKED BY DEFECT-011`。按 Stop Point 未修复，未执行 E2E-005 或 Testing Track。

## Phase 2.7B Continuation：DEFECT-011 Fix / E2E-004 Retry

- Minimal Fix：提取共享 `partition_opportunity_evidence()`，Creation 与 Refinement 统一把 `research_report/content_opportunity` 保留为 grounding，只把 Research typed NOTE/COMMENT/ACCOUNT projection 送入 retrieval；Refinement typed input 同时保留 Opportunity、grounding 和 context refs。
- Contract Parity：两条 Workflow 对相同 mixed refs 得到相同 grounding `[research_report, content_opportunity]` 与 retrieval `[NOTE]`；unknown、cross-Research、empty factual projection 继续失败。
- Version regression：同 Root append、next version、exact parent、`USER_REVISION`、stale branch rejection 和原版本不覆盖均通过。
- Regression：最小 39 passed；定向 151 passed / 1 warning；backend 600 passed / 3 skipped / 18 warnings；frontend 7/7；typecheck/build/diff/Alembic PASS；Migration=0、New Route=0。
- Retry：Account 8456 / Conversation 874 / Turn 103 / client request `phase27b-e2e004-defect011-retry-20260924-01`；正式 request payload 含 `workspace_selection.draft_ref=2625`。
- New defect：结果为 `CONTENT_REFINE / CLARIFY / WAITING_USER`，missing=`draft_ref`，`run_ref=null`。没有进入 Evidence Retrieval，因此 DEFECT-011 尚未得到真实 E2E 验证。
- Partial data：Turn 103 后新增 Refinement Run=0、Ledger=0、V2=0；Root 2625 仍仅 V1 2082，body MD5 `4004ba8f766c34feffa900b8e38af716`。
- Product Read：没有 V2 可验收；V1 状态保持不变。
- Interview：新增 1 条关于兄弟 Workflow contract drift 与 parity test 的 Q&A；未新增未经真实 V2 支撑的 immutable-version Q&A。
- Final：`DEFECT-011 = IMPLEMENTED / REGRESSION VERIFIED / REAL E2E NOT REACHED`；登记 `DEFECT-012 = OPEN / EVIDENCE CAPTURED / NOT FIXED`；`E2E-004 = FAILED / BLOCKED BY DEFECT-012`。
- Stop Point：未静默修复 DEFECT-012，未再次重试，未执行 E2E-005、Testing Track、Allure 或 Schemathesis。

## Phase 2.7B Continuation：DEFECT-012 Fix / E2E-004 PASS

- RCA：Classification B。Turn 96 与 Turn 103 文本、Account、Conversation、Workspace 均相同；前者 Semantic 输出 `ACTIVE_DRAFT / 这个开头`，后者 `references=[]`。旧 Resolver 因只遍历 Semantic references，没有消费唯一 canonical Workspace Draft。
- Minimal Fix：只修改 Context Resolver，复用既有 Intent→Expected Type；required type 尚未解析且无 unresolved/ambiguous 冲突时，按 `explicit → workspace` 使用唯一同类型 canonical candidate。没有通用 latest/active/recent fallback。
- Explicit Safety：非法或跨账号 explicit 继续阻断；合法 explicit 优先于 workspace；多候选 ambiguous；错误类型不能替代 required type；DEFECT-009 deictic 行为保持。
- Regression：Resolver 39 passed；定向 127 passed / 1 warning；backend 611 passed / 3 skipped / 18 warnings；frontend 7/7、typecheck/build、diff check、Alembic current/head PASS；Migration=0、New Route=0。
- Retry：Turn 110 / client request `phase27b-e2e004-defect012-retry-20260924-01` / 40,588 ms；CONTENT_REFINE / EXECUTE_PLAN；Run `wfr_d87115e85b3243d19986790c15a53848` / CONTENT_REFINEMENT_V1 / SUCCESS。
- Semantic：本次真实输出为 ACTIVE_DRAFT，attempt 1 / 23,589 ms；空-reference 与相同 Workspace 的 deterministic parity 由自动化回归验证。
- DEFECT-011 Evidence：grounding=`content_opportunity:3923`、`research_report:2862`；retrieval 仅 ACCOUNT 2914、NOTE 10998/10999/11000、COMMENT 11721..11742；所有 workflow steps SUCCESS。
- Revision：Draft Revision attempt 1 / 16,860 ms；qwen/deepseek-v4-flash-0731；非 Mock。
- Version：Root 2625；V1 2082/version 1/parent null/GENERATED；V2 2087/version 2/parent 2082/USER_REVISION。V1 body MD5 仍为 `4004ba8f766c34feffa900b8e38af716`；V2 body 非空且 MD5 为 `21634f608c2eadeac9cd31ce6a1ca077`。
- Ledger：Run 内仅 operation 186，`create_draft_version:singleton` success，结果精确指向 Root 2625 / V2 2087 / parent 2082。
- Product Read：status=REVISED，latest=2087/V2；versions 返回 V1 2082 与 V2 2087，Exact Parent=2082。
- Interview：新增 2 条 Q&A，分别沉淀 LLM SemanticReference 非确定性与 deterministic control，以及真实 V1/V2 immutable version chain。
- Final：`DEFECT-012 = FIXED / VERIFIED / FROZEN`；`DEFECT-011 = FIXED / VERIFIED / FROZEN`；`E2E-004 = PASS`。
- Next：`E2E-005 Pending Resume`。本轮未执行 E2E-005、Testing Track、Allure 或 Schemathesis。

## Phase 2.7B E2E-005：Pending Resume / ENV-003

- Frozen Scenario：第一轮只提供已授权 Profile URL，正式启动 `RESEARCH_V1`；Workflow 应在完成 growth context / account collection 后因缺少 Note Evidence 进入 `WAITING_USER`。第二轮应在同一 Conversation 只补充授权 Note URL，由 Orchestrator 命中 Pending 并 Resume 同一 Run。
- Preflight：Backend / PostgreSQL / Frontend 正常；LLM `qwen/deepseek-v4-flash-0731` 为 `available=true`、`is_mock=false`；crawler `readonly_xhs` 为 `available=true`、`is_mock=false`。
- Request 1：Account 8456 / Conversation 874 / Turn 111 / request `phase27b-e2e005-turn1-20260924-01`；正式 `POST /api/agent/turns`；只提供授权 Profile `/user/profile/5d38107b0000000012021405`。
- Actual：Turn 从 `2026-09-24 04:32:55` 执行至 `04:36:11`，最终 `FAILED`；错误为 `LLM structured call failed: Request timed out.`；总耗时 196209 ms。
- Workflow WAITING_USER：未到达。该请求停在 Control Semantic，新增 Workflow Run=0。
- Pending / Checkpoint：Conversation `active_pending_run_ref=null`、`active_pending_checkpoint_version=null`、`active_pending_interaction=null`；不存在 before checkpoint。
- Request 2 / Same Run Resume / Checkpoint After：未执行。没有合法 Pending 可消费，不允许伪造第二轮 Resume。
- Reuse / Idempotency：未产生 Workflow Operation、Artifact 或副作用；不存在已完成 Workflow step 可供复用，也不存在重复执行。
- Account Boundary：请求使用冻结 Account 8456；未创建额外账号数据。
- Defects：未发现 Pending/Resume 产品路径缺陷，故不登记 DEFECT-013。登记环境阻断 `ENV-003`。
- Interview：新增 0，更新 0。真实 Resume 未通过，不沉淀未经验证的面试结论；文件 `docs/interview/INTERVIEW_QA.md` 未修改。
- Final：`E2E-005 = BLOCKED BY ENV-003`。未执行 E2E-006、Testing Track、Allure 或 Schemathesis；未修改产品代码，未运行完整 regression。
- Next：恢复稳定 real LLM 后，使用新的 client_request_id 从 E2E-005 Turn 1 重试。

## Phase 2.7B E2E-005 Retry：ENV-003 REPRODUCED

- Environment Precheck：容器与 `.env` 的 provider=`qwen`、model=`deepseek-v4-flash-0731`、base URL host 完全一致；健康接口 `available=true`、`is_mock=false`；无 configuration drift，未读取或输出 API Key。
- Structured Smoke：直接调用 canonical `LLMClient.generate_structured()`，最小 `{ok: bool}` schema；结果 `ok=true`、`is_mock=false`；总耗时 7744 ms，provider latency 7743 ms；attempt 1/2 SUCCESS。
- OBS-001 Smoke Evidence：PromptRunLog 2071 / `phase27b_e2e005_env003_smoke` / SUCCESS / 7697 ms；raw prompt/output 为空，只保存 schema 与最小脱敏 attempt summary。
- Turn 1 Retry：Account 8456 / Conversation 874 / Turn 112 / request `phase27b-e2e005-turn1-retry-20260924-01`；仅提供授权 Profile URL；正式 `POST /api/agent/turns`。
- Turn 1 Actual：`FAILED`，`LLM structured call failed: Request timed out.`；2026-09-24 04:55:35 至 04:58:43，总耗时 187637 ms。
- Structured Evidence：PromptRunLog 2072/2073；provider=`qwen`、model=`deepseek-v4-flash-0731`、`is_mock=false`；attempt 1/2 latency 85138 ms，attempt 2/2 latency 101475 ms；均为 `PROVIDER_FAILED / STRUCTURED_GENERATION / LLM_PROVIDER_UNAVAILABLE`，第二次 `retry_exhausted=true`。
- WAITING_USER / Pending / Checkpoint Before：均未到达；新增 Workflow Run=0；Conversation pending run/checkpoint/interaction 均为 null。
- Turn 2 / Same Run Resume / Checkpoint After：未执行。不存在合法 Pending 和 Run，不允许伪造 Resume。
- Duplication Check：Workflow Operation 保持 186；Research Artifact 保持 2888；没有 Workflow、Operation 或 Artifact 副作用。
- Defects：`ENV-003 = REPRODUCED`。失败仍在真实 Provider 的 Control Semantic structured call，未进入 Pending/Resume 产品路径，因此 `DEFECT-013 = NOT REGISTERED`。
- Interview：新增 0，更新 0；`docs/interview/INTERVIEW_QA.md` 未修改。
- Final：`E2E-005 = BLOCKED BY ENV-003`。按合同停止，不再调用 Provider，不执行 E2E-006、Testing Track、Allure 或 Schemathesis。
- Next：等待 real LLM 服务稳定或外部环境状态变化；后续重试需新的明确授权。

## Phase 2.7B E2E-005 Second Authorized Retry：ENV-003 REPRODUCED

- Structured Smoke：canonical `LLMClient.generate_structured()` 最小 schema 首轮成功；`qwen/deepseek-v4-flash-0731`、`is_mock=false`；调用观测 2971 ms，PromptRunLog 2074 provider latency 2925 ms，attempt 1/2 SUCCESS。
- Turn 1：Account 8456 / Conversation 874 / Turn 113 / request `phase27b-e2e005-turn1-retry2-20260924-01`；仅提供同一授权 Profile URL；正式 `POST /api/agent/turns`。
- Actual：`FAILED`，`LLM structured call failed: Request timed out.`；2026-09-24 05:03:56 至 05:07:18，总耗时 201487 ms。
- OBS-001：PromptRunLog 2075/2076；attempt 1/2 latency 99376 ms，attempt 2/2 latency 101097 ms；均 `PROVIDER_FAILED / STRUCTURED_GENERATION / LLM_PROVIDER_UNAVAILABLE`，第二次 `retry_exhausted=true`；raw prompt/output 为空。
- Workflow / Pending / Checkpoint：未到达；新增 Run=0，Conversation pending run/checkpoint/interaction 均为 null。
- Duplication：Operation 保持 186；Research Artifact 保持 2888；无 Workflow、Operation 或 Artifact 副作用。
- Turn 2：未执行；不存在合法 Run/Pending，不能验收 same-run Resume。
- Defects：`ENV-003 = REPRODUCED`；尚未进入 Pending/Resume 产品路径，`DEFECT-013 = NOT REGISTERED`。
- Final：`E2E-005 = BLOCKED BY ENV-003`。按停止条件不再调用 Provider，不执行 E2E-006。

## Qwen Provider 切换后的 E2E-005 验证

- Runtime Provider：`.env` 与 backend 容器均为 provider=`qwen`、model=`qwen3.8-2.4t-a95b`、相同 base URL host；健康接口 `available=true`、`is_mock=false`；无 configuration drift。
- Qwen Structured Smoke：canonical `LLMClient.generate_structured()` 最小 schema 首轮 SUCCESS；调用观测 5722 ms，PromptRunLog 2077 provider latency 5661 ms，attempt 1/2。
- Old ENV-003：保留为旧 `deepseek-v4-flash-0731` model 下的历史 timeout 证据，不删除、不覆盖，也不直接外推到本次 Qwen model。
- Turn 1：Account 8456 / Conversation 874 / Turn 114 / request `phase27b-e2e005-turn1-qwen-20260924-01`；只提供正式授权 Profile URL。
- Qwen Actual：Control Semantic 两次 attempt 均 timeout；PromptRunLog 2078/2079，latency 102319/102079 ms，均 `PROVIDER_FAILED / STRUCTURED_GENERATION / LLM_PROVIDER_UNAVAILABLE`，第二次 `retry_exhausted=true`；Turn 总耗时 205466 ms。
- WAITING_USER / Pending / Checkpoint：未到达；新增 Workflow Run=0，Conversation pending run/checkpoint/interaction 均为 null。
- Turn 2 / Same Run：未执行；不存在合法 Run/Pending。
- Duplication：Operation 保持 186；Research Artifact 保持 2888；无 Workflow、Operation 或 Artifact 副作用。
- Defects：新增环境记录 `ENV-004 = QWEN_PROVIDER_TIMEOUT / OPEN`。尚未进入产品 Resume 路径，`DEFECT-013 = NOT REGISTERED`。
- Final：`E2E-005 = BLOCKED BY ENV-004`。按 Provider failure 停止，不执行 E2E-006。

## ENV-004 Qwen Control Semantic Timeout RCA

- Smoke vs Semantic：两者均通过 `LLMClient.generate_structured → QwenProvider(OpenAICompatibleProvider) → chat.completions.create`，provider/model/base URL 与 `response_format={type: json_object}` 完全相同。
- Request Parameter Diff：无。两条路径都未显式传 max_tokens/max_completion_tokens、temperature、top_p、thinking/reasoning、stream 或 extra_body；均使用同一 OpenAI SDK client、相同 timeout 与 retry 配置。
- Structured Schema Diff：Smoke 为 1 property / 168 schema chars，system+user 94 chars；TaskSemanticFrame 为 13 properties / 3990 schema chars，system+user 1073 chars。完整请求显著更复杂，但本轮未做 Token Audit。
- Timeout Source：运行配置与 SDK client 均为 timeout=30 秒；OpenAI SDK client `max_retries=2`，一次 SDK call 最多执行 3 次 HTTP 尝试。adapter 外层 Tenacity 再执行 2 attempts，因此 OBS 2078/2079 每条约 102 秒，而 Turn 总耗时约 205 秒。现有 evidence 未保存 HTTP status，只有客户端异常 `Request timed out`；时间与配置共同指向客户端 SDK 内部 timeout/retry exhaustion，而非 Provider 明确返回的 HTTP error。
- OBS-001：2077 SUCCESS / 5661 ms；2078 attempt 1/2 PROVIDER_FAILED / 102319 ms / retry_exhausted=false；2079 attempt 2/2 PROVIDER_FAILED / 102079 ms / retry_exhausted=true；provider=qwen、model=qwen3.8-2.4t-a95b、failure_stage=STRUCTURED_GENERATION、final_error=LLM_PROVIDER_UNAVAILABLE。
- Controlled Reproduction：未执行。现有 Turn 114 已使用真实相同 Semantic schema/参数稳定复现两次 timeout，且静态配置足以解释约 102 秒 attempt，不需要增加第三次 Provider 调用。
- First Divergence：完整 TaskSemanticFrame workload 未在单次 30 秒 HTTP 窗口内完成；最小 smoke 在 5.7 秒内完成。之后 SDK 内部重试隐藏在一条 OBS attempt 内，耗尽后 adapter 外层才进入第二次 attempt。
- RCA Classification：`D. Client/provider timeout configuration interaction`。复杂 workload 是触发条件；当前证据不能证明 response_format 参数不兼容，也不足以单独归类为永久的模型兼容性问题。
- Minimal Resolution Recommendation：后续独立变更中明确单一 retry owner；建议 OpenAI SDK client 使用 `max_retries=0`，保留 adapter 外层两次 attempt 与 OBS-001 evidence，再单独评估 Semantic 所需 timeout 或专用模型路由。本轮不修改 adapter、timeout、retry、Prompt、Schema 或业务代码。
- E2E Gate：`E2E-005` 不可继续；ENV-004 保持 OPEN。未执行 E2E-005、E2E-006 或 Testing Track。

## ENV-004 Nested Retry Fix / ENV-005

- Minimal Fix：OpenAI-compatible SDK client 初始化显式 `max_retries=0`；保留 timeout=30 秒、adapter structured attempts=2、Prompt、TaskSemanticFrame、model 与全部业务合同。
- Retry Ownership：adapter 成为唯一 retry owner，继续负责 attempt number、OBS-001、retry decision、retry_exhausted 与 error normalization。SDK 每个 adapter attempt 只发一次 HTTP 请求。
- Regression A-D：首轮 timeout 后成功总 HTTP=2；两轮 timeout 总 HTTP=2 而非 6；evidence 为 PROVIDER_FAILED→SUCCESS 或两条 PROVIDER_FAILED；首轮成功总 HTTP=1。QwenProvider 构造断言 `max_retries=0`。
- Regression E-F：既有 structured validation retry 与 secret/raw prompt 不记录测试保持通过。定向合计 44 passed。
- Full Regression：backend 615 passed / 3 skipped / 18 warnings；frontend 7/7；`vue-tsc --noEmit` PASS；production build PASS；`git diff --check` PASS；Alembic current=head=`c7d8e9f0a1b2`；本轮 Migration=0、New Route=0。
- Controlled Semantic：运行时确认 sdk_max_retries=0、timeout=30、Qwen real/non-mock。唯一调用使用与 E2E-005 相同 TaskSemanticFrame schema 和 Semantic prompt contract，不创建 AgentTurn/Workflow/业务数据；调用未在 30 秒观察窗口内返回成功结果，未重发。
- ENV-004 Final：`RESOLVED / REGRESSION VERIFIED`。nested retry amplification 已消除。
- ENV-005：`CONTROL_SEMANTIC_SINGLE_REQUEST_TIMEOUT / OPEN`。完整 Semantic workload 单次 latency 仍超过当前 timeout；按冻结合同停止，不提高 timeout、不换模型。
- E2E-005：`BLOCKED BY ENV-005`；未执行 Turn 1/Turn 2；`DEFECT-013 = NOT REGISTERED`。

## ENV-005 Control Semantic Timeout RCA

- Current Runtime Contract：provider=`qwen`、model=`qwen3.8-2.4t-a95b`、`is_mock=false`；production timeout=30 秒、SDK max_retries=0、adapter structured attempts=2。ENV-004 nested retry 已冻结关闭。
- Diagnostic Setup：一次性 client 局部 timeout=120 秒、max_retries=0；直接执行一次 `chat.completions.create`，不走 adapter retry；复用 E2E-005 相同 TaskSemanticFrame schema、Semantic system/user prompt、model/provider 与 `response_format=json_object`；HTTP calls=1。
- Result：start `2026-09-24T06:00:03.724013Z`，end `2026-09-24T06:01:56.667843Z`，latency 112951 ms；`PROVIDER_ERROR / APIConnectionError / Connection error.`。
- Structured Validation：`NOT_COMPLETED`；未获得可解析 response，TaskSemanticFrame 合法性无法验证；未保存 raw prompt/output。
- RCA Classification：`C. Provider/transport connection error`。错误发生在 120 秒阈值之前，不是客户端 timeout；没有 HTTP status，不能进一步归类服务端 HTTP 错误。单次诊断不支持 A（提高 timeout 即成功），也不足以证明 B（模型/schema 永久不兼容）。
- Latency Budget：即使忽略最终连接错误，入口控制层请求已等待约 113 秒且仍无结果；“技术上可能最终返回”与“适合每个 Turn 的实时控制层”必须分开评估。
- Recommendation：先在 Provider/endpoint 侧排查长请求连接稳定性、网关连接上限与该部署的服务日志；如连接稳定后 workload 仍无法在实时入口预算内完成，再评估 Control Semantic 专用的更快 structured model。不要仅继续提高 timeout。
- E2E Gate：`ENV-005 = RCA COMPLETE / PROVIDER_CONNECTION_ERROR / OPEN`；E2E-005 不可继续；未执行 E2E-005/E2E-006，`DEFECT-013 = NOT REGISTERED`。

## ENV-005 Transport Layer Isolation

- Exception Cause Chain：OpenAI SDK 对 timeout exception 抛 APITimeoutError，对其他 transport exception 使用 `raise APIConnectionError(request=...) from err`；inner cause/runtime context 原本存在。但当前 adapter/OBS 将异常归一化为外层字符串，第一次 112951 ms 诊断只留下 `APIConnectionError: Connection error.`，底层类型不可恢复。
- Timeout Mapping：production `timeout=30` 在 httpx 映射为 connect/read/write/pool 各 30 秒；diagnostic `timeout=120` 同样覆盖四项。SDK max_retries=0；没有 nested retry。
- Proxy / Docker / Network Path：backend 与宿主 HTTP_PROXY/HTTPS_PROXY/ALL_PROXY/NO_PROXY 均未设置；WinHTTP direct access。DNS 23 ms并解析出 IPv4/IPv6；三次 TLS 1.3 handshake 435/451/457 ms；普通 HTTPS root 404/3040 ms，authenticated `/models` 200/821 ms。基础链路未复现故障。
- Connection Lifecycle：httpx trust_env=true 但无环境代理；HTTP/1.1、HTTP/2 disabled；max connections=1000、max keepalive=100、keepalive expiry=5s。隔离诊断创建全新 Provider/client，不依赖旧 keepalive connection。
- Controlled Diagnostic：一次且仅一次完整 Control Semantic；相同 Qwen model、TaskSemanticFrame、Semantic prompt、response_format；timeout=120、SDK retries=0、adapter retries=0、HTTP calls=1。start `2026-09-24T06:08:47.713202Z`，end `06:10:20.190586Z`，latency 92482 ms；SUCCESS，structured validation PASS，TaskSemanticFrame valid，intent=RESEARCH、confidence=.92；未保存 raw prompt/output。
- First Confirmed Failure Layer：第一次诊断只能确认错误在 OpenAI SDK transport boundary 暴露；exact inner transport layer 未被 evidence 保存。第二次相同请求成功，故不能确认稳定的 DNS/TCP/TLS/pool/gateway/provider-close 故障。
- RCA Classification：`F. Evidence still insufficient`。上一次 connection error 未复现；没有底层 cause、HTTP status 或 Provider request correlation id，不能负责任地选择 A–E。可确认的是行为具有 intermittent 特征。
- Minimal Recommendation：先增强现有脱敏错误 evidence，使 APIConnectionError 记录 inner exception type/message、elapsed time 和安全 request correlation metadata；同时用诊断时间窗向 Provider/网关侧查询日志。不要先改网络、transport、endpoint、timeout 和模型多个变量。连接 RCA 完成后再决定修网络、HTTP transport、endpoint 或更快 Control model。
- E2E Gate：虽然请求在 92.5 秒最终成功，但该延迟不代表适合实时入口，且 transport 原因仍未知。`ENV-005 = TRANSPORT RCA INCOMPLETE / INTERMITTENT / OPEN`；E2E-005 不可继续；未执行 E2E-005/E2E-006。

## Phase 2.7B E2E-005：真实 Pending / Resume 与 DEFECT-013

- Turn 1：Account 8456 / Conversation 874 / Turn 144 / request `phase27b-e2e005-turn1-providerrestored-20260924-01`；正式 `POST /api/agent/turns`，只提交一条授权 Profile URL；HTTP 200，177361 ms。
- Provider Workload：canonical `XiaohongshuMcpProvider` 的 `collection_accounts=SUCCESS`；账号证据 2914 为 `xiaohongshu_mcp / XHS_MCP / is_mock=false`。`ENV-007 = RESOLVED / REAL PROVIDER WORKLOAD VERIFIED`。
- Workflow Pending：Control Semantic 与 Planner 进入 `RESEARCH_V1`；Run `wfr_2cbfe18c78734ff69be3e391360f1876` 在 Evidence Gate 因缺 Note Evidence 进入真正 Workflow `WAITING_USER`，不是 Control CLARIFY 或 Planner NEED_USER_INPUT。
- Durable Before：checkpoint=3；Pending=`CLARIFICATION / RESEARCH_V1_RESUME`，required fields=`note_urls,evidence_refs`；Conversation active pending 指向同一 Run/version。Step：growth_context SUCCESS，artifact_context SKIPPED，collection_accounts SUCCESS，collection_notes SKIPPED，evidence_retrieval SUCCESS，evidence_adapter SUCCESS，evidence_gate WAITING_USER，analysis/artifact_creation NOT_STARTED。
- Baseline：Run Operation=0、global Operation=222；Workspace Research Artifact=1、global Research Artifact=2900；Workspace Account Evidence=4、Note Evidence=3；collected account refs=`[2914]`。
- Turn 2：Turn 145 / request `phase27b-e2e005-turn2-resume-20260924-01`；第二个独立 `POST /api/agent/turns`，同一 Account/Conversation，只补 3 条授权 Note URL；未传 run_ref、未直接调用 Runtime.resume、未修改数据库。
- Same Run：before/after run_ref 均为 `wfr_2cbfe18c78734ff69be3e391360f1876`；checkpoint 3→5；execution_mode=`RESUME`，没有创建第二个 Run。
- Replay / Duplication：growth_context 与 collection_accounts 在 Resume 后均为 SKIPPED；processed Profile URL 仍为 1、collected account ref 仍为 2914。Run Operation 0→0、global Operation 222→222；Research Artifact、Account Evidence、Note Evidence 数量均不变，没有重复成功 operation 或 artifact。
- Pending Consumption：Run pending 与 Conversation active pending 均已清空，但 Run 最终为 FAILED，因此只能证明 Pending 被消费/清理，不能宣称成功 Resume。
- First Failure：Resume durable input 含 6 条 note candidates；Turn 2 正式 materials 中 3 条均为合法 XHS Note URL 且 token 非空，另外 3 条来自 Semantic Frame，均无 scheme/host/token。`build_resume_input(RESEARCH_V1)` 直接采用 `frame.note_urls`，`ResearchWorkflow._run` 在构造 `CollectXhsNotesInput` 时触发 Pydantic `note_urls 只能包含公开小红书 Note URL`。Provider/collection_notes 尚未调用，processed Note URL 仍为 0。
- Defect：`DEFECT-013 = OPEN / REAL PENDING-RESUME PATH REPRODUCED / CURRENT-TURN NOTE MATERIAL AUTHORITY GAP`。Turn 2 返回 `WORKFLOW_RESUME_EXECUTION_ERROR`，Run FAILED/checkpoint=5。
- Final：`E2E-005 = FAILED / BLOCKED BY DEFECT-013`。未重试 Turn 2，未执行 E2E-006、Testing Track 或 Full Regression；未修改产品代码。

## DEFECT-013 Resume Material Authority 修复与 E2E-005 Final Report

1. Frozen Material Authority Contract：当前 Turn 经 `CollectionAccessScope` 确认的 structured Note materials 非空时覆盖 Semantic Note values，不做 union；无 structured Note material 时保留旧行为。
2. Root Cause：Orchestrator 原先对 Semantic 和 Turn Note URL 直接 union，Resume builder 因而收到模型重建的非 URL 值。
3. Resume Input Construction：最小修复位于 Orchestrator canonical frame construction；Resume builder/Runtime 未改。
4. Structured Material vs Semantic Frame：structured Note 非空时胜出；Semantic 字段仍保留。
5. Authorization Boundary：仅接受同 Account、`USER_PROVIDED`、当前 Turn 内 URL；Profile 行为不变。
6. Regression：定向 103 passed。
7. Full Regression：backend 644 passed / 3 skipped / 18 warnings；frontend 7 passed；typecheck/container build/diff/Alembic PASS；Migration=0，New Route=0。
8. New Turn 1：Turn 150 / `phase27b-e2e005-defect013-turn1-20260925-02` / Run `wfr_ea16dbf2dbbc4400af91b5c14f7036e5`。
9. WAITING_USER / Pending：checkpoint=3，`RESEARCH_V1_RESUME`，required=`note_urls,evidence_refs`。
10. New Turn 2：Turn 151 / `phase27b-e2e005-defect013-turn2-20260925-01`，只有 3 条 Note materials。
11. Same Run Verification：same run_ref，checkpoint 3→5，`execution_mode=RESUME`。
12. Completed Step Replay：`growth_context=SKIPPED`，`collection_accounts=SKIPPED`，account ref 仍为 2914。
13. Note Provider Workload：`collection_notes=SUCCESS`，processed URL 恰好等于 3 条授权材料，refs=10998/10999/11000，真实 XHS MCP 数据。
14. Operation / Artifact Duplication：run operations 0→0，global operations 228→228，research artifacts 2902→2902，account/note evidence 2989/11126 均不变。
15. Pending Consumption：Run/Conversation Pending 均清空；因后续 analysis 失败，仅记录 consumed/cleared observation。
16. DEFECT-013 Final Status：`FIXED / REGRESSION VERIFIED / REAL MATERIAL AUTHORITY PATH VERIFIED`；Workflow 未最终完成，不标 FROZEN。
17. E2E-005 Final Status：`FAILED / BLOCKED BY ENV-008`。
18. 面试资产：新增 0，更新 1。
19. 下一步：隔离处理 `ENV-008 = COMPETITOR_ANALYSIS_PROVIDER_TIMEOUT / RCA COMPLETE / OPEN`；不进入 E2E-006/Testing Track。
20. Git：保留原 dirty worktree，未 reset/restore/clean/stash，未 commit。

ENV-008 证据：PromptRunLog 2130/2131，`competitor_semantic_analysis / qwen / qwen3.8-2.4t-a95b / is_mock=false / PROVIDER_FAILED`，latency=30872/30767 ms，`STRUCTURED_GENERATION / LLM_PROVIDER_UNAVAILABLE`，第二次 `retry_exhausted=true`。失败位于 Note collection、retrieval/adapter/gate 成功之后，不属于 material authority。
