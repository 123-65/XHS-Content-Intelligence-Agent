# Real E2E Acceptance Cases

## Acceptance Contract

- SUT: XHS Growth Intelligence Agent, Phase 2.7A frozen baseline.
- Business topic: 大学生/应届生考公考编内容研究。
- Real material authorization: 用户明确提供 3 条公开 Note URL 和 2 条公开 Profile URL。
- Discovery boundary: 禁止全站发现；只允许使用用户提供的 URL。
- Mock policy: Production Mock = 0；Mock 不能当作 Real Acceptance PASS。
- Current execution gate: DEFECT-011 / DEFECT-012 `FIXED / VERIFIED / FROZEN`; E2E-003 / E2E-004 `PASS`; next `E2E-005 Pending Resume`。

## Authorized Material Manifest

| Material ID | Type | Canonical public resource | Authorization |
|---|---|---|---|
| NOTE-01 | XHS_NOTE | `/explore/6a335dbe000000000f01d537` | USER_PROVIDED |
| NOTE-02 | XHS_NOTE | `/explore/6aa3ac53000000002802e1a2` | USER_PROVIDED |
| NOTE-03 | XHS_NOTE | `/explore/6a9559df000000000502acf5` | USER_PROVIDED |
| PROFILE-01 | XHS_PROFILE | `/user/profile/5d38107b0000000012021405` | USER_PROVIDED |
| PROFILE-02 | XHS_PROFILE | `/user/profile/62aae883000000001b027c18` | USER_PROVIDED |

完整 URL（包含用户提供的临时查询参数）只在真正执行 E2E-001 时作为 Turn materials 使用，不写入长期测试文档。

## Case Matrix

| Case ID | Module | Objective | Priority | Precondition | Input | Steps | Expected | Actual | Result | Run Ref | Artifact Ref | Latency | Defect ID | Notes |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| E2E-001 | Research | 真实 URL 经 Unified Turn 产生 Research | P0 | Real LLM + authorized XHS provider | 3 Note + 2 Profile URL；考公考编研究 | POST `/api/agent/turns`; Read Research detail | RESEARCH; authorized URLs only; Runtime; persisted artifact | 3 Note + 1 Profile；PARTIAL_SUCCESS；真实 warnings | PASS WITH WARNINGS | wfr_e5945bf23a4048a1b0f7fc7f215fc1be | research=2862 | ~486000 ms server | DEFECT-001/002 closed | account=8456; conversation=874; turn=45 |
| E2E-002 | Strategy | Conversation 自动承接 Research | P0 | E2E-001 SUCCESS | “根据刚才那个研究帮我做选题” | Same conversation Turn; Read Strategy | CONTENT_STRATEGY; no Research rerun; opportunities readable | Turn 76 SUCCESS；Strategy 13；generated Opportunity 3956；Research 2862 被复用；Product Read 正常 | PASS | wfr_2193edf65ec14dcfba2f224df3642406 | strategy=13; opportunity=3956 | ~96214 ms run | DEFECT-007 FIXED / VERIFIED | conversation=874; turn=76; research=2862; source opportunity=3923 |
| E2E-003 | Draft | Opportunity Ref 生成 Draft V1 | P0 | E2E-002 SUCCESS | selected opportunity ref + “用这个写一篇，语气自然一点” | Select ref; same chat Turn; Read Draft | CONTENT_CREATE; only creation; root + V1; lineage | Typed partition 后 retrieval SUCCESS；Draft 2625 / Version 2082 V1 / Review PASS | PASS | wfr_466d50889d364b74a098013a0256a4a0 | draft=2625; version=2082 | 71908 ms HTTP | DEFECT-010 fixed | conversation=874; turn=95 |
| E2E-004 | Refinement | Same root 生成 V2 | P0 | E2E-003 SUCCESS | “把这个开头改得更直接一点，整体语气再自然一些，核心内容不要大改。” | Workspace draft ref; same conversation Turn; Read Draft versions | CONTENT_REFINE; V2 parent=V1; V1 preserved | Turn 110 SUCCESS；Root 2625；V2 2087/version 2/parent 2082；V1 hash preserved；retrieval excludes source Opportunity；Product Read PASS | PASS | wfr_d87115e85b3243d19986790c15a53848 | draft=2625; version=2087 | 40588 ms HTTP | DEFECT-011/012 fixed | conversation=874; turn=110 |
| E2E-005 | Runtime Resume | WAITING_USER 同 Run resume | P0 | Real LLM available | Missing-material Turn + follow-up | Submit turn 1/2 in same conversation | Same run_ref; checkpoint increments; pending clears | ENV-004 nested retry 已修复；真实 controlled Semantic 单请求仍未在 30 秒内返回，未允许进入 E2E | BLOCKED | - | - | controlled call >30s | ENV-005 | 未创建 Turn/Run/Pending；未发 E2E Turn 1 |
| E2E-006 | Idempotency | Durable retry and mismatch reject | P0 | Backend healthy | Same request ID replay | POST replay after client timeout | Same result/no duplicate | 原 turn 45 / 同 Run / research 2862 | PASS | wfr_e5945bf23a4048a1b0f7fc7f215fc1be | research=2862 | 136 ms replay | - | mismatch automated regression PASS |
| E2E-007 | Security | Account A resources denied to B | P0 | Two accounts/resources | Account B detail/run/conversation reads | Execute all cross-boundary GETs | All denied with formal codes | Research/Run/Conversation/messages/cursor 均完成 boundary 验证 | PASS | wfr_e5945bf23a4048a1b0f7fc7f215fc1be | research=2862 | - | DEFECT-003 FIXED | SEC-CONV-001..004 verified |
| E2E-008 | Publication | Bind exact Draft Version | P0 | E2E-004 + manual publication | Actual published URL/version | Formal manual binding; read Publication | Exact root/version retained after later versions | Upstream blocked | BLOCKED | - | - | - | ENV-001 | - |
| E2E-009 | Metrics | UNKNOWN then partial private metrics | P0 | E2E-008 SUCCESS | Public metrics; later partial private values | Read before/after private input | UNKNOWN, then only provided fields | Automated persistence/read regression PASS; real chain blocked | PARTIAL | regression | regression | automated | ENV-001 | - |
| E2E-010 | Post Review | Review exact publication facts | P0 | Publication + metrics | “分析一下这篇…” | Unified Turn; read review/candidates | Exact version; no UNKNOWN estimation; PROPOSED only | Upstream blocked | BLOCKED | - | - | - | ENV-001 | - |
| E2E-011 | Version Consistency | Published V2 remains review target | P0 | V1..V4, V2 published | Post review | Review resolves V2, never V4 | Automated regression PASS; real chain blocked | PARTIAL | regression | regression | automated | ENV-001 | - |
| E2E-012 | Frontend | Lazy-load network behavior | P1 | Browser + frontend | `/agent/chat`, then Draft route | Observe requests and state | No detail GET on Chat; Draft GET on open; chat retained | Architecture/build checks PASS; interactive browser trace pending | PARTIAL | - | - | automated | ENV-001 | Real browser trace after E2E data |

