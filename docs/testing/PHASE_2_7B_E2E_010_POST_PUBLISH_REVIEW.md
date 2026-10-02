# Phase 2.7B E2E-010 Post Publish Review Acceptance Report

## 1. Canonical Review Path

确认 canonical path 为 `POST /api/agent/turns` → Intent `POST_PUBLISH_REVIEW` → `POST_PUBLISH_REVIEW_V1` → query_post_publish_metrics → exact DraftVersion query → analyze_post_publish_review → Review Artifact → Strategy Candidate。Memory 仅能通过后续显式确认服务写入。

## 2. PublishedNote Baseline

Account 8456 / PublishedNote 592 / Draft 2625 / DraftVersion 2087(V2)；PrivateConversionSnapshot 416。执行前 Post Publish Review=37/max2135，Strategy Candidate=37/max37，Strategy Memory=451/max451，WorkflowRun=2641，Operation=265/max265，PromptRunLog=2171/max2171，MCP=847/max847。Note 592 没有 PublicMetricSnapshot。

## 3. Exact DraftVersion Resolution

代码路径通过 `resolve_published_binding` 得到 PublishedNote 的 canonical `draft_version_id=2087`，随后 QueryArtifact 显式提交 `draft_version_ref`，并检查 resolved version 与 metrics lineage 一致；不读取 Draft latest 来选择发布版本。但本轮真实 Workflow 未启动，未形成运行时 exact-version 证据。

## 4. Metric Context

Private Snapshot 416 为 dm_count=3、wechat_add_count=1，未提供 consultation/deal/revenue；canonical projection 使用 provided_fields 保持后三项 UNKNOWN。Note 592 Public Snapshot 数量为 0，合同要求不得编造公开指标。

## 5. Provenance / UNKNOWN

Private source 为 USER_ATTRIBUTED；未提供字段没有被转成 0。由于 Workflow 在 Planner 前置阶段被阻断，未到达 LLM grounding validation。

## 6. Agent Turn

Turn 177 因 PowerShell 未显式使用 UTF-8 而收到乱码，安全返回 UNKNOWN/CLARIFY，run_ref=null；该次无业务执行。

Turn 178 使用显式 UTF-8、新 client_request_id、Conversation 874、Workspace PublishedNote 592 和自然语言请求。返回 Intent `POST_PUBLISH_REVIEW`，但 Action=CLARIFY、required_fields=`research_artifact_ref`、run_ref=null。

## 7. Semantic / Resolver

真实 PromptRunLog 2173：provider=qwen、model=qwen3.8-flash、prompt version=v1、attempt 1、latency=4723ms、is_mock=false、structured status=SUCCESS。Primary Intent 正确为 Post Publish Review，PublishedNote 显式选择有效；同时产生一个 Content Strategy sub-goal。

## 8. Workflow Execution

未创建 WorkflowRun。Deterministic Planner 对 primary intent 与 sub-goals 分别构造 Workflow：Post Publish Review 可由 PublishedNote 592 满足，但额外 CONTENT_STRATEGY workflow 要求 Research Artifact，于是整份 Plan 返回 NEED_USER_INPUT，并错误追问 `research_artifact_ref`。

## 9. LLM / Structured Validation

只执行 Control Semantic LLM；Post Publish Review Analysis LLM 未执行。没有 Review structured output、Pydantic、业务语义或 grounding validation 结果。

## 10. Review Artifact

未创建。Post Publish Review count/max 保持 37/2135。

## 11. Artifact Lineage

未创建 Artifact，因此不能声称真实 Review Artifact 已绑定 PublishedNote 592 / DraftVersion 2087。

## 12. Strategy Candidate

未创建，count/max 保持 37/37。

## 13. Memory Boundary

Strategy Memory count/max 保持 451/451。没有候选自动升级为 durable Memory。

## 14. Side-effect Check

WorkflowRun 保持 2641；Operation 保持 265/max265；MCP 保持 847/max847。PromptRunLog 仅因两次 Control Semantic 调用从 2171 增至 2173。没有 Review、Candidate、Memory、DraftVersion、PublishedNote lineage 或 Private Snapshot 变化。

## 15. Product Defect

`DEFECT-018 = OPEN / RCA CONFIRMED / NOT FIXED`。

分类：Semantic multi-goal / Planner contract defect。复盘请求中的“给出下一轮内容策略建议”属于 POST_PUBLISH_REVIEW_V1 本身产出的 PROPOSED Strategy Candidate，却被 Semantic 层升级为独立 CONTENT_STRATEGY sub-goal。Planner 因第二条 workflow 缺少 Research Artifact 阻断整个可执行的 Post Publish Review，导致 production entry 无法启动。

