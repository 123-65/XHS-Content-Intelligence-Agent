# Phase 2.7B DEFECT-021 Implementation（2026-09-27）

- 仅处理 DEFECT-021；DEFECT-022/023/024 与 Testing Track 未开始。
- Pinia 无现成 persistence package；新增最小 localStorage adapter，仅持久化用户明确选择的正整数 Account ID。
- Store bootstrap 同步恢复选择；Account 切换同步更新；非法值、账号列表不存在、detail API 403/404 均 fail safely 并清除选择，不自动切换其他 Account。
- localStorage 只恢复用户选择；所有 canonical API 仍携带 `account_ref`，backend ownership validation 仍是最终授权边界。
- Targeted + frontend tests 13/13 PASS；typecheck + production build PASS；Alembic=`d8e9f0a1b2c3 (head)`；Migration=0。
- 多个隔离 Edge/CDP 真实浏览器尝试均因环境 renderer/WebSocket reset 或 `Target crashed` 未取得完整 refresh/direct-navigation 证据；未安装 Selenium、EdgeDriver、Playwright 或新框架。
- `DEFECT-021 = IMPLEMENTED / REGRESSION VERIFIED / REAL BROWSER VERIFICATION PENDING`，尚未 FIXED/FROZEN。
- `E2E-012 = BLOCKED`；`Phase 2.7B = INCOMPLETE / BLOCKED BY E2E-012`。
- 报告：`docs/testing/PHASE_2_7B_DEFECT_021_REPORT.md`。

# Phase 2.7B E2E-012 Frontend Route / Lazy Load Acceptance（2026-09-27）

- Route-based UI、全部业务页面 lazy import、detail 按需读取、canonical Agent/API 边界与 Manual Publish exact `draft_version_id` 实现检查通过。
- Frontend tests 7/7、typecheck + production build PASS；主要页面均生成独立 route chunk；Alembic=`d8e9f0a1b2c3 (head)`；Migration=0。
- 真实 Edge 直达 `/agent/draft/2625` 已渲染 SPA/Draft shell，但因非持久化 `account_ref` 显示“请先选择账号”并停止读取；刷新/直达产品路径不成立。
- `DEFECT-021 = CONFIRMED / RCA COMPLETE / NOT FIXED`：详情路由依赖易失的内存账号上下文。
- `DEFECT-022 = CONFIRMED / RCA COMPLETE / NOT FIXED`：Publication 仅展示 Private Metrics，无 canonical write 产品入口。
- `DEFECT-023 = CONFIRMED / RCA COMPLETE / NOT FIXED`：Review/Candidate artifact card 将 artifact ID 错当 PublishedNote ID 路由。
- `DEFECT-024 = CONFIRMED / RCA COMPLETE / NOT FIXED`：产品 UI 尚不能形成 published V2 与 latest V4 的可用 canonical 区分。
- `E2E-012 = BLOCKED / FRONTEND PRODUCT ENTRY AND DIRECT-ROUTE DEFECTS`。
- `Phase 2.7B = INCOMPLETE / BLOCKED BY E2E-012`；E2E-011 保持 PASS/FROZEN；不进入 Testing Track。
- 报告：`docs/testing/PHASE_2_7B_E2E_012_FRONTEND_ROUTE_LAZY_ACCEPTANCE.md`。

# 当前阶段

Phase 2.7B REAL E2E ACCEPTANCE IN PROGRESS  
E2E-002 PASS / E2E-003 PASS / E2E-004 PASS  
Next: E2E-005 Pending Resume  
Phase 2.7A COMPLETE / FROZEN  
Product Read API Gap Closure COMPLETE / FROZEN  
Phase 2.6B COMPLETE / FROZEN  
Agent Frontend Integration — Route-based Lazy Architecture COMPLETE / FROZEN  
Phase 2.6A COMPLETE / FROZEN  
Unified Agent API COMPLETE / FROZEN  
Phase 2.5 Control Agent Integration COMPLETE / FROZEN  
Phase 2.5C Planner + AgentRuntime Integration FROZEN  
Phase 2.5B Context Resolver FROZEN  
Phase 2.5A Control Agent Semantic Layer FROZEN  
Phase 2.4 Runtime COMPLETE / FROZEN

## 当前系统

Tools: 17/17  
Workflows: 5/5  
Alembic: c7d8e9f0a1b2  
OpenAPI: 37 operations / 31 paths  
Tests: 615 passed, 3 skipped

Frontend: 7/7 architecture gates + production build passed  
Agent Routes: Chat + Research + Strategy + Draft + Publication + Run  
Bundle: all Agent views emitted as independent lazy chunks

## Phase 2.7B Acceptance 状态

- 业务主题：大学生/应届生考公考编内容研究
- 用户授权材料：3 条公开 Note URL + 2 条公开 Profile URL
- Backend / PostgreSQL / Frontend Health: PASS
- XHS Provider: `readonly_xhs`, available, `is_mock=false`
- LLM: `qwen/deepseek-v4-flash-0731`, `is_mock=false`; structured smoke PASS
- Acceptance Cases: 12 total / 5 PASS / 3 PARTIAL / 0 FAILED / 4 BLOCKED
- E2E-001 已完成：conversation 874 / run `wfr_e5945bf23a4048a1b0f7fc7f215fc1be` / research 2862 / PARTIAL_SUCCESS
- 报告：`docs/testing/REAL_E2E_ACCEPTANCE.md`
- 总结：`docs/testing/REAL_E2E_ACCEPTANCE_REPORT.md`

## Runtime 能力

- Durable Run / Cross-request Resume / AgentRuntime
- Transaction Boundary / Durable Operation Idempotency
- Execution Lease / Fencing / Explicit Orphan Recovery

## 保留边界

- Unified Turn client_request_id durable dedupe 已实现
- external provider exactly-once 不保证
- 无后台 orphan scanner

## Phase 2.5A 能力

- Turn -> TaskSemanticFrame
- 12 Intent / Multi-goal / Constraint Preservation
- Semantic Reference / Missing Info / Confidence
- Versioned Prompt / Structured Retry / Prompt Injection Boundary
- 只做语义理解，不规划、不执行 Workflow

## Phase 2.5B 能力

- Typed Resolver Input / Resolved Context
- Frozen Resolution Priority / Account Boundary
- Workspace / Pending / Active / Recent / History Context
- 1-based Ordinal Opportunity Resolution
- Temporal / Explicit Latest Published Note Resolution
- Unresolved / Ambiguous / Blocking Missing Info
- Canonical Read-only Identity Access / Safe Resolution Trace
- 不调用 LLM、Tool、Workflow、HTTP 或 AgentRuntime

## Phase 2.5C 能力

- Semantic + Resolved Context -> Deterministic ExecutionPlan
- Frozen Intent / Action / Skill / Workflow Registry Reuse
- Static Typed Workflow Input Builder Registry
- Blocking Gate / Plan Validation / Multi-goal DAG
- READY Plan -> AgentRuntime.start() Only
- WAITING_USER / FAILED Dependent-step Stop
- 非 Workflow Intent Runtime Calls = 0

## Phase 2.5D 能力

- Unified Agent Turn: Semantic -> Resolve -> Plan -> Action / Runtime
- Workflow WAITING_USER -> Same Run Cross-turn Resume
- Structured Recent Context / Active Pending Run Context
- Deterministic Clarification / Confirmation / Runtime Response
- Artifact Identity -> Recent Context Continuity
- Pending 中独立 Chat / Query / Cancel 不误 Resume

## Phase 2.6A 能力

- POST /api/agent/turns（唯一正式 Turn 入口）
- GET /api/agent/runs/{run_ref}（Account-bound public-safe read）
- Persistent Conversation / Turn Messages
- Durable client_request_id Replay / Payload Mismatch Rejection
- Strict Request Contract / Internal Control Fields Forbidden
- Pending Resume 继续通过同一个 Turn Endpoint

## Phase 2.6B 能力

- `/agent/chat/:conversationId?` 轻量 Agent Chat
- Research / Strategy / Draft / Publication / Run 独立详情路由
- 所有 Agent View 通过 Vue Router dynamic import 真实分块
- 用户自然语言仅调用 `POST /api/agent/turns`
- 稳定 `client_request_id` 网络重试与 Account Switch 隔离
- Chat 仅渲染消息、Pending、轻量 Artifact Card 和 Run Status
- Workspace Selection 仅保存类型化 Ref
- Detail GET 支持路由离开时 AbortController
- Production legacy Workflow API 调用 = 0