## Failure Taxonomy

`FUNCTIONAL`, `DATA_CONSISTENCY`, `API_CONTRACT`, `STATE_MACHINE`, `CONVERSATION_CONTEXT`, `AI_BEHAVIOR`, `SECURITY`, `PERFORMANCE`, `ENVIRONMENT`, `TEST_DATA`.

## Defect Record

### ENV-001

- Classification: ENVIRONMENT
- Severity: Blocker for Real Acceptance; not a product defect.
- Reproduction: `GET /api/providers/llm/health`.
- Expected: configured real low-cost LLM; `available=true`; `is_mock=false`.
- Actual: `configured=false`, `available=false`, `is_mock=false`, `error_code=LLM_CONFIG_MISSING`.
- Impact: E2E-001/E2E-002/E2E-003/E2E-004/E2E-005/E2E-008/E2E-010 cannot produce legitimate Real Acceptance evidence.
- Resolution needed: configure a real supported LLM API key and restart/reload backend configuration.

Status: RESOLVED before E2E-001. Qwen smoke returned `OK`, `available=true`, `is_mock=false`, latency 942 ms.

### ENV-003

- Classification: ENVIRONMENT / PROVIDER_TIMEOUT。
- Severity: Blocker for E2E-005 Real Acceptance；不是 Pending/Resume 产品缺陷。
- Reproduction: Account 8456 / Conversation 874，通过正式 `POST /api/agent/turns` 提交 E2E-005 Turn 1；只提供授权 Profile URL，使正式 `RESEARCH_V1` 在缺少 Note Evidence 时进入 `WAITING_USER`。
- Preflight: `/api/providers/health` 返回 LLM `available=true`、`is_mock=false`、model=`deepseek-v4-flash-0731`；crawler `available=true`、`is_mock=false`。
- Expected: Control Semantic 完成，创建 `RESEARCH_V1` Run；Workflow 在 evidence gate 持久化 `WAITING_USER` checkpoint 和 Pending Interaction。
- Actual: Turn 111 / request `phase27b-e2e005-turn1-20260924-01` 在 Control Semantic 阶段以 `LLM structured call failed: Request timed out.` 失败；耗时 196209 ms。新增 Workflow Run=0；Conversation active pending 仍为空；无 checkpoint、Pending、Operation 或 Artifact 可供 Resume。
- Stop: 未发送 Turn 2，未登记 DEFECT-013，未执行 E2E-006，未修改产品代码。
- Retry precheck: 容器与 `.env` 均为 `qwen / deepseek-v4-flash-0731`，base URL host 一致，`is_mock=false`；无 configuration drift。
- Structured smoke: `LLMClient.generate_structured()` 最小 schema 首轮成功；PromptRunLog 2071；provider latency 7697 ms；attempt 1/2；`is_mock=false`；raw prompt/output 均未保存。
- Retry actual: Turn 112 / request `phase27b-e2e005-turn1-retry-20260924-01`，耗时 187637 ms；两次 structured attempt 均 `PROVIDER_FAILED / LLM_PROVIDER_UNAVAILABLE / Request timed out`，PromptRunLog 2072/2073，latency 85138/101475 ms，第二次 `retry_exhausted=true`。
- Retry boundary: 新增 Workflow Run=0；Operation 保持 186；Research Artifact 保持 2888；Conversation Pending/checkpoint 仍为空；未发送 Turn 2。
- Second authorized retry smoke: PromptRunLog 2074；首轮 SUCCESS；provider latency 2925 ms；`is_mock=false`。
- Second authorized retry actual: Turn 113 / request `phase27b-e2e005-turn1-retry2-20260924-01`，耗时 201487 ms；PromptRunLog 2075/2076 两次均 `PROVIDER_FAILED / LLM_PROVIDER_UNAVAILABLE / Request timed out`，latency 99376/101097 ms，第二次 `retry_exhausted=true`。
- Second retry boundary: 新增 Workflow Run=0；Operation 仍为 186；Research Artifact 仍为 2888；Pending/checkpoint 仍为空；未发送 Turn 2。
- Status: `REPRODUCED`；E2E-005 `BLOCKED BY ENV-003`。