本轮按冻结规则只完成 RCA，没有修改 Prompt、Semantic、Planner 或 Workflow。

## 16. E2E-010 Final Status

`E2E-010 = BLOCKED BY DEFECT-018 / POST PUBLISH REVIEW WORKFLOW NOT STARTED`。

不能标记 PASS：真实 Agent path 未进入 Workflow/Analysis/Persistence。

## 17. 面试资产

未更新。当前只有缺陷证据，没有成功 Review/Exact Version/Provenance/Candidate 全链路，避免将阻塞案例包装为完成能力。

## 18. 下一步

单独冻结并授权 DEFECT-018 的最小修复：明确 Post Publish Review 内生 Strategy Candidate 与独立 CONTENT_STRATEGY workflow 的语义边界。修复前不重试 E2E-010，不执行 E2E-011，不开始 Testing Track。

## 19. Git

未修改产品代码；未 commit、reset、restore、clean、stash、`git add .` 或 `git add -A`。

---

# DEFECT-018 修复与 E2E-010 重验（2026-09-26）

## 1. RCA

Turn 178 的“下一轮内容策略建议”被错误拆成独立 CONTENT_STRATEGY，但 POST_PUBLISH_REVIEW_V1 本身已产出 review-derived Strategy Candidate。Planner 对合法的两个 Workflow 要求各自输入没有错；根因是 Semantic goal decomposition 没有执行 goal subsumption。

## 2. Goal Subsumption Contract

当 primary intent 为 POST_PUBLISH_REVIEW，下一轮优化建议、策略建议、内容方向与下一篇怎么改均属 Review 内生交付。只有明确请求独立 Strategy Artifact/Workflow，或基于某 Research 另外制定完整策略，才保留 CONTENT_STRATEGY sub-goal。

## 3. Semantic Fix

Control Semantic prompt 升级为 v2；post-parse business validation 将非独立 Review+Strategy 标记为 `REDUNDANT_SUB_GOAL / GOAL_SUBSUMED`，记录失败后把原因反馈给既有 structured retry。不静默删除模型输出。

## 4. Mixed-Goal Compatibility

显式“复盘 + 基于 Research 2862 另外创建完整内容策略”仍保留 POST_PUBLISH_REVIEW + CONTENT_STRATEGY。纯 CONTENT_STRATEGY 和 DEFECT-014 的 mixed-goal fail-closed 边界未改。

## 5. Regression

定向 Semantic/Planner/Orchestration：80 passed。Backend full suite：654 passed / 3 skipped / 18 warnings。Frontend tests：7/7 passed。Frontend build 已通过 vue-tsc 并 transform 3263 modules，但 Vite 进程随后无错误文本地以 code 1 退出，未记为完整 PASS。

## 6. Conversation Pending Check

Conversation 874 在重验前 `active_pending_run_ref/checkpoint/interaction` 均为 null，因此继续使用原 Conversation，未删除历史数据。

## 7. Real Agent Turn

Turn 182 / request `phase27b-e2e010-defect018-20260926-01`，Account 8456 / Conversation 874 / workspace PublishedNote 592，使用原始合理自然语言且保留“下一轮内容策略建议”。

## 8. Semantic Result

Intent=`POST_PUBLISH_REVIEW`，Action=`EXECUTE_PLAN`，未再询问 `research_artifact_ref`。PromptRunLog 2179：qwen / qwen3.8-flash / v2 / attempt 1 / 4572ms / is_mock=false / SUCCESS。

## 9. Workflow Execution

真实创建 POST_PUBLISH_REVIEW_V1 Run `wfr_b188f63e36b4418aa805173c2be33e2f`（id 2748），checkpoint=3。Run 在 metrics query 阶段进入 WAITING_USER，required_fields=`public_metrics`；analysis/artifact/candidate 未执行。

## 10. New Blocking RCA

Note 592 真实 PublicMetricSnapshot 数量为 0。`QueryPostPublishMetricsTool` 在指定窗口无公开快照时返回 CONTEXT_ERROR，Workflow 在行 144/191 将其转为 `WAITING_USER(public_metrics)`。这与 E2E-010 冻结合同“无公开指标时保持 UNKNOWN/unavailable，不得伪造”冲突。登记 `DEFECT-019 = OPEN / RCA CONFIRMED / ZERO-PUBLIC-METRICS REVIEW BLOCKED`，本轮不自动修复。