## Phase 2.7A 能力

- Typed Research / Strategy / Draft / Publication Detail Read API
- Canonical Repository Owner 复用，Product Read Service 只读投影
- 四类 Detail Account Boundary 校验
- Draft latest content + 轻量 version lineage + review summary
- Publication exact published version + public/private metrics + review/candidates
- Private Metrics 缺失时保持 `UNKNOWN`，不转换为 0
- Conversation Message ID keyset cursor pagination
- 100 条消息 40/40/20，无重复、无丢失、新消息插入后 cursor 稳定
- Detail Views 路由进入后独立 fetch / unmount abort
- `ARTIFACT_DETAIL_READ_API_GAP` CLOSED
- `CONVERSATION_PAGINATION_GAP` CLOSED

## Remaining Boundary

- Runtime 暂无正式 cancel capability；CANCEL_TASK 仅安全 handoff
- Confirmed Control Command Executor 尚未接入；更新请求停在 CONFIRMATION
- 未注入 Control Query Handler 时，QUERY 返回明确 capability gap

## 下一阶段

OBS-001 已完成：structured attempts 与 post-parse validation 写入最小脱敏 prompt evidence。Turn 69 真实复现确认 DEFECT-007 为 canonical Opportunity 3923 未进入 Service authorized evidence set 的合同缺口；最小修复只授权当前正式输入中的 canonical Opportunity。Turn 76 / Run `wfr_2193edf65ec14dcfba2f224df3642406` 最终只读验收确认 Strategy 13、Opportunity 3956、Research 2862、Ledger 与 Product Read 一致，且无 Research rerun / XHS recollection。`DEFECT-007 = FIXED / VERIFIED`，`E2E-002 = PASS`。  
E2E-003 首次真实执行在 Workspace Selection 阶段失败：Turn 77 / client request `phase27b-e2e003-20260923-01`；该历史失败记录保持不变。DEFECT-008 已用显式 Opportunity ownership resolver 最小修复，定向与完整回归全部 PASS；Turn 84 真实验证成功越过 Workspace ownership 并进入 CONTENT_CREATE，因此 `DEFECT-008 = FIXED / VERIFIED`。  
Turn 84 的 `UNKNOWN / 这个` 在旧 Resolver 中未进入 Workspace candidate enumeration。最小修复以 Intent expected type 限定有限 deictic reference，并保持 explicit > workspace > pending > active > recent > history 与 canonical ownership。定向 82 passed、完整 backend 598 passed / 3 skipped、frontend/typecheck/build/Alembic 全部 PASS。  
Turn 91 真实验证获得 CONTENT_CREATE / EXECUTE_PLAN 并启动 CONTENT_CREATION_V1，Strategy 13 / Opportunity 3956 / Research 2862 lineage 正确，因此 `DEFECT-009 = FIXED / VERIFIED`。Run `wfr_02c20c262f3c40a68e1fc94705b1741b` 随后在 evidence_retrieval 失败：`Opportunity Evidence 类型不可检索: content_opportunity`；该历史失败及无 Draft/Version/Ledger 事实保持不变。  
DEFECT-010 frozen RCA 为 Classification B：`content_opportunity:3923` 是 lineage/grounding，不是 retrievable evidence。最小修复在 Research Query projection 与 CONTENT_CREATION_V1 assembly 显式 partition；定向 122 passed，完整 backend 600 passed / 3 skipped，frontend/typecheck/build/Alembic 全部 PASS。Turn 95 / Run `wfr_466d50889d364b74a098013a0256a4a0` 真实验证 SUCCESS，retrieval 仅含 ACCOUNT 2914 与 NOTE 10998/10999/11000；Draft 2625 / Version 2082 V1 / Review PASS。`DEFECT-010 = FIXED / VERIFIED / FROZEN`，`E2E-003 = PASS`。  
E2E-004 Turn 96 使用正式 Workspace `draft_ref=2625` 与自然语言修改要求，真实获得 CONTENT_REFINE / EXECUTE_PLAN 并启动 Run `wfr_c469888935bb4419936ecc4675d3ab32`。Draft resolution 精确读取 Root 2625 / V1 2082，Opportunity 3956 / Strategy 13 / Research 2862 lineage 正确；但 CONTENT_REFINEMENT_V1 仍使用旧 Evidence assembly，在 `evidence_retrieval` 对合法 grounding ref `content_opportunity:3923` 报不可检索。Revision/Persistence 未开始，V1 未变，无 V2/Ledger。已登记 `DEFECT-011 = OPEN / RCA EVIDENCE CAPTURED / NOT FIXED`，`E2E-004 = FAILED / BLOCKED BY DEFECT-011`。  
DEFECT-011 已把 Creation 的 typed Evidence partition 提取为共享实现并接入 Refinement；typed revision input 同时保留 Opportunity、grounding 与 context refs。最小检查 39 passed、定向 151 passed、完整 backend 600 passed / 3 skipped、frontend/typecheck/build/diff/Alembic 全部 PASS，Migration=0、New Route=0。  
Turn 103 使用新 request `phase27b-e2e004-defect011-retry-20260924-01` 重试，但虽持久化 request payload 明确包含 `workspace_selection.draft_ref=2625`，仍返回 `CONTENT_REFINE / CLARIFY / draft_ref`，未创建 Run。已登记 `DEFECT-012 = OPEN / EVIDENCE CAPTURED / NOT FIXED`。Root 2625 仍仅 V1 2082，body MD5 不变，无 V2/Ledger。`DEFECT-011 = IMPLEMENTED / REGRESSION VERIFIED / REAL E2E NOT REACHED`；`E2E-004 = FAILED / BLOCKED BY DEFECT-012`。  
DEFECT-012 frozen RCA 为 Classification B：Semantic nondeterminism 暴露 Resolver 对显式 SemanticReference 的过强依赖。最小修复只在无冲突时按既有 Intent expected type 使用唯一 canonical explicit/workspace candidate；显式错误、多候选、跨账号和错误类型继续阻断。Resolver 39 passed、定向 127 passed、完整 backend 611 passed / 3 skipped、frontend/typecheck/build/diff/Alembic 全部 PASS。  
Turn 110 / Run `wfr_d87115e85b3243d19986790c15a53848` 真实 SUCCESS：CONTENT_REFINE / EXECUTE_PLAN；Root 2625 追加 V2 2087，version=2、parent=2082、USER_REVISION；V1 hash 不变；Evidence Retrieval 只含 ACCOUNT/NOTE/COMMENT，Source Opportunity 3923 保留为 grounding；Ledger 仅一条成功 persistence；Product Read latest=V2。`DEFECT-012 = FIXED / VERIFIED / FROZEN`，`DEFECT-011 = FIXED / VERIFIED / FROZEN`，`E2E-004 = PASS`。  
E2E-005 首次正式尝试使用 Account 8456 / Conversation 874 / Turn 111 / request `phase27b-e2e005-turn1-20260924-01`，只提交授权 Profile URL，以真实触发 `RESEARCH_V1` evidence gate 的 `WAITING_USER`。Provider preflight 为 real/available，但 Control Semantic structured call 在 196209 ms 后超时；Run=0、Pending=null、checkpoint 不存在，未进入 Resume 产品路径。登记 `ENV-003 = OPEN`，`E2E-005 = BLOCKED BY ENV-003`；未登记 DEFECT-013，未发 Turn 2，未执行 E2E-006。  
ENV-003 最小预检确认容器与 `.env` 无 drift：`qwen / deepseek-v4-flash-0731`、相同 base URL host、`is_mock=false`。一次 canonical structured smoke 首轮成功（PromptRunLog 2071，7697 ms，attempt 1/2）。随后唯一 Turn 1 Retry 为 Turn 112 / request `phase27b-e2e005-turn1-retry-20260924-01`，Control Semantic 两次真实 Provider attempt 均 timeout（PromptRunLog 2072/2073，85138/101475 ms），Turn 总耗时 187637 ms；Run=0、Pending=null、checkpoint 不存在、Operation 仍为 186。`ENV-003 = REPRODUCED`，`E2E-005 = BLOCKED BY ENV-003`；未登记 DEFECT-013，未发 Turn 2，未执行 E2E-006。  
下一步：停止重复 Provider 调用；等待 real LLM 服务稳定或外部环境状态变化后，再另行授权重试 E2E-005。  
本轮再次获得明确授权后，canonical structured smoke 首轮成功（PromptRunLog 2074，2925 ms，attempt 1/2，`is_mock=false`）；唯一 Turn 1 Retry 为 Turn 113 / request `phase27b-e2e005-turn1-retry2-20260924-01`。Control Semantic 两次 Provider attempt 再次 timeout（PromptRunLog 2075/2076，99376/101097 ms），Turn 总耗时 201487 ms；Run=0、Pending=null、checkpoint 不存在、Operation 仍为 186、Research Artifact 仍为 2888。`ENV-003 = REPRODUCED`，`E2E-005 = BLOCKED BY ENV-003`；未登记 DEFECT-013，未发 Turn 2，未执行 E2E-006。  
Provider model 随后由旧 `deepseek-v4-flash-0731` 切换为 `qwen3.8-2.4t-a95b`；运行容器与 `.env` 一致，provider=`qwen`、`is_mock=false`。Qwen canonical structured smoke 首轮成功（PromptRunLog 2077，5661 ms）。唯一 E2E Turn 1 为 Turn 114 / request `phase27b-e2e005-turn1-qwen-20260924-01`，但 Control Semantic 两次 Qwen attempt 均 timeout（PromptRunLog 2078/2079，102319/102079 ms），Turn 总耗时 205466 ms；Run=0、Pending=null、checkpoint 不存在、Operation 仍为 186、Research Artifact 仍为 2888。ENV-003 保留为旧 DeepSeek-model 历史证据；本次独立登记 `ENV-004 = QWEN_PROVIDER_TIMEOUT / OPEN`，`E2E-005 = BLOCKED BY ENV-004`；`DEFECT-013 = NOT REGISTERED`，未发 Turn 2，未执行 E2E-006。  
ENV-004 RCA 完成：Smoke 与 Semantic 请求参数相同，均使用 `response_format=json_object`，且均未显式设置 max tokens、temperature、top_p、thinking、stream 或 extra_body；差异仅为 prompt/schema workload（Smoke 1 property/168 schema chars，TaskSemanticFrame 13 properties/3990 schema chars）。运行 client `timeout=30`、OpenAI SDK `max_retries=2`，而 adapter 外层又有 2 attempts；因此每条 OBS attempt 实含最多 3 次 SDK HTTP 尝试，2078/2079 各约 102 秒与 `3×30s + backoff` 一致。First divergence 是完整 Semantic workload 未在单次 30 秒窗口内返回。RCA=`D. Client/provider timeout configuration interaction`；建议后续让 adapter 只保留一个 retry owner（优先 SDK `max_retries=0`、保留外层 evidence），本轮未修改。E2E-005 仍不可继续。  
ENV-004 最小修复已完成：OpenAI-compatible SDK client 显式 `max_retries=0`，timeout 仍为 30 秒，adapter attempts 仍为 2。新增 retry ownership 回归后定向 44 passed；完整 backend 615 passed / 3 skipped / 18 warnings；frontend 7/7、typecheck、production build、diff check、Alembic current/head 全部 PASS；Migration=0、New Route=0。运行时确认 sdk_max_retries=0。唯一真实 controlled Semantic 调用使用 E2E-005 相同 TaskSemanticFrame/Prompt/Qwen contract，但未在单次 30 秒窗口内返回，宿主观察边界结束且无成功结果；未重发。`ENV-004 = RESOLVED / REGRESSION VERIFIED`，新增 `ENV-005 = CONTROL_SEMANTIC_SINGLE_REQUEST_TIMEOUT / OPEN`，`E2E-005 = BLOCKED BY ENV-005`；未执行 E2E-005，`DEFECT-013 = NOT REGISTERED`。  
ENV-005 唯一隔离诊断使用相同 Qwen model、TaskSemanticFrame、Semantic prompt、response_format，仅局部 timeout=120 秒、SDK max_retries=0，并直接发一次 HTTP 请求，不走 adapter retry、不写业务数据。调用从 `2026-09-24T06:00:03.724013Z` 至 `06:01:56.667843Z`，112951 ms 后返回明确 `APIConnectionError: Connection error.`；不是 120 秒 timeout，且 structured validation 未开始。RCA 分类=`C. Provider/transport connection error`；无法证明把 timeout 提高到 120 秒即可成功，也无法据此判定 Schema 不兼容。`ENV-005 = RCA COMPLETE / PROVIDER_CONNECTION_ERROR / OPEN`，E2E-005 继续阻塞，未执行 E2E-005/E2E-006，`DEFECT-013 = NOT REGISTERED`。  
ENV-005 Transport Isolation：SDK 源码确认 APIConnectionError 通过 cause chain 保留底层异常，但既有 evidence 只保存 outer error，第一次诊断的 inner cause 已丢失。容器/宿主无 proxy env，WinHTTP direct；DNS 23 ms、TLS 1.3 三次 435–457 ms、HTTPS `/models` 200/821 ms，基础链路正常。httpx timeout=connect/read/write/pool 各 30 秒；HTTP/1.1、pool 1000、keepalive 100/5s；隔离调用使用新 client。唯一允许的完整 transport diagnostic 使用 timeout=120、retry=0、HTTP=1，于 `2026-09-24T06:08:47.713202Z` 开始，92482 ms 后 SUCCESS；TaskSemanticFrame validation PASS，intent=RESEARCH/confidence=.92。上一次 112951 ms APIConnectionError 未复现且无 inner cause，无法直接区分 local network、pool、gateway、provider close 或 TLS/protocol。最终分类=`F. Evidence still insufficient`；`ENV-005 = TRANSPORT RCA INCOMPLETE / INTERMITTENT / OPEN`，E2E-005 仍阻塞，未执行 E2E-005/E2E-006。  
Control Semantic 最小模型路由已完成：默认 `LLM_MODEL=qwen3.8-2.4t-a95b` 不变，仅 TaskSemanticFrame 使用 `LLM_CONTROL_SEMANTIC_MODEL=qwen3.8-flash` 和 per-call `enable_thinking=false`；timeout=30、SDK retry=0、adapter policy 不变。定向 44 passed，完整 backend 620 passed / 3 skipped。真实 Controlled Semantic 首轮 8124 ms SUCCESS，validation PASS，intent=RESEARCH；OBS 2097 正确记录 flash model。`ENV-005 = CONTROL_SEMANTIC_MODEL_LATENCY RESOLVED BY MODEL ROUTING`。随后 E2E-005 Turn 1 使用新 request `phase27b-e2e005-turn1-fastqwen-20260924-02` 创建 Turn 124；OBS 2098 首轮 6189 ms SUCCESS，但 Planner 因“多目标包含非 Workflow Intent”返回 FAILED，Run/Pending/checkpoint 均未创建，未发 Turn 2。E2E-005 尚未进入 Pending/Resume，保持 BLOCKED；`DEFECT-013 = NOT REGISTERED`，未执行 E2E-006。  
DEFECT-014 已冻结并修复：Workflow primary 的 `sub_goals` 只允许 Workflow Intent；Semantic post-parse business validation 拒绝 mixed goal、记录 OBS 并复用现有 retry，重复目标确定性去重，Planner fail-closed 防线保留。定向 81 passed；完整 backend 629 passed / 3 skipped，frontend 7/7、typecheck/build、diff/Alembic PASS。Turn 128 首轮 OBS 2104 再次产生 `RESEARCH + QUERY_PROFILE`，OBS 2105 正确记录 `POST_PARSE_BUSINESS_VALIDATION` 并 retry；OBS 2106 第二轮得到合法 RESEARCH，Planner READY，创建 Run `wfr_801e92daac554ed9920927377da55997`。`DEFECT-014 = FIXED / REGRESSION VERIFIED / REAL PATH VERIFIED / FROZEN`。Run 随后在 `collection_accounts` 因 `XSEC_TOKEN_REQUIRED` FAILED，checkpoint=3，Evidence Gate 未开始，Pending=null；登记 `ENV-006 = XHS_PROVIDER_XSEC_TOKEN_REQUIRED / OPEN`，E2E-005 被 ENV-006 阻塞，未发 Turn 2，`DEFECT-013 = NOT REGISTERED`。  
ENV-007 Service Recovery 与 Health RCA：历史验收文档与本地二进制帮助共同确认 `xpzouying/xiaohongshu-mcp v2.4.0` Windows executable 使用默认 `:18060` 启动。宿主 `/mcp`、`tools/list` 与 backend 连通均正常；登录程序生成的会话位于项目根目录，因此 MCP 必须同样以项目根目录为工作目录启动。此前 canonical `check_login_status` 的 `context deadline exceeded` 发生在 MCP handler → `XiaohongshuService.CheckLoginStatus` → bundled browser/page → `LoginAction.CheckLoginStatus` 内部，不是 backend/httpx timeout。受控复核中 bundled Chrome 148 与 `leakless.exe` 均成功启动，MCP 进程保持存活；第一次 24589 ms 返回 HTTP 200 / `isError=false`，第二次 canonical Provider 在 19944 ms 返回 `SUCCESS / is_logged_in=true / is_mock=false`。RCA 分类为 `F. Login-state page/navigation timeout`（具体 navigation 与 selector 子步骤因 v2.4.0 日志粒度不足无法再细分），在正确工作目录重启并完成 browser 冷启动后恢复。未调用 `user_profile`、未执行 E2E-005。`ENV-007 = PROVIDER HEALTH RESTORED / E2E VERIFICATION REQUIRED`，`E2E-005 = READY FOR SEPARATELY AUTHORIZED EXECUTION`，`DEFECT-013 = NOT REGISTERED`。  
E2E-005 真实 Pending/Resume：Turn 144 / request `phase27b-e2e005-turn1-providerrestored-20260924-01` 仅提交授权 Profile，177361 ms 后创建 `RESEARCH_V1` Run `wfr_2cbfe18c78734ff69be3e391360f1876`；`collection_accounts=SUCCESS`，账号证据 2914 为 `xiaohongshu_mcp / XHS_MCP / is_mock=false`，Evidence Gate 因缺 Note Evidence 进入真正 Workflow `WAITING_USER`，durable checkpoint=3、Conversation active pending 与 `RESEARCH_V1_RESUME` 均持久化。因此 `ENV-007 = RESOLVED / REAL PROVIDER WORKLOAD VERIFIED`。Turn 145 / 新 request `phase27b-e2e005-turn2-resume-20260924-01` 是只补 3 条授权 Note URL 的独立 HTTP Turn；命中同一 Run，checkpoint 3→5，`growth_context` 与 `collection_accounts` 均为 `SKIPPED`，Operation 0→0、Research Artifact 与 Account Evidence 数量不变，Pending 已从 Run 与 Conversation 清空。但 Resume 在 Provider 调用前构造 `CollectXhsNotesInput` 失败：正式请求的 3 条 Note URL 全部结构合法，而 durable Resume input 有 6 条，前 3 条为 Semantic Frame 生成的无 scheme/host/token 值，后 3 条才是当前 Turn 的可信材料；`build_resume_input` 直接采用 `frame.note_urls`，触发 Pydantic `note_urls 只能包含公开小红书 Note URL` 并令 Run `FAILED / WORKFLOW_RESUME_EXECUTION_ERROR`。登记 `DEFECT-013 = OPEN / REAL PENDING-RESUME PATH REPRODUCED / CURRENT-TURN NOTE MATERIAL AUTHORITY GAP`；`E2E-005 = FAILED / BLOCKED BY DEFECT-013`。未重试、未修改代码、未执行 E2E-006 或 Testing Track。  
DEFECT-013 最小修复完成：Orchestrator 仅从同 Account、`USER_PROVIDED CollectionAccessScope`、且确属当前 Turn 的 URL 构造 authoritative Note set；该 set 非空时覆盖 Semantic Note values，否则保留 Semantic 旧行为。Profile authority 未变；Runtime、Checkpoint、Ledger、Provider、Resolver、Planner、Workflow、Route、DB Schema、LLM 均未改。定向 103 passed；backend 644 passed / 3 skipped / 18 warnings；frontend 7/7；typecheck、container production build、diff check、Alembic current=head=`c7d8e9f0a1b2` PASS；Migration=0，New Route=0。新 Turn 150 创建 Run `wfr_ea16dbf2dbbc4400af91b5c14f7036e5`，WAITING_USER/checkpoint=3/Pending required=`note_urls,evidence_refs`。新 Turn 151 只提交 3 条 Note，同 Run checkpoint 3→5，execution_mode=RESUME；`growth_context`/`collection_accounts=SKIPPED`，`collection_notes=SUCCESS`，processed URLs 精确等于 3 条授权材料，refs=10998/10999/11000，无 Semantic 扩展。Operation 0→0、global operation 228→228、Research Artifact 2902→2902、Account/Note Evidence 2989/11126 不变；Pending consumed/cleared。随后独立失败在 `analysis`：OBS 2130/2131 为 `competitor_semantic_analysis / qwen3.8-2.4t-a95b / is_mock=false / PROVIDER_FAILED`，30872/30767 ms timeout，第二次 retry exhausted。登记 `ENV-008 = COMPETITOR_ANALYSIS_PROVIDER_TIMEOUT / RCA COMPLETE / OPEN`，不混入 DEFECT-013。`DEFECT-013 = FIXED / REGRESSION VERIFIED / REAL MATERIAL AUTHORITY PATH VERIFIED`，但因 Workflow 未最终完成而不标 FROZEN；`E2E-005 = FAILED / BLOCKED BY ENV-008`；不进入 E2E-006/Testing Track。面试资产：新增 0，更新 1。  
ENV-008 只读 RCA 完成：真实路径是 `ResearchWorkflow._run -> AnalyzeResearchTool -> LLMStructuredCompetitorAnalyzer -> LLMClient -> QwenProvider/OpenAICompatibleProvider`，未经 `CompetitorReportService`，也未使用 Rule baseline。OBS 2130/2131 确认 provider=`qwen`、model=`qwen3.8-2.4t-a95b`、is_mock=false；analysis 无 per-call model override，无 `extra_body`，因此未显式设置 `enable_thinking`。SDK `max_retries=0`；Adapter/Tenacity 恰好 2 logical attempts，Workflow 该 Tool 调用 `retry=False`，无 nested retry。timeout 来自 `LLM_TIMEOUT_SECONDS=30` 并直接配置到 OpenAI SDK/httpx request，不是 Workflow deadline。当前 evidence=3 Note+1 Account+0 Comment+0 OCR，无重复，evidence 约 4052 chars/7830 bytes，Schema 约 10609 chars，System Prompt 340 chars，整体 structured request 约 15K chars，10 个顶层输出 section。历史默认强模型 Control diagnostic 约 92482 ms 成功，flash 约 8124 ms；本次两次 30872/30767 ms 与 30s request deadline 精确对齐。不需要新 diagnostic。Primary RCA=`A. DEFAULT MODEL LATENCY INCOMPATIBLE WITH 30S TIMEOUT`；secondary=`C. STRUCTURED OUTPUT COMPLEXITY`。`ENV-008 = DEFAULT STRONG MODEL LATENCY INCOMPATIBLE WITH SHARED 30S REQUEST TIMEOUT / RCA COMPLETE / OPEN`；不登记新 Product Defect；`E2E-005 = BLOCKED BY ENV-008`。Pending consumed/cleared 仅记 observation。本轮未调 Provider、未执行 E2E/Full Regression、未修改产品代码。当前冻结状态以最新合同为准：`DEFECT-013 = FIXED / REGRESSION VERIFIED / REAL RESUME MATERIAL PATH VERIFIED / FROZEN`。面试资产：新增 0，更新 1。  
ENV-008 Timeout Budget 最小修复已实施：全局 `LLM_TIMEOUT_SECONDS=30` 不变，新增 `LLM_RESEARCH_ANALYSIS_TIMEOUT_SECONDS=120`，通过最小可选 `timeout_seconds` 参数只在 `LLMStructuredCompetitorAnalyzer.analyze` 透传到单次 OpenAI-compatible request。定向 65 passed；Backend 646 passed / 3 skipped / 18 warnings；Frontend 7/7、typecheck、container build、diff check、Alembic current=head=`c7d8e9f0a1b2` 全部 PASS；Migration=0，New Route=0。backend recreate 后运行时确认 qwen / default `qwen3.8-2.4t-a95b` / Control `qwen3.8-flash` / default timeout 30 / Research timeout 120 / SDK retries 0 / Adapter attempts 2 / is_mock=false。新 Turn 155 创建 Run `wfr_14dee8edbef24079a30e5420cbfb451d`，WAITING_USER/checkpoint=3/durable Pending。Turn 156 仅补 3 条 Note，same Run/checkpoint 3→5/execution_mode=RESUME；collection_accounts=SKIPPED，collection_notes=SUCCESS，URLs 精确等于 authoritative materials，refs 10998/10999/11000 均为 XHS_MCP/is_mock=false。Analysis 仍失败：OBS 2139 attempt 1/2 为 104711 ms `Connection error`；OBS 2140 attempt 2/2 为 120745 ms `Request timed out`/retry exhausted，证明 120s override 生效但未完成 structured validation。Artifact creation NOT_STARTED，Research Artifact 未创建。Run Operation 0→0、global Operation 234→234、Research Artifact 2904→2904、Account/Note Evidence 2993/11133 均不变。按停止合同未提高到 300s、未重试。`ENV-008 = TASK-SPECIFIC 120S BUDGET IMPLEMENTED / REGRESSION VERIFIED / REAL ANALYSIS STILL FAILED / OPEN`；`DEFECT-013 = FIXED / REGRESSION VERIFIED / REAL RESUME MATERIAL PATH VERIFIED / FROZEN`；`E2E-005 = FAILED / BLOCKED BY ENV-008`；未进入 E2E-006/Testing Track。下一步需单独决策 per-task model routing 或 Prompt/Schema optimization。面试资产：新增 0，更新 1。  
ENV-008 Research Analysis Model Routing Diagnostic 完成：从 Run `wfr_14dee8edbef24079a30e5420cbfb451d` durable state 只读恢复同一 `CompetitorEvidence`（3 Note refs 10998/10999/11000，1 Account ref 2914，0 Comment，0 OCR），复用同一 `LLMStructuredCompetitorAnalyzer`、`CompetitorSemanticResult`、`competitor_semantic_analysis/v1`、System Prompt、Schema 和 `CompetitorGroundingValidator`；唯一变量是 model=`qwen3.8-flash`。SDK retries=0，Adapter attempts=1，timeout=120，`enable_thinking` 未显式设置。唯一真实调用在 121279 ms 结束，provider result=`PROVIDER_FAILED / LLM_PROVIDER_UNAVAILABLE`，attempt latency=121276 ms/retry exhausted；无可用 structured payload，JSON parse、Pydantic validation、10 个顶层 section 完整性与 grounding validation 均未到达。Strong baseline 为 104711 ms Connection error + 120745 ms timeout；Flash 未展示在 Control Semantic 节点上的 latency 优势，两者均未在当前 Analysis 合同下产生可验证结果。决策：不建议将 Research Analysis 路由到 flash，不调用第二未知模型，不修改 production routing；下一步转 Prompt/Schema optimization RCA。`ENV-008 = STRONG AND FLASH MODELS FAILED CURRENT RESEARCH ANALYSIS CONTRACT WITHIN 120S / MODEL ROUTING DIAGNOSTIC COMPLETE / OPEN`；`E2E-005 = BLOCKED BY ENV-008`，本轮未执行 E2E。业务副作用核验：Run/checkpoint/Pending 不变，PromptRunLog max id 仍为 2140，Operation 234、Research Artifact 2904、Opportunity 4027、Account/Note Evidence 2993/11133 不变。面试资产：新增 0，更新 1。  
ENV-008 Research Analysis Thinking-Mode Diagnostic 完成：从同一 Run 只读恢复同一 3 Note+1 Account+0 Comment+0 OCR `CompetitorEvidence`，复用同一 `LLMStructuredCompetitorAnalyzer`、`competitor_semantic_analysis/v1`、`CompetitorSemanticResult`、System Prompt、Schema 和 `CompetitorGroundingValidator`；model 仍为 `qwen3.8-flash`，timeout=120，SDK retries=0，Adapter attempts=1，唯一变量是显式 `extra_body={"enable_thinking": false}`。唯一真实调用 20575 ms SUCCESS（attempt=20571 ms），JSON structured parse、Pydantic `CompetitorSemanticResult`、10 个顶层 section 和 deterministic grounding validation 全部 PASS。对比上轮 Flash 未显式 thinking 的 121279 ms Provider failure，thinking policy 是已隔离的关键运行变量；不应先进入 Prompt/Schema 优化。建议下一步另行授权实施 Research-only `LLM_RESEARCH_ANALYSIS_MODEL=qwen3.8-flash` + `enable_thinking=false`，保持 Control Semantic 不变，本轮未修改 production routing。`ENV-008 = THINKING-MODE RCA COMPLETE / FLASH NON-THINKING PATH VERIFIED / PRODUCTION ROUTING NOT YET IMPLEMENTED / OPEN`；`E2E-005 = BLOCKED BY ENV-008`，本轮未执行 E2E。副作用核验：Run 仍 FAILED/checkpoint=5/RESUME，Pending 不变，PromptRunLog max id=2140，Operation 234、Research Artifact 2904、Opportunity 4027、Account/Note Evidence 2993/11133 不变。面试资产：新增 0，更新 1。  
ENV-008 Research Analysis production execution policy 已落地并完成 E2E-005：新增 canonical `LLM_RESEARCH_ANALYSIS_MODEL=qwen3.8-flash` / timeout=120 / `LLM_RESEARCH_ANALYSIS_ENABLE_THINKING=false`，Analyzer 仅复用现有 model/timeout/extra_body 能力；默认强模型、Control Semantic Flash+thinking=false+30s、SDK retry=0 与 Adapter retry owner 不变。定向 49 passed，Backend 646 passed/3 skipped/18 warnings，Frontend 7/7、typecheck、container build、diff check、Alembic current=head=`c7d8e9f0a1b2` 全部 PASS，Migration=0/New Route=0。重建后运行时配置与冻结合同一致。前两个 pre-run Turn 160/161 均在 Workflow 前停止（PowerShell 中文编码、English 措辞 Planner 误读）且未创建 Run；使用已验证中文文本与显式 UTF-8 的正式 Turn 162/request `phase27b-e2e005-researchpolicy-turn1-20260925-03` 新建 Run `wfr_0528728e8503405dad7b1fe0c7c30b39`，checkpoint=3/WAITING_USER/Account ref 2914；Turn 163/request `phase27b-e2e005-researchpolicy-turn2-20260925-01` 仅提交 3 条 Note materials，未传 run_ref，same Run checkpoint 3→5/RESUME，growth_context+collection_accounts=SKIPPED，collection_notes=SUCCESS，URL 精确相等，refs=10998/10999/11000。OBS 2150 为 qwen/`qwen3.8-flash`/is_mock=false/attempt 1/2/27274 ms SUCCESS，`CompetitorSemanticResult` parse/Pydantic 与 grounding PASS；analysis+artifact_creation=SUCCESS，创建 Research Artifact 2949，Run 以可接受的 `PARTIAL_SUCCESS` 终态完成（OCR 未配置、Comment partial warnings）。Run API/State/Result 与 Conversation Pending 全部清空；数据库聚合列为 JSON null 而非残留 Pending object。基线→最终：Run 2448→2449、Operation 240→241、Research 2906→2907、Opportunity 4032→4034（bundle 预期 2 条），Account/Note Evidence 2997/11140 不变，无重复。`ENV-008 = RESOLVED / REAL ANALYSIS WORKLOAD VERIFIED / FROZEN`；`E2E-005 = PASS / REAL PENDING-RESUME-ANALYSIS-ARTIFACT PATH VERIFIED / FROZEN`；`DEFECT-013 = FIXED / REGRESSION VERIFIED / REAL RESUME VERIFIED / FROZEN` 保持。未执行 E2E-006/Testing Track。面试资产：新增 0，更新 1。  
E2E-006 Request Idempotency 真实验收通过：从 Turn 163 持久化 `request_payload` 原样恢复 Account 8456 / Conversation 874 / client_request_id `phase27b-e2e005-researchpolicy-turn2-20260925-01` / 3 Note materials，未打印正文或 xsec token。Replay 前 Turn 总数=163、key 对应唯一 Turn 163/COMPLETED，Run 总数=2449，目标 Run `wfr_0528728e8503405dad7b1fe0c7c30b39` 为 PARTIAL_SUCCESS/checkpoint=5/RESUME，PromptRunLog count/max=2150/2150，MCP calls count/max=827/827，Operation=241，Account/Note Evidence=2997/11140，Research=2907，Opportunity=4034。正式 `POST /api/agent/turns` Exact Replay 返回 HTTP 200、turn_id=163、same run/checkpoint/status；之后所有计数与 max ID 完全不变，证明无第二 Turn/Run、无 Control/Analysis LLM replay、无 XHS Provider replay、无 Operation/Evidence/Artifact/Opportunity 重复。随后保持同 key/materials 仅修改安全 message，正式 HTTP 返回 409 / `REQUEST_IDENTITY_MISMATCH` / `client_request_id 已用于不同请求。`，计数仍全部不变。无 Product Defect。`E2E-006 = PASS / DURABLE REQUEST IDEMPOTENCY VERIFIED / FROZEN`。下一项 E2E-007 Account Boundary；未开始 Testing Track。面试资产：新增 0，更新 1。  
E2E-007 Conversation Account Boundary 真实验收通过：基线 Conversation 874 owner=Account 8456，active Pending 全空，最新有效 Turn 163 / Run `wfr_0528728e8503405dad7b1fe0c7c30b39`。只读选择现存 Account B=1，正式 `POST /api/agent/turns` 使用 Conversation 874、新 key `phase27b-e2e007-cross-account-20260925-01`、无 URL/material/Artifact/run/Pending token 的安全文本，返回 HTTP 403 / `CONVERSATION_ACCOUNT_MISMATCH` / `Conversation 不属于当前 Account。`。拒绝后 Turn count/max=163/163 且 Account B key row=0，Run=2449/2502，PromptRunLog=2150/2150，MCP=827/827，Operation=241/241，Research=2907/2949，Account/Note Evidence=2997/2997 与 11140/11140，Opportunity=4034/4118，全部不变；Conversation owner/Pending/recent state 也未污染，证明 boundary 在 Turn reserve 与 Agent execution 前生效。正确 owner 正向控制用 Account 8456 / Conversation 874 / `Hello.` 创建 Turn 164，返回 `GENERAL_CHAT / RESPOND / SUCCESS`，无 run/Pending/Artifact；仅新增预期 Control Semantic OBS 2151（3498 ms），Run/MCP/业务对象不变。无 Product Defect。`E2E-007 = PASS / CONVERSATION ACCOUNT BOUNDARY VERIFIED / FROZEN`。下一项 E2E-008 Manual Publish Exact Draft Version；未开始 Testing Track。面试资产：新增 0，更新 1。  
E2E-008 Manual Publish Exact Draft Version 真实验收在正式请求前发现产品合同缺口并停止。运行时 OpenAPI 共 31 条 path，publish/draft/note 相关仅有只读 `/api/artifacts/draft/{ref}`；Legacy `/publish-packages` / `/published-notes` 已按当前产品边界取消注册，Unified Agent 也无 Manual Publish intent/workflow/write tool，因此不存在 canonical HTTP 写入入口。只读基线确认 Draft root 2625 owner=8456/current V2；Version 2082=V1/parent null/GENERATED/hash `8bec704aff0df1b3dbcb354da6864193`，Version 2087=V2/parent 2082/USER_REVISION/hash `6af2133da2be6c46a7af710e4f0672d9`，均存在且无 PublishPackage/PublishedNote 绑定；意向 Version X 冻结为 2087。保留的内部 `PublishPackageInput` 只接受 `draft_ref`，`PublishedNoteBindingInput` 只接受 `package_ref`，都不接受 `draft_version_id`；Package 从可变 Draft root 复制内容并用 root.version 生成 JSON string，Binding 再次从 root.version 重算，`PublishedNote` 无 DraftVersion FK，不满足 exact immutable version contract。未绕过 HTTP 调内部 service、未声称任何真实外部发布、未调 XHS/LLM。RCA 前后 PublishedNote=590/590、PublishPackage=510/510、Draft=2631/2651、DraftVersion=2096/2096、Operation=241/241、PromptRunLog=2151/2151、MCP=827/827、Research=2907/2949，Version hashes/parent 不变。登记 `DEFECT-016 = OPEN / RCA CONFIRMED / NOT FIXED`；`E2E-008 = BLOCKED BY DEFECT-016 / EXACT DRAFT VERSION CONTRACT UNAVAILABLE`。不执行 E2E-009/Testing Track。面试资产：无新增或更新，待修复后真实验收再更新。  
Phase 2.7B 真实完成后才进入 Testing Track T1。