### ENV-004

- Classification: ENVIRONMENT / QWEN_PROVIDER_TIMEOUT。
- Environment: 运行容器与 `.env` 均为 provider=`qwen`、model=`qwen3.8-2.4t-a95b`、相同 base URL host；`available=true`、`is_mock=false`，无 configuration drift。
- Smoke: canonical `LLMClient.generate_structured()` 最小 schema 首轮成功；PromptRunLog 2077；provider latency 5661 ms；attempt 1/2。
- E2E Retry: Account 8456 / Conversation 874 / Turn 114 / request `phase27b-e2e005-turn1-qwen-20260924-01`；只提供授权 Profile URL。
- Actual: Control Semantic 两次真实 Qwen attempt 均 `PROVIDER_FAILED / LLM_PROVIDER_UNAVAILABLE / Request timed out`；PromptRunLog 2078/2079；latency 102319/102079 ms；Turn 总耗时 205466 ms。
- Boundary: 新增 Workflow Run=0；Pending/checkpoint 为空；Operation 保持 186；Research Artifact 保持 2888；未发送 Turn 2。
- Defect classification: 尚未进入 WAITING_USER / Pending / Resume 产品路径，`DEFECT-013 = NOT REGISTERED`。
- Historical separation: ENV-003 保留为旧 `deepseek-v4-flash-0731` model 环境证据；不把其结论直接套用到本次 Qwen model。本次独立记录为 ENV-004。
- Status: OPEN；E2E-005 `BLOCKED BY ENV-004`。
- RCA parameter comparison: Smoke 与 Control Semantic 使用同一 provider/model/base URL、`response_format=json_object`、SDK client 和 adapter；两者都未显式设置 max tokens、temperature、top_p、thinking/reasoning、stream 或 extra_body。差异仅为 system/user prompt 与 JSON Schema。
- RCA workload comparison: Smoke schema 1 property / 168 chars，system+user 94 chars；TaskSemanticFrame 13 properties / 3990 chars，system+user 1073 chars。这里只确认复杂度差异，未做 Token Audit。
- RCA timeout interaction: 运行配置 `llm_timeout_seconds=30`；OpenAI SDK client 实际 `timeout=30` 且默认 `max_retries=2`，所以一次 adapter attempt 最多包含 3 次 SDK HTTP 尝试。外层 structured adapter 又用 `llm_max_retries=2`。2078/2079 各约 102 秒与 `3×30s + SDK backoff` 一致。
- First divergence: 完整 TaskSemanticFrame workload 未在单次 SDK 30 秒窗口内返回；SDK 内部重试耗尽后才向 adapter 暴露 `Request timed out`，adapter 外层随后执行第二次 attempt。Smoke 在 5.7 秒内返回，没有触发该路径。
- RCA classification: `D. Client/provider timeout configuration interaction`。请求复杂度是触发条件；现有证据不足以单独判定 Qwen schema 不兼容或模型永久不适合该 workload。
- Recommendation only: 由 adapter 明确拥有唯一 retry layer，例如构造 OpenAI client 时设 `max_retries=0` 并保留现有外层 attempt/evidence；随后在独立变更中重新评估真实 Semantic 单次 timeout 与模型适配性。本轮不实施。
- Resolution: OpenAI-compatible SDK client 已显式 `max_retries=0`，timeout 保持 30 秒，adapter structured attempts 保持 2。定向 44 passed；完整 backend 615 passed / 3 skipped；frontend 7/7、typecheck/build、diff/Alembic PASS。
- Status: `RESOLVED / REGRESSION VERIFIED`；真实 controlled Semantic 验证暴露独立 ENV-005。