## 11. Exact DraftVersion

Canonical DB 仍确认 PublishedNote 592 -> Draft 2625 -> DraftVersion 2087 / V2。但本次 Run 在 metrics query 已阻断，尚未进入 QueryArtifact，因此不声称 runtime exact-version PASS。

## 12. Metric Provenance / UNKNOWN

Private Snapshot 416 只在 raw `provided_fields` 中提供 dm_count=3 / wechat_add_count=1，source=`USER_ATTRIBUTED`；consultation/deal/revenue 仍是 canonical UNKNOWN，DB 兼容列的 0 不得作为真实值。由于 metrics tool 提前失败，Review LLM 未使用这些数据。

## 13. Artifact / Candidate / Memory

Review Artifact 与 Strategy Candidate 均未新增；Strategy Memory count/max 保持 451/451，无 durable Memory 自动确认。

## 14. Side Effects

真实转向预期新增 Turn 182、PromptRunLog 2179 与 WorkflowRun 2748。本次 Run 的 durable Operation=0；Review 38/2136、Candidate 38/38、Memory 451/451 相对本次执行前基线均不变。DraftVersion 2087、PublishedNote 592 与 Private Snapshot 416 未修改。

## 15. Final Status

`DEFECT-018 = FIXED / REGRESSION VERIFIED / REAL WORKFLOW START VERIFIED / FROZEN`。

`E2E-010 = BLOCKED BY DEFECT-019 / ZERO-PUBLIC-METRICS CONTRACT PREVENTS REVIEW ANALYSIS`。

未执行 E2E-011，未开始 Testing Track。

---

# DEFECT-019 修复与 E2E-010 再验（2026-09-27）

## 1. Fix Contract

`QueryPostPublishMetricsTool` 在窗口内无 PublicMetricSnapshot 时返回合法 `PostPublishMetricsResult`：`public_metrics_status=UNKNOWN`、`public_metrics={}`、`missing_metrics` 包含 `public_metrics`，并继续返回真实 Private Snapshot。不再返回 CONTEXT_ERROR。

## 2. Workflow / Analysis Contract

POST_PUBLISH_REVIEW_V1 不再因公开快照缺失进入 WAITING_USER，而是添加 `PUBLIC_METRICS_UNKNOWN` warning 并继续 Analysis。`AnalyzePostPublishReviewInput` 允许 `UNKNOWN + empty public_metrics`，但拒绝 `AVAILABLE + empty` 或 `UNKNOWN + fabricated values`。

## 3. Prompt Contract

`post_publish_review_semantic` 升级为 v2，明确：公开 UNKNOWN 不得伪造或表述为 0；USER_ATTRIBUTED 私域数据可作为用户归因事实引用；私域 UNKNOWN 不得解释为 0。

## 4. Regression

定向 Query/Semantic/Workflow/Publication closure：38 passed。Backend full suite：654 passed / 3 skipped / 18 warnings。Frontend tests：7/7 passed。Container frontend `vue-tsc --noEmit && vite build` PASS（3263 modules）。Alembic current/head=`d8e9f0a1b2c3`，Migration=0。

## 5. Clean Conversation

Turn 182 遗留旧 WAITING_USER Run，因此通过 canonical Conversation API 创建同 Account 的干净 Conversation 1405，避免旧 Pending 被自动 Resume。未删除或修改历史 Run。

## 6. Real Agent Turn

Turn 186 / request `phase27b-e2e010-defect019-20260926-01`，Account 8456 / Conversation 1405 / Workspace PublishedNote 592，完全复用原自然语言，未提供、刷新或伪造 public metrics。Intent=`POST_PUBLISH_REVIEW`，Action=`EXECUTE_PLAN`。

## 7. Real Partial-Metrics State

Run `wfr_14485d5b1b0748a098dc8ef07902eb7b` / id 2798 真实持有：`public_metrics_status=UNKNOWN`、`public_metrics={}`、provenance 仅 `USER_ATTRIBUTED`；dm_count=3、wechat_add_count=1；consultation/deal/revenue=null + UNKNOWN。Warnings=`PUBLIC_METRICS_UNKNOWN`,`PRIVATE_METRICS_UNKNOWN`。未进入 WAITING_USER。

## 8. Exact Version Runtime Evidence

同一 Run 真实解析 PublishedNote 592 -> Draft 2625 -> `published_draft_version_ref=2087` / version 2，publish_package_ref=511；`published_draft.resolved_draft_version_ref=2087`，resolved content 来自 V2。该路径不使用 latest 替代发布版本。