## Phase 2.7B E2E-008 冻结

- `DEFECT-016 = FIXED / REGRESSION VERIFIED / REAL EXACT-VERSION PATH VERIFIED / FROZEN`
- `E2E-008 = PASS / USER-SELECTED V2 EXACT LINEAGE VERIFIED / FROZEN`
- Draft 2625 显式选择 V2 / `draft_version_id=2087`。
- PublishPackage 511 与 PublishedNote 592 均绑定 `draft_id=2625 / draft_version_id=2087 / version_number=2`。
- Package title/body/tags 与 V2 snapshot 逐字段一致，`auto_publish=false`。
- Draft 2625 仍只有 V1(2082) 与 V2(2087)，未创建 V3/V4。
- `E2E-011 = RESERVED / NOT EXECUTED`。

## Phase 2.7B E2E-009 冻结

- `DEFECT-017 = FIXED / REGRESSION VERIFIED / REAL PRIVATE METRICS WRITE PATH VERIFIED / FROZEN`。
- `E2E-009 = PASS / PRIVATE METRICS UNKNOWN-PARTIAL CONTRACT VERIFIED / FROZEN`。
- Production HTTP 创建 PrivateConversionSnapshot 416，绑定 Account 8456 / PublishedNote 592 / label `E2E009_ACCEPT`。
- E2E ACCEPTANCE TEST DATA：dm_count=3、wechat_add_count=1；consultation/deal/revenue 未提交并在 canonical read 中保持 null/UNKNOWN。
- provenance=`USER_ATTRIBUTED`；PublishedNote 592 仍绑定 Draft 2625 / DraftVersion 2087。
- Migration=0；Alembic head 保持 `d8e9f0a1b2c3`。
- 下一步为 E2E-010；不开始 Testing Track。