### ENV-005

- Classification: ENVIRONMENT / CONTROL_SEMANTIC_SINGLE_REQUEST_TIMEOUT。
- Precondition: ENV-004 修复已生效；运行 client `sdk_max_retries=0`、timeout=30、provider=`qwen`、model=`qwen3.8-2.4t-a95b`、`is_mock=false`。
- Controlled call: 使用 E2E-005 相同 TaskSemanticFrame schema、Semantic system/user prompt contract 与 Qwen provider/model；不创建 AgentTurn、Workflow 或业务数据。
- Actual: 唯一调用未在单次 30 秒窗口内返回，宿主观察边界结束且无成功 stdout；没有发起第二次 controlled call。
- Interpretation: nested retry amplification 已消失，但完整 Control Semantic workload latency 仍超过当前单请求 timeout。这是独立环境/模型 workload 问题，不是 Pending/Resume 产品缺陷。
- 120s isolated diagnostic: 仅一次 HTTP 请求；局部 timeout=120、SDK max_retries=0；相同 Qwen model、TaskSemanticFrame schema、Semantic prompt 与 response_format；未创建业务数据。
- Diagnostic actual: start=`2026-09-24T06:00:03.724013Z`，end=`2026-09-24T06:01:56.667843Z`，latency=112951 ms；结果为 `APIConnectionError: Connection error.`，不是 120 秒 timeout；structured validation 未开始。
- RCA classification: `C. Provider/transport connection error`。没有 HTTP status 或合法 structured response；现有证据不能判定单纯 30 秒 threshold mismatch，也不能证明模型在 120 秒内可完成该 workload。
- Transport inspection: OpenAI SDK 通过 `raise APIConnectionError(...) from err` 保留底层 cause，但既有 adapter/OBS 只记录外层 `Connection error.`，因此第一次 120 秒诊断的 cause/context 已丢失。httpx 整数 timeout 映射为 connect/read/write/pool 全部相同；局部 120 秒 override 同样作用于四类 timeout。
- Network path: backend 与宿主标准 proxy env 均未设置，WinHTTP 为 direct access；DNS 23 ms；三次 TLS 1.3 handshake 435/451/457 ms；HTTPS root 404/3040 ms、authenticated `/models` 200/821 ms。未发现稳定的基础链路故障。
- Connection lifecycle: httpx trust_env=true，但无 proxy env；HTTP/1.1，HTTP/2 disabled；pool max connections=1000、keepalive=100、expiry=5s。两次隔离诊断均使用新 client，不能直接归因于 stale keepalive reuse。
- Controlled transport diagnostic: 唯一新诊断仍为相同 Semantic contract、timeout=120、SDK/adapter retry=0、HTTP calls=1；start=`2026-09-24T06:08:47.713202Z`，end=`06:10:20.190586Z`，latency=92482 ms；结果 SUCCESS，TaskSemanticFrame validation PASS，intent=RESEARCH，confidence=0.92。
- Transport RCA: 上一次 112951 ms APIConnectionError 未复现，且当时没有保存 inner cause。无法用直接证据区分本地网络、httpx pool、upstream gateway、Provider 主动关闭或 TLS/protocol error。
- Final classification: `F. Evidence still insufficient`；ENV-005 保持 OPEN。当前请求偶尔可在 120 秒内完成，但约 92 秒也不证明适合实时 Control Semantic。
- Status: `TRANSPORT RCA INCOMPLETE / INTERMITTENT / OPEN`；E2E-005 `BLOCKED BY ENV-005`；`DEFECT-013 = NOT REGISTERED`。

### DEFECT-001

- Classification: FUNCTIONAL / AI_BEHAVIOR
- Severity: P1
- Reproduction: submit E2E-001 through `POST /api/agent/turns` with three `materials.note_urls` and two `materials.profile_urls`.
- Expected: Semantic RESEARCH retains the authorized URL references and Planner starts `RESEARCH_V1`.
- Actual: Semantic returns CLARIFY / WAITING_USER with reason “未提供任何小红书笔记 URL 或账号主页 URL”; `run_ref=null`; artifacts empty.
- Evidence: account 8456, conversation 840, turn 31, request ID `30343c9f-ffbe-4312-a463-bbd4c512a425`, latency 5763 ms.
- Impact: Real Research cannot start although the user supplied authorized materials.
- Next action: trace Turn materials into Semantic input before considering a minimal fix.