## 9. Analysis Provider Result

Review Analysis 真实启动，但 provider=`qwen`、model=`qwen3.8-2.4t-a95b`、is_mock=false 的 OBS 2186/2187 在 30143ms/30133ms 均返回 `Request timed out`；structured parse/Pydantic/business grounding 未开始。这是独立的 Review LLM 执行策略/环境阻断，不是零公开指标合同回归。

## 10. Persistence / Side Effects

重验前后 Review=39/max2137、Candidate=39/max39、Memory=451/max451、Operation=277/max277，全部不变。仅新增预期 Turn 186、WorkflowRun 2798 与 PromptRunLog 2185-2187。DraftVersion 2087、PublishedNote 592、Private Snapshot 416 未修改。

## 11. Status

`DEFECT-019 = FIXED / REGRESSION VERIFIED / REAL PARTIAL-METRICS ANALYSIS PATH VERIFIED / FROZEN`。

`ENV-009 = POST_PUBLISH_REVIEW_STRONG_MODEL_30S_TIMEOUT / OPEN`。

`E2E-010 = BLOCKED BY ENV-009 / REVIEW ARTIFACT AND STRATEGY CANDIDATE NOT CREATED`。

未执行 E2E-011，未开始 Testing Track。

---

# ENV-009 修复与 E2E-010 最终重验（2026-09-27）

## 1. Execution Policy

复用既有 `LLMClient.generate_structured` per-call override，新增 Review-only Settings：`LLM_POST_PUBLISH_REVIEW_MODEL=qwen3.8-flash`、`LLM_POST_PUBLISH_REVIEW_TIMEOUT_SECONDS=120`、`LLM_POST_PUBLISH_REVIEW_ENABLE_THINKING=false`。全局 strong model、Control Semantic、Research Analysis、Draft/Strategy/Revision 配置不变。专属配置缺失时回退全局 model/timeout，不强行注入 thinking override。

## 2. Retry Ownership

Qwen/OpenAI-compatible SDK `max_retries=0`；Adapter/Tenacity 仍为唯一 structured retry owner（max attempts=2）；POST_PUBLISH_REVIEW Workflow 对 Analysis Tool 仍 `retry=False`。无新 router/client，无三层 nested retry。

## 3. Regression

定向 Review policy + retry + Control/Research isolation：65 passed。Backend full suite：657 passed / 3 skipped / 18 warnings。Frontend tests 7/7；container typecheck/build PASS（3263 modules）。Alembic current/head=`d8e9f0a1b2c3`，Migration=0。

## 4. Real Turn

干净 Conversation 1406；Turn 187 / request `phase27b-e2e010-env009-20260927-01`；Account 8456 / PublishedNote 592；用户文本与之前完全相同，未补 public metrics。Run=`wfr_fec42605371241b296e31cf5d3cb4320`。

## 5. Structured Execution

OBS 2189：provider=qwen、model=qwen3.8-flash、prompt=`post_publish_review_semantic/v2`、attempt 1/2、latency=14098ms、status=SUCCESS、is_mock=false。JSON parse 与 Pydantic `PostPublishReviewLLMResult` PASS，证明 Review-specific model/timeout/thinking policy 真实生效且解决 30s timeout。

## 6. Runtime Context

Run 已真实通过 metrics/exact-version 阶段：PublishedNote 592 -> Draft 2625 -> DraftVersion 2087/V2 / Package 511；public=`UNKNOWN/{}`；private dm=3、wechat=1 / USER_ATTRIBUTED；consultation/deal/revenue=UNKNOWN。

## 7. Grounding Failure RCA

Provider structured output 包含 evidence refs，但 `AnalyzePostPublishReviewTool` 从 `published_note.evidence_refs` 构造 allowed set，而 Workflow 的 `published_note` payload 未传入任何 evidence refs，因此 allowed set 为空。PostPublishReviewService 的 deterministic validation 将模型返回的 PublishedNote/Research 引用判为 invalid，Run 以 `VALIDATION_ERROR` 失败。这是 grounding input contract 缺口，不是 Flash JSON/Pydantic 质量失败，也不应依赖 strong+120 “恰好返回空引用”规避。

## 8. New Defect / Status

`ENV-009 = EXECUTION POLICY IMPLEMENTED / REGRESSION VERIFIED / REAL FLASH STRUCTURED WORKLOAD VERIFIED / FULL CLOSURE BLOCKED BY DEFECT-020`。由于冻结关闭条件要求 Artifact/Candidate 完整成功，本轮不冒充 RESOLVED/FROZEN。