## Phase 2.7B E2E-010 冻结

- Turn 178 使用 UTF-8、Conversation 874、Workspace PublishedNote 592 和自然语言复盘请求。
- Control Semantic 真实成功：qwen/qwen3.8-flash、v1、attempt 1、4723ms、is_mock=false；Primary Intent=`POST_PUBLISH_REVIEW`。
- “给出下一轮内容策略建议”同时被识别为独立 CONTENT_STRATEGY sub-goal；Planner 因第二条 workflow 缺少 Research 错误追问 `research_artifact_ref`。
- run_ref=null；WorkflowRun/Operation/Review/Candidate/Memory 均未新增；PromptRunLog 仅新增两次 Control Semantic 记录。
- `DEFECT-018 = OPEN / RCA CONFIRMED / NOT FIXED`。
- `E2E-010 = BLOCKED BY DEFECT-018 / POST PUBLISH REVIEW WORKFLOW NOT STARTED`。
- 不执行 E2E-011，不开始 Testing Track。

## Phase 2.7B DEFECT-018 修复 / E2E-010 重验冻结

- Semantic prompt v2 + post-parse business validation + structured retry 实施 Review goal subsumption；未静默删除 sub-goal。
- 内生 Review 策略建议不再拆成 CONTENT_STRATEGY；明确 Research/独立 Strategy Artifact 的真实 mixed-goal 仍保留。
- 定向回归 80 passed；Backend full 654 passed / 3 skipped；Frontend tests 7/7。
- Turn 182：Account 8456 / Conversation 874 / PublishedNote 592 / request `phase27b-e2e010-defect018-20260926-01`。
- Control Semantic：qwen3.8-flash / v2 / is_mock=false / 4572ms / SUCCESS；Intent 仅 POST_PUBLISH_REVIEW，不再询问 Research。
- 真实创建 Run `wfr_b188f63e36b4418aa805173c2be33e2f` / POST_PUBLISH_REVIEW_V1 / checkpoint 3。
- Note 592 无 PublicMetricSnapshot；metrics query 返回 CONTEXT_ERROR，Run 进入 WAITING_USER(required=`public_metrics`)。
- 该行为与冻结的“无公开指标保持 UNKNOWN/unavailable”合同冲突。
- `DEFECT-018 = FIXED / REGRESSION VERIFIED / REAL WORKFLOW START VERIFIED / FROZEN`。
- `DEFECT-019 = OPEN / RCA CONFIRMED / ZERO-PUBLIC-METRICS REVIEW BLOCKED`。
- `E2E-010 = BLOCKED BY DEFECT-019 / REVIEW ANALYSIS NOT REACHED`。
- Review/Candidate 未新增，Memory 保持 451；未修改 DraftVersion 2087 / PublishedNote 592 / Private Snapshot 416。
- Alembic current/head=`d8e9f0a1b2c3`；Migration=0。
- 不执行 E2E-011，不开始 Testing Track。