Status: CLOSED by minimal fix. Structured material presence is exposed to semantic parsing while actual URLs remain deterministically merged into the authorized scope.

### DEFECT-002

- Classification: AI_BEHAVIOR / CONVERSATION_CONTEXT
- Severity: P1
- Reproduction: E2E-001 after exposing complete material URLs to semantic parsing.
- Expected: URLs remain material inputs only.
- Actual: URLs were also interpreted as temporal/context references; Planner returned CLARIFY.
- Evidence: account 8456, conversation 874, turn 41, latency 29132 ms.
- Resolution: semantic parsing receives material counts, not URL bodies; actual URLs are merged deterministically after parsing.
- Status: CLOSED; targeted regression 25 passed.

### DEFECT-003

- Classification: SECURITY / API_CONTRACT
- Severity: P0
- Expected: Account B cannot read Account A Conversation.
- Actual: `GET /agent/conversations/{conversation_id}` has no account/authentication context; the rejection cannot be enforced or tested.
- Related evidence: Research and Run reads correctly reject Account 8602 with HTTP 403, but Conversation read contract is unscoped.
- Root Cause: Conversation detail/messages/state API 只按 conversation_id 调用 `db.get()`；Service 仅检查存在性，没有比较请求 account identity 与 canonical `conversation.account_id`。
- Fix: 正式 Conversation list/detail/messages/state/patch 接收 account_ref；Service 先加载 canonical Conversation，再严格验证 ownership；messages cursor 在 ownership guard 之后执行；前端消息分页携带当前 account_ref；禁止通过 state patch 转移 ownership。
- Regression Case: SEC-CONV-001（owner 200 / B 403）、SEC-CONV-002（B messages 403）、SEC-CONV-003（B + before_id 403）、SEC-CONV-004（A cursor pagination 正常）。同时回归 Unified Agent 与 Phase 2.7A Product Read。
- Actual Result: 定向 36 passed；完整 572 passed, 3 skipped。真实 conversation 874 对 Account 8602 的 detail/messages cursor 返回 403 `CONVERSATION_ACCOUNT_MISMATCH`。
- Status: FIXED / VERIFIED。

### ENV-002

- Classification: ENVIRONMENT
- Reproduction: E2E-002 in conversation 874, “根据刚才那个研究帮我做选题”。
- Actual: Qwen returned HTTP 403 `AccessDenied.Unpurchased`; Turn failed before Strategy Run creation.
- Latency: 1831 ms.
- Status: OPEN; dependent Real cases remain BLOCKED. No Mock fallback used.

### DEFECT-004

- Classification: CONVERSATION_CONTEXT / FUNCTIONAL
- Severity: P1
- Reproduction: conversation 874, turn 56, “根据刚才那个研究帮我做选题”。
- Expected: Resolver uses recent Research 2862 and Planner starts `CONTENT_STRATEGY_V1` without requiring research_ref again.
- Actual: intent was CONTENT_STRATEGY, but resolved canonical Research did not satisfy redundant semantic `missing_info`; Planner returned CLARIFY / WAITING_USER before creating a Run.
- Evidence: turn 56, run_ref null, latency 7750 ms; conversation state contains trusted Research 2862.
- Root Cause: Resolver copied semantic `missing_info` into blocking inputs before resolution and never reconciled it after a valid Recent Research was resolved.
- Status: RECORDED; minimal fix and regression pending.

### DEFECT-005

- Classification: DATA_CONSISTENCY / FUNCTIONAL
- Expected: Strategy persistence 使用 Research 2862 下 canonical Opportunity 3923。
- Actual: Query Artifact Research 投影遗漏 opportunity identity，Semantic 输出 `source_opportunity_id=1`，Repository 报 `Source Opportunity 不存在: 1`。
- Fix: 在既有 Query Artifact Research 投影中提供 canonical `content_opportunities`；未修改下游 Repository 校验。
- Regression: 新测试修复前 FAIL、修复后 PASS；相关 38 passed。
- Partial data: Strategy Artifact 0，派生 Opportunity 0，Operation Ledger 0。
- Status: FIXED / AUTOMATED VERIFIED；真实 Retry 已越过该持久化缺陷前置代码，但被 DEFECT-006 提前阻塞。

### DEFECT-006