`DEFECT-020 = OPEN / RCA CONFIRMED / REVIEW GROUNDING ALLOWLIST EMPTY`。

`E2E-010 = BLOCKED BY DEFECT-020 / REVIEW ARTIFACT AND STRATEGY CANDIDATE NOT CREATED`。

## 9. Side Effects

Account 8456 本次 E2E 仅新增 Turn 187、Run 2799、OBS 2188/2189；未新增 Review/Candidate/Memory/Operation，未修改 DraftVersion 2087、PublishedNote 592 或 Private Snapshot 416。全量测试在独立测试 Account 10775/10850 下生成 Review 2138/2139 与 Candidate 40/41；未清理或改写这些测试产物。

未执行 strong+120 Provider 调用，未修改 Prompt/Schema/Workflow/metrics contract，未执行 E2E-011 或 Testing Track。

---

# DEFECT-020 修复与 E2E-010 Final（2026-09-27）

## Evidence Data Flow

Producer：`QueryPostPublishMetricsTool` 产生 PublishedNote 592、Private Snapshot 416 与 exact version lineage；`QueryArtifactTool` 产生 Strategy 13 / Opportunity 3956 及其有限 canonical evidence refs。Carrier：`PostPublishMetricsResult` 保留 snapshot ref，Workflow state 保留 resolved views，`AnalyzePostPublishReviewInput.grounding_refs` 显式承载。Consumer：`AnalyzePostPublishReviewTool` 将该有限集传给 `PostPublishReviewService`，Service 对 Review 顶层、Candidate supporting/contradicting refs 做确定性 allowlist 校验。

## Grounding Contract

真实 allowlist：`published_note:592` / canonical object context；`private_metric_snapshot:416` / USER_ATTRIBUTED；`research_report:2862` / resolved Strategy lineage；`content_opportunity:3923` / resolved Opportunity lineage。Public Snapshot 不存在，因此不创建 public metric ref。没有 Account-wide search、recent refs 扩张或 allow-all。

## Regression

Targeted grounding/query/workflow/artifact tests：53 passed。Backend full：660 passed / 3 skipped / 18 warnings。Frontend tests 7/7；container typecheck/build PASS。Migration=0，Alembic=`d8e9f0a1b2c3 (head)`。

## Real E2E

Conversation 1461 / Turn 197 / request `phase27b-e2e010-defect020-20260927-01` / Run `wfr_bd9133ef597b4f249919f1e55b917d6a`。原文本、Account 8456、PublishedNote 592；未补 public metrics。Run=`PARTIAL_SUCCESS`，仅 warnings=`PUBLIC_METRICS_UNKNOWN`,`PRIVATE_METRICS_UNKNOWN`，所有业务 steps 均 SUCCESS。

OBS 2206：qwen / qwen3.8-flash / thinking=false / timeout=120 / attempt 1/2 / 21607ms / is_mock=false / SUCCESS。JSON、Pydantic、Business validation、Grounding 全部 PASS。模型返回 refs 精确为 allowlist 四项，无拒绝 ref。

## Exact Version / Metrics

PublishedNote 592 -> Draft 2625 -> DraftVersion 2087/V2 / parent 2082 / Package 511。Public Snapshot count=0，status=UNKNOWN，metrics={}。Private Snapshot 416：dm=3、wechat=1 / USER_ATTRIBUTED；consultation/deal/revenue 在 Review 输出中明确为 UNKNOWN，未伪造为 0。

## Persistence / Memory Boundary

Review Artifact 2141：Account 8456 / PublishedNote 592 / Draft 2625 / SUCCESS，data facts 保留四项 refs 和 UNKNOWN/provenance 事实。Strategy Candidate 43/44：Account 8456 / Review 2141 / PROPOSED。Durable operations 296/297/298 分别对应 Review 和两个 Candidate。Account 8456 Strategy Memory 前后均为 0，无自动确认。

## Final Status

`DEFECT-020 = FIXED / REGRESSION VERIFIED / REAL GROUNDED REVIEW PATH VERIFIED / FROZEN`。

`E2E-010 = PASS / POST PUBLISH REVIEW EXACT VERSION + PROVENANCE + STRATEGY CANDIDATE BOUNDARY VERIFIED / FROZEN`。

下一步为 E2E-011 Published Version Consistency；本轮未执行 E2E-011/E2E-012/Testing Track。