## Phase 2.7B DEFECT-019 修复 / E2E-010 再验冻结

- QueryPostPublishMetricsTool 在 0 public snapshot 时返回 `UNKNOWN + empty public_metrics`，并保留真实 Private Snapshot；不再返 CONTEXT_ERROR。
- Workflow 以 `PUBLIC_METRICS_UNKNOWN` warning 继续 Analysis；Analysis contract 允许 partial metrics，并拒绝 UNKNOWN/AVAILABLE 状态混用。
- Review semantic prompt v2 明确公开 UNKNOWN 不得伪造为 0，USER_ATTRIBUTED 私域事实可引用。
- 定向 38 passed；Backend 654 passed / 3 skipped；Frontend 7/7 + container build PASS；Migration=0；Alembic=`d8e9f0a1b2c3 (head)`。
- 为隔离 Turn 182 历史 Pending，使用 canonical API 创建同 Account 干净 Conversation 1405；未删除历史数据。
- Turn 186 / Run `wfr_14485d5b1b0748a098dc8ef07902eb7b`：原文本、PublishedNote 592，未补 public metrics。
- Runtime 真实持有 public UNKNOWN/empty，Private 3/1 USER_ATTRIBUTED，其余 UNKNOWN；无 WAITING_USER。
- Runtime exact lineage：PublishedNote 592 -> Draft 2625 -> DraftVersion 2087/V2，Package 511。
- Review Analysis 启动后，qwen3.8-2.4t-a95b 两次均在约 30.1s timeout，Artifact/Candidate 未创建。
- `DEFECT-019 = FIXED / REGRESSION VERIFIED / REAL PARTIAL-METRICS ANALYSIS PATH VERIFIED / FROZEN`。
- `ENV-009 = POST_PUBLISH_REVIEW_STRONG_MODEL_30S_TIMEOUT / OPEN`。
- `E2E-010 = BLOCKED BY ENV-009 / REVIEW ARTIFACT AND STRATEGY CANDIDATE NOT CREATED`。
- Review/Candidate/Memory/Operation 相对重验前基线不变；未修改 DraftVersion/PublishedNote/Private Snapshot。
- 不执行 E2E-011，不开始 Testing Track。