- Classification: AI_BEHAVIOR / FUNCTIONAL
- Severity: P1
- Expected: “根据刚才那个研究帮我做选题”结合 Recent Research 2862 直接执行 CONTENT_STRATEGY_V1；选题范围、数量或偏好不是冻结合同的必填项。
- Actual: turn 61 返回 `CONTENT_STRATEGY / CLARIFY / WAITING_USER`，理由为“未明确选题的具体范围、数量或偏好”，未创建 Run。
- Evidence: conversation 874，turn 61，latency 15370 ms，client_request_id `phase27b-e2e002-defect005-retry-20260923-01`。
- Root Cause: Planner 把原始 semantic missing_info 与 resolver blocker 无条件合并，绕过 typed input requiredness。
- Fix: 保留 semantic missing_info；Resolver 只输出 canonical unresolved/ambiguous blocker；Planner 由 typed Input Builder 判断 required input。
- Regression: 定向 66 passed；完整 backend 579 passed, 3 skipped；真实 turn 65 已 READY 并创建 CONTENT_STRATEGY_V1 Run。
- Status: FIXED / VERIFIED。

### DEFECT-007

- Classification: AI_BEHAVIOR / VALIDATION
- Severity: P1
- Expected: Strategy semantic output 通过结构与 evidence 校验，随后持久化 Strategy Artifact 与 Opportunity。
- Actual: run `wfr_f780fb64e168446786896cf4ccbb5b36` 在 `strategy_generation` FAILED，error `VALIDATION_ERROR`；artifact creation 未开始。
- Evidence: conversation 874，turn 65，Research 2862，canonical Opportunity 3923，latency 28634 ms。
- Partial data: Strategy Artifact 0，Derived Opportunity 0，Operation Ledger 0。
- Root Cause evidence: 原 Run 未保留 structured output、具体 validation details 或 attempt trace；相同上下文受控诊断首轮成功，无法证明原失败 field。
- Fix / Regression: 未执行，避免猜测式修改。
- Status: OPEN / RCA BLOCKED BY MISSING FAILURE EVIDENCE。

#### DEFECT-007 最终只读验收续记

- Turn 65 的原始失败证据与 Turn 69 经 OBS-001 捕获的真实失败证据均保留，不以成功 Run 覆盖历史记录。
- Root Cause：LLM 可见的正式输入包含 `research_report:2862` 与 canonical `content_opportunity:3923`，但原 semantic authorized evidence set 只包含 Research，导致合法的 Opportunity 引用被 post-parse business validation 拒绝。
- Fix boundary：只把当前正式输入 `historical_opportunities` 中的正整数 canonical identity 加入 allowlist；既有自动回归接受当前输入 200，并拒绝未授权的 300、400、999，因此不是“任意数据库 Opportunity ID 均可引用”。
- Real verification：conversation 874 / turn 76 / run `wfr_2193edf65ec14dcfba2f224df3642406` 为 `CONTENT_STRATEGY_V1 / SUCCESS`；Strategy 13 归属 Account 8456、Research 2862；Opportunity 3956 归属 Strategy 13，source 为 3923。
- Research reuse：Run 时间窗 `2026-09-23 08:49:19` 至 `08:50:55` 内，RESEARCH_V1 Run、Research Artifact、crawl task、refresh run、competitor account/note/comment 新增数均为 0。
- Persistence：该 Run 只有一条成功的 `create_content_strategy_artifact:singleton` Ledger；Strategy 13 与 generated Opportunity 3956 均只有一份。
- Product Read：`GET /api/artifacts/strategy/13?account_ref=8456` 返回正式 typed detail 与 Opportunity 3956，响应不含 raw LLM response、secret 或 trace。Strategy detail 跨 Account 拒绝由既有 Phase 2.7A 自动回归覆盖。
- Final status：`DEFECT-007 = FIXED / VERIFIED`；`E2E-002 = PASS`。该 E2E-002 验收轮次未执行 E2E-003。

### DEFECT-008

- Classification: FUNCTIONAL / DATA MODEL CONTRACT / CONTEXT RESOLUTION
- Severity: P0，阻塞 E2E-003 及后续真实链路。
- Reproduction: conversation 874，以 `workspace_selection={opportunity_ref:3956}` 提交自然语言“用这个写一篇，语气自然一点。”；client request `phase27b-e2e003-20260923-01`。
- Expected: Workspace Selection 解析 generated Opportunity 3956 的 Account ownership，随后进入 CONTENT_CREATE Semantic、Planner 和 `CONTENT_CREATION_V1`。
- Actual: `RepositoryContextIdentityReader.get_identity()` 对 `ContentOpportunity` 直接读取 `item.account_id`；正式模型没有该字段，HTTP 500：`'ContentOpportunity' object has no attribute 'account_id'`。
- Failure stage: `UnifiedAgentService._workspace` / canonical workspace identity lookup，发生在写入用户消息、调用 LLM、Semantic、Planner 和 Workflow 之前。
- Turn: AgentTurn 77，状态 FAILED；Run Ref 不存在。
- Partial data: 仅保留 FAILED 幂等记录；新增会话消息 0、Content Creation Run 0、Draft Root 0、Draft Version 0、Operation Ledger 0、prompt evidence 0。
- Root Cause Evidence: Opportunity 的 Account ownership 需要沿 `report_id` / Strategy lineage 由 canonical Repository 解析；通用 identity adapter 错误假设所有非 Account 模型都有直接 `account_id`。
- Fix / Regression: 显式按实体类型解析 ownership；定向 57 + 84 passed，完整 backend 588 passed / 3 skipped，frontend 7/7，typecheck/build 与 Alembic PASS。
- Real verification: Turn 84 成功通过 Opportunity 3956 Workspace ownership 并进入 CONTENT_CREATE Semantic；旧 Turn 77 保留。
- Status: `FIXED / VERIFIED`。后续 E2E-003 被新的 DEFECT-009 阻塞。

### DEFECT-009

- Classification: CONTEXT_RESOLUTION / FUNCTIONAL
- Expected: 自然语言“这个”与唯一可信 Workspace `opportunity_ref=3956` 解析为 generated Opportunity 3956。
- Actual: Turn 84 返回 `CLARIFY / WAITING_USER`，reason=`这个: REFERENCE_CONTEXT_MISSING`；没有 Run。
- Evidence: Control Semantic 为 CONTENT_CREATE、首轮 SUCCESS、constraints 非空；Workspace 仅含 Ref 且 canonical ownership 已通过。
- Partial data: Turn 与消息已保存；Run、Draft、Version、Ledger 为 0。
- Fix / Regression: Resolver 使用 Intent expected type 对有限 deictic UNKNOWN 走既有 priority 与 canonical ownership；定向 82 passed，完整 backend 598 passed / 3 skipped，frontend 7/7，typecheck/build 与 Alembic PASS。
- Real verification: Turn 91 为 CONTENT_CREATE / EXECUTE_PLAN，启动 CONTENT_CREATION_V1；input 为 Strategy 13 / Opportunity 3956，证明 Context 与 Planner 已通过。
- Status: `FIXED / VERIFIED`。后续 Evidence Retrieval 被新的 DEFECT-010 阻塞。

### DEFECT-010

- Classification: WORKFLOW EVIDENCE INPUT ASSEMBLY / FUNCTIONAL
- Expected: Draft Workflow 保留 Strategy 13 / generated Opportunity 3956 business context 与 Research 2862 / source Opportunity 3923 grounding，并只检索 NOTE/COMMENT/ACCOUNT。
- Actual: Run `wfr_02c20c262f3c40a68e1fc94705b1741b` 在 `evidence_retrieval` FAILED，错误 `Opportunity Evidence 类型不可检索: content_opportunity`。
- Partial data: Draft generation/persistence/review 均 NOT_STARTED；Draft、Version、Ledger 为 0。
- RCA: Classification B；`content_opportunity:3923` 是 lineage/grounding ref，不是 retrievable evidence。
- Fix: Research Artifact Query projection 暴露 typed ACCOUNT/NOTE/COMMENT refs；Workflow 显式 partition，unknown/cross-Research 仍 fail fast。
- Regression: 定向 122 passed；backend 600 passed / 3 skipped；frontend 7/7；typecheck/build/diff/Alembic PASS。
- Retry: Turn 95 / Run `wfr_466d50889d364b74a098013a0256a4a0` SUCCESS；retrieval=`ACCOUNT:2914`、`NOTE:10998/10999/11000`，未包含 `content_opportunity:3923`。
- Draft: Root 2625 / Version 2082 V1 / parent null / GENERATED；Product Read PASS；Review PASS。
- Status: `DEFECT-010 = FIXED / VERIFIED / FROZEN`；`E2E-003 = PASS`。未执行 E2E-004。

### DEFECT-011

- Classification: WORKFLOW EVIDENCE INPUT ASSEMBLY / FUNCTIONAL
- Expected: `CONTENT_REFINEMENT_V1` 基于 Draft 2625 / V1 2082 执行 revision，并追加 V2，parent=2082。
- Actual: Turn 96 / Run `wfr_c469888935bb4419936ecc4675d3ab32` 正确得到 CONTENT_REFINE / EXECUTE_PLAN，但在 `evidence_retrieval` 返回 `Opportunity Evidence 类型不可检索: content_opportunity`。
- Failure boundary: Draft resolution 与 Opportunity resolution SUCCESS；revision/persistence NOT_STARTED。
- Partial data: Root 2625 仍只有 V1 2082；V1 hash 未变化；无 V2、无 Ledger。
- Reuse: 只新增一个 CONTENT_REFINEMENT_V1 Run；Research/Strategy/Creation Run、Artifact、Draft Root、Draft Version、XHS collection 均无新增。
- Fix: Creation 与 Refinement 复用同一 typed partition；ReviseDraftInput 保留 Opportunity、grounding 与 context refs；unknown/cross-Research/empty factual projection 继续 fail fast。
- Regression: 最小 39 passed；定向 151 passed；backend 600 passed / 3 skipped；frontend 7/7、typecheck/build、diff、Alembic PASS；Migration=0、New Route=0。
- Status: `IMPLEMENTED / REGRESSION VERIFIED / REAL E2E NOT REACHED`。真实 retry 在进入 Workflow 前被 DEFECT-012 阻塞。