## Phase 2.7B ENV-009 / E2E-010 最终重验冻结

- Review-only execution policy：`qwen3.8-flash / 120s / enable_thinking=false`；专属配置缺失时 fallback 全局值。
- SDK max_retries=0；Adapter 仍是唯一 structured retry owner；Workflow Analysis `retry=False`。
- 定向 65 passed；Backend 657 passed / 3 skipped；Frontend 7/7 + container build PASS；Migration=0；Alembic head=`d8e9f0a1b2c3`。
- Turn 187 / Conversation 1406 / Run `wfr_fec42605371241b296e31cf5d3cb4320`；原文本与 PublishedNote 592。
- OBS 2189：qwen3.8-flash / thinking=false / timeout=120 / attempt 1 / 14098ms / SUCCESS / is_mock=false；JSON+Pydantic PASS。
- Runtime exact V2=2087；public UNKNOWN/empty；private 3/1 USER_ATTRIBUTED；missing 仍 UNKNOWN。
- deterministic grounding 失败：Workflow 未向 `published_note` payload 传入 evidence refs，Review Service allowed set 为空，模型合理引用被判 invalid。
- `ENV-009 = POLICY IMPLEMENTED / REGRESSION VERIFIED / REAL FLASH STRUCTURED WORKLOAD VERIFIED / FULL CLOSURE BLOCKED BY DEFECT-020`。
- `DEFECT-020 = OPEN / RCA CONFIRMED / REVIEW GROUNDING ALLOWLIST EMPTY`。
- `E2E-010 = BLOCKED BY DEFECT-020 / REVIEW ARTIFACT AND STRATEGY CANDIDATE NOT CREATED`。
- Account 8456 本轮无 Review/Candidate/Memory/Operation 新增；未修改 DraftVersion/PublishedNote/Private Snapshot。
- 未运行 strong+120，未执行 E2E-011，未开始 Testing Track。

## Phase 2.7B DEFECT-020 / E2E-010 最终冻结

- Producer→Carrier→Consumer grounding propagation 已补齐；Validator 仍 fail-closed，未放宽 scope。
- 真实 allowlist：PublishedNote 592、Private Snapshot 416、Research 2862、Source Opportunity 3923；无 public ref、无全 Account 搜索。
- Targeted 53 passed；Backend 660 passed / 3 skipped；Frontend 7/7 + build PASS；Migration=0；Alembic head=`d8e9f0a1b2c3`。
- Turn 197 / Run `wfr_bd9133ef597b4f249919f1e55b917d6a` = PARTIAL_SUCCESS，仅 UNKNOWN warnings；全部业务 steps SUCCESS。
- OBS 2206：qwen3.8-flash / thinking=false / timeout=120 / attempt 1 / 21607ms / JSON+Pydantic+Business+Grounding PASS。
- Exact lineage：PublishedNote 592 -> Draft 2625 -> DraftVersion 2087/V2 / Package 511。
- Metrics：public UNKNOWN/{}；Private 416 = 3/1 USER_ATTRIBUTED；consultation/deal/revenue=UNKNOWN。
- Review Artifact 2141 = SUCCESS；Strategy Candidate 43/44 = PROPOSED；Account 8456 Strategy Memory 仍为 0。
- `DEFECT-020 = FIXED / REGRESSION VERIFIED / REAL GROUNDED REVIEW PATH VERIFIED / FROZEN`。
- `E2E-010 = PASS / POST PUBLISH REVIEW EXACT VERSION + PROVENANCE + STRATEGY CANDIDATE BOUNDARY VERIFIED / FROZEN`。
- 下一步 E2E-011；本轮未执行 E2E-011/E2E-012/Testing Track。

## Codex 新窗口接管步骤

1. `git status --short`
2. `git diff --stat`
3. 阅读 `CURRENT_PHASE.md`
4. 保留工作区修改
5. 禁止 reset / restore / clean / stash
6. 只执行当前明确任务
# Phase 2.7B E2E-011 阻断（2026-09-27）

- 冻结基线：E2E-008/E2E-009/E2E-010 PASS；DEFECT-020 与 ENV-009 FROZEN。
- E2E-011 通过正式 Agent Turn 198 / Run `wfr_c8c1936eff5e4db591aaf6f1269ed1f5` 尝试从 Draft 2625/V2 创建 V3。
- Draft/Opportunity/Evidence resolution SUCCESS；Revision 使用 qwen3.8-2.4t-a95b，在 30742ms/30759ms 两次 timeout；Persistence NOT_STARTED，Operation=0。
- Draft 仍只有 V1=2082、V2=2087；V1/V2 hash 不变。PublishedNote 592 与 Package 511 仍绑定 2087/V2；Review/Candidate/Memory 不变。
- `ENV-010 = DRAFT REVISION STRONG MODEL 30S TIMEOUT / OPEN`。
- `E2E-011 = BLOCKED BY ENV-010 / V3 NOT CREATED`。
- 下一步先单独授权 ENV-010 Draft Revision execution-policy diagnostic；不要执行 V4、Review、E2E-012 或 Testing Track。