### DEFECT-012

- Classification: CONTEXT RESOLUTION / PLANNER REQUIRED INPUT / FUNCTIONAL（待独立 RCA）。
- Expected: Turn 103 使用 Workspace `draft_ref=2625` 启动 CONTENT_REFINEMENT_V1。
- Actual: 持久化 request payload 明确包含该 ref，但结果为 `CONTENT_REFINE / CLARIFY / draft_ref / WAITING_USER`，`run_ref=null`。
- Partial data: Refinement Run、Ledger、Revision、Persistence 均为 0；Root 2625 仍仅 V1 2082，body MD5 不变。
- RCA: Classification B；同一文本与 Workspace 下，Turn 96 输出 ACTIVE_DRAFT，Turn 103 `references=[]`，暴露 Resolver 对概率性 SemanticReference 的过强依赖。
- Fix: 仅在 required type 未解析且无冲突时，按 `explicit → workspace` 使用唯一 canonical 同类型 candidate；不访问 pending/active/recent/history。
- Regression: Resolver 39 passed；定向 127 passed；backend 611 passed / 3 skipped；frontend/typecheck/build/diff/Alembic PASS。
- Retry: Turn 110 / Run `wfr_d87115e85b3243d19986790c15a53848` / SUCCESS；Draft 2625 新建 V2 2087，parent=2082；V1 preserved。
- Status: `DEFECT-012 = FIXED / VERIFIED / FROZEN`；`DEFECT-011 = FIXED / VERIFIED / FROZEN`；`E2E-004 = PASS`。未执行 E2E-005。

### ENV-005 model-routing resolution / E2E-005 retry

- Routing: `LLM_CONTROL_SEMANTIC_MODEL=qwen3.8-flash`；仅 Control Semantic per-call 传入 `enable_thinking=false`，默认生成模型仍为 `qwen3.8-2.4t-a95b`。
- Controlled Semantic: 完整 E2E-005 contract 首轮 8124 ms SUCCESS，TaskSemanticFrame validation PASS，intent=RESEARCH，OBS 2097。
- ENV-005: `CONTROL_SEMANTIC_MODEL_LATENCY RESOLVED BY MODEL ROUTING`；历史 92.5 秒成功与偶发 APIConnectionError 证据保留。
- E2E retry: Turn 124 / request `phase27b-e2e005-turn1-fastqwen-20260924-02`；Control Semantic OBS 2098 首轮 6189 ms SUCCESS，但 Planner 返回 `FAILED / 多目标包含非 Workflow Intent`。
- Boundary: Run/Pending/checkpoint 均为空，未发 Turn 2，未登记 DEFECT-013，未执行 E2E-006。

## Execution Rule

### DEFECT-014 / ENV-006

- DEFECT-014 contract: Workflow primary 的 sub-goals 只允许 Workflow Intent；非法 mixed frame 在 Semantic post-parse business validation 阶段失败并 retry，Planner 保留 defensive validation。
- Regression: 定向 81 passed；backend 629 passed / 3 skipped；frontend 7 passed；typecheck/build/diff/Alembic PASS；Migration=0，New Route=0。
- Turn 128: request `phase27b-e2e005-defect014-turn1-20260924-01`；OBS 2104 SUCCESS 后，OBS 2105 对 `QUERY_PROFILE` 记录 `POST_PARSE_BUSINESS_VALIDATION`；OBS 2106 retry SUCCESS，Planner READY。
- Run: `wfr_801e92daac554ed9920927377da55997` / `RESEARCH_V1` 创建成功，证明 DEFECT-014 真实路径修复有效。
- New blocker: `collection_accounts=FAILED / XSEC_TOKEN_REQUIRED`；Run FAILED，checkpoint=3，Evidence Gate NOT_STARTED，Pending=null，Operation=0。
- Status: `DEFECT-014 = FIXED / VERIFIED / FROZEN`；`ENV-006 = XHS_PROVIDER_XSEC_TOKEN_REQUIRED / OPEN`；E2E-005 BLOCKED，未发 Turn 2，DEFECT-013 NOT REGISTERED。

After ENV-001 is removed, start from E2E-001. Record conversation ID, run/artifact refs, actual status, latency, warnings and errors before proceeding to dependent cases. A failed case must receive evidence and classification before any fix.