# ENV-010 Flash diagnostic（2026-09-27）

- Draft Revision 专属 execution policy 已接入：可选 model/timeout/thinking，缺失时回退全局；统一 LLMClient、SDK retry=0、Adapter structured retry owner 均不变。
- 生效配置：qwen3.8-flash / 120s / thinking=false；全局 strong model 未修改。
- Turn 199 / Run `wfr_5f190d00041c489baa5cd96dfffe9d5b`：flash 两次分别 8948ms/7303ms 返回 candidate，但都缺少必填 `applied_changes`，Pydantic VALIDATION_FAILED；Persistence NOT_STARTED，Operation=0。
- `ENV-010 = FLASH LATENCY VERIFIED / DRAFT REVISION PYDANTIC CONTRACT FAILED / OPEN`。
- `E2E-011 = BLOCKED BY ENV-010 / V3 NOT CREATED`。未执行 V4、Review、E2E-012 或 Testing Track。

# ENV-010 Schema Adherence resolved（2026-09-27）

- RCA=A：Pydantic 与追加 JSON Schema 均含 required `applied_changes`；Qwen 路径仅为 JSON mode，Revision v1 领域 Prompt 未解释该字段，sanitized candidate 在 Provider 层即缺失，并非 normalization 删除。
- Prompt `draft_revision_semantic` v1→v2：明确非空、真实 `applied_changes`；没有 default/alias、Schema 降级或额外 retry。
- Turn 203 / Run `wfr_e55d2c5784d34175af5a4bd9dd123e44` / OBS 2219：flash / thinking=false / 120s / attempt 1 / 10279ms / SUCCESS；V3=2112/version3/parent2087。
- Fidelity PASS：title/tags/CTA 不变；只改首段；首段之后正文 hash 完全相同；applied_changes 非空且准确。
- `ENV-010 = RESOLVED / REAL DRAFT REVISION WORKLOAD VERIFIED / FROZEN`。
- `E2E-011 = IN PROGRESS / V3 CREATED / V4 AND REVIEW NOT EXECUTED`。本轮未执行 V4、Review、E2E-012 或 Testing Track。

# E2E-011 Published Version Consistency PASS（2026-09-27）

- Draft 2625 append-only lineage：V1=2082 → V2=2087（published）→ V3=2112 → V4=2114（current/latest）；V1/V2/V3 hashes 不变。
- V4 Turn 207 / Run `wfr_7d94ebeee58f44c7b937abc973b81a1d` / OBS 2227 真实成功；只压缩结尾，其他内容 deterministic fidelity PASS。
- Review Turn 208 / Run `wfr_238a01de097e41adb4d6c354bd2eefc2`：runtime latest=2114，但 resolved published=2087；Analysis content hash 与 V2 相同、与 V4 不同。
- Review Artifact 2144；Candidates 47/48 PROPOSED；Public UNKNOWN，Private 416/3/1 USER_ATTRIBUTED；Account 8456 Strategy Memory 仍为 0。
- PublishedNote 592 与 Package 511 hashes/updated_at/binding 不变，均保持 V2/2087。
- Targeted 26 passed；`E2E-011 = PASS / PUBLISHED VERSION CONSISTENCY VERIFIED / FROZEN`。
- 下一步 E2E-012 Frontend Route / Lazy Load Acceptance；不要开始 Testing Track。

# Phase 2.7B DEFECT-026 Account-Scoped Asset Discovery（2026-09-27）
- 新增五个 account-scoped、read-only、paginated、lightweight Asset Index API 与五个 lazy list route；左侧正式导航覆盖 Agent、Research、Strategy、Draft、Published Content、Review、Trace。
- Account 8456 真实 API：Research 2/720B、Strategy 1/287B、Draft 1/221B、Publication 1/266B、Review 2/298B，page_size=20；SQL 层 account filter，max page_size=100。
- 真实 Edge：导航→Draft List→Draft 2625→Detail PASS；Research/Strategy/PublishedNote 592/Review 2144 可发现；Network failures=[]、Console errors=[]。
- Backend targeted 11 passed；full 667 passed/3 skipped；Frontend 16 passed；typecheck/build/diff PASS；Alembic=`d8e9f0a1b2c3 (head)`；Migration=0。
- `DEFECT-026 = FIXED / REGRESSION VERIFIED / REAL ACCOUNT-SCOPED ASSET DISCOVERY VERIFIED / FROZEN`。
- `E2E-012 = BLOCKED`：DEFECT-021/022/023/024 保持原状态；未开始 Testing Track。
- 报告：`docs/testing/PHASE_2_7B_DEFECT_026_REPORT.md`。

# Phase B2 Agent Decision Context / D03（2026-09-29）

- 实施 `CanonicalTurnContext + Tool Capability/Eligibility Policy + LLM Semantic Selection + Workflow Validation`；未恢复 12 Intent Router，未新增 Intent enum，Migration=0。
- Material provenance 保留 `CURRENT_TEXT / EXPLICIT_MATERIAL / BOTH`；同 URL 双来源只进入 Provider 一次。
- `FilteredToolset` 从 BUSINESS_ACTION 固定 5 tools 改为 capability candidate set；`_validate_tool_selection` 仅保留 objective invariant guard。
- Pending Research 仅在 account/workflow/status/checkpoint/required field 全部验证后形成 singleton，并复用现有 `AgentRuntime.resume()`。
- Targeted `119 passed`；Backend full `783 passed / 3 skipped / 18 warnings`。
- 真实 ExecutionGate“你有记忆吗”=`CONVERSATION / MEMORY_QUESTION`；OBS 2445=`qwen3.7-flash-2026-07-15 / SUCCESS / is_mock=false`。
- D03 真实 UI Material Panel 提交 3 Profile：Canonical=`EXTERNAL_XHS_PROFILE ×3 / EXPLICIT_MATERIAL`，eligible=`[run_research]`，实际选择 Research。
- Run `wfr_30289cbccdd645b1a2f392588a76b207`=`PARTIAL_SUCCESS`，input Profile=3，Account refs=3，均为 `XHS_MCP / is_mock=false`，Research Artifact=3038。
- OBS 2446 ExecutionGate 与 OBS 2447 Research Analysis 均使用 `qwen3.7-flash-2026-07-15` 且 SUCCESS；未观察到 `qwen3.8-flash` fallback。
- 报告：`docs/testing/PHASE_B2_AGENT_DECISION_CONTEXT.md`。继续 Phase B2，不开始 B3。

# Phase B2 Continued Context Selection Acceptance（2026-09-29）
- 未重跑 R01/R02/R03；使用 headed Edge 继续验证 B03/B04/B06。
- B03：候选 `run_research + run_content_strategy`，LLM 选择 Strategy；Run `wfr_0e8b5fa1781a49ecbf90311885166f56`=`SUCCESS`，Strategy 136，Opportunity 4317/4318/4319。
- B04：候选 `run_research + run_content_creation`，LLM 选择 Creation；Run `wfr_64043f99a6fb4a2c8c0933baebe0b906`=`PARTIAL_SUCCESS`，Draft 2697 已持久化，warning=`DRAFT_REVIEW_FAILED`。
- B06：候选 `run_research + run_post_publish_review`，LLM 选择 Post Review；Run `wfr_e6aad557980d4e139c4047af213cc6d5`=`PARTIAL_SUCCESS`，Review 2155 已持久化，指标缺失保持 `UNKNOWN`。
- 三次均为 `BUSINESS_ACTION`；当前材料为空，候选集来自服务器验证的 Workspace/Recent object facts，不依赖关键词 intent routing。
- PromptRunLog 均为 `is_mock=false / fallback_used=false`；ExecutionGate 与 Post Review 使用 `qwen3.7-flash-2026-07-15`，Strategy/Draft 保持主模型 `qwen3.8-2.4t-a95b`；未观察到 `qwen3.8-flash`。
- 本轮无代码修改、无 Migration、未开始 B3。完整证据见 `docs/testing/PHASE_B2_AGENT_DECISION_CONTEXT.md`。

