# ENV-008 Timeout Budget 修复与 E2E-005 Final Acceptance Report

## 1. Frozen Timeout Contract

Global `LLM_TIMEOUT_SECONDS=30` remains the default request budget. New `LLM_RESEARCH_ANALYSIS_TIMEOUT_SECONDS=120` applies only to canonical Research Analysis. Control Semantic and all other uncovered LLM calls retain the default 30-second budget.

## 2. Implementation

A minimal optional `timeout_seconds` parameter is passed from `LLMClient.generate_structured` to `OpenAICompatibleProvider.generate_structured` and then to the individual `chat.completions.create` request. `LLMStructuredCompetitorAnalyzer.analyze` is the only production caller passing the Research Analysis setting. No model, Prompt, Schema, Evidence, Workflow, Provider selection, or retry policy changed.

## 3. Runtime Configuration

After backend recreation, runtime values were verified from the live process: provider=`qwen`, default model=`qwen3.8-2.4t-a95b`, Control Semantic model=`qwen3.8-flash`, default timeout=30, Research Analysis timeout=120, SDK max retries=0, structured logical attempts=2, is_mock=false.

## 4. Retry Ownership

SDK internal retries remain disabled. Adapter/Tenacity remains the only structured retry owner with two logical attempts. No nested retry was introduced. OBS 2139/2140 are exactly attempts 1/2 and 2/2.

## 5. Targeted Regression

65 passed. Coverage includes default 30 seconds, Research 120 seconds, Control no timeout override, strong/flash model boundaries, SDK retry=0, existing structured retry behavior, finite default, and rejection of non-positive Research timeout values.

## 6. Full Regression

Backend: 646 passed, 3 skipped, 18 warnings. Frontend: 7 passed; `vue-tsc --noEmit` and container production build passed. `git diff --check` passed. Alembic current=head=`c7d8e9f0a1b2`. Migration=0; New Route=0.

## 7. New Turn 1

Turn 155, request `phase27b-e2e005-env008-turn1-20260925-01`, Account 8456, Conversation 874, Run `wfr_14dee8edbef24079a30e5420cbfb451d`. Total Turn latency was 25,896 ms.

## 8. WAITING_USER / Pending

Turn 155 reached real Workflow `WAITING_USER`, checkpoint=3. `collection_accounts=SUCCESS`; durable Pending was `RESEARCH_V1_RESUME` with required fields `note_urls,evidence_refs`, and Conversation state pointed to the same Run/checkpoint.

## 9. New Turn 2

Turn 156, request `phase27b-e2e005-env008-turn2-20260925-01`, submitted only the three authorized Note materials. It did not pass a run_ref, call Runtime directly, mutate the database manually, or resend Turn 1. Total Turn latency was 304,207 ms.

## 10. Same Run Resume

Turn 156 resumed the same Run `wfr_14dee8edbef24079a30e5420cbfb451d`; checkpoint advanced 3 to 5 and `execution_mode=RESUME`. Only one Run exists for this path. `growth_context=SKIPPED` and `collection_accounts=SKIPPED`.

## 11. Note Provider Workload

`collection_notes=SUCCESS`. Processed URLs exactly equal the three current-turn authoritative Note materials. Evidence refs are 10998/10999/11000. Each record is `xiaohongshu_mcp / XHS_MCP / is_mock=false`.

## 12. Research Analysis

The real call used provider=`qwen`, model=`qwen3.8-2.4t-a95b`, schema=`CompetitorSemanticResult`, prompt key=`competitor_semantic_analysis`, version=`v1`, and the 120-second per-call budget. Structured validation did not begin because neither attempt returned a response payload.

## 13. Analysis Latency

OBS 2139, attempt 1/2: 104,711 ms, `PROVIDER_FAILED`, `Connection error`. OBS 2140, attempt 2/2: 120,745 ms, `PROVIDER_FAILED`, `Request timed out`, `retry_exhausted=true`. The second attempt proves the 120-second override was active. Per the frozen stop condition, no 300-second increase or further retry was performed.

## 14. Research Artifact

No Research Artifact was created. `artifact_creation=NOT_STARTED`; the Run ended `FAILED / ANALYSIS_PROVIDER_FAILED`.

## 15. Duplication Check

Run operations remained 0; global operations 234->234; Research Artifacts 2904->2904; Account Evidence 2993->2993; Note Evidence 11133->11133. No duplicate operation, artifact, or evidence side effect was created.

## 16. ENV-008 Final Status

`ENV-008 = TASK-SPECIFIC 120S BUDGET IMPLEMENTED / REGRESSION VERIFIED / REAL ANALYSIS STILL FAILED / OPEN`.

The accepted RCA remains frozen. New real evidence shows both provider/transport instability on attempt 1 and strong-model latency exceeding the finite 120-second budget on attempt 2. The next decision must evaluate per-task model routing versus Prompt/Schema optimization; timeout must not be raised again without a new contract.

## 17. DEFECT-013

`DEFECT-013 = FIXED / REGRESSION VERIFIED / REAL RESUME MATERIAL PATH VERIFIED / FROZEN`. The same-run authoritative material path passed again and is not implicated in the analysis failure.

## 18. E2E-005 Final Status

`E2E-005 = FAILED / BLOCKED BY ENV-008`. The PASS contract was not met because real Analysis and Artifact creation did not succeed. E2E-006 was not started.

## 19. 面试资产

新增 Q&A=0；更新 Q&A=1。现有 timeout/model-routing 问题已补充真实 120 秒预算仍未完成强模型 Research Analysis 的证据。

## 20. 下一步

Open a separately authorized decision for Research Analysis per-task model routing versus Prompt/Schema optimization. Do not increase the timeout to 300 seconds and do not enter Testing Track.

## 21. Git

No commit, reset, restore, clean, stash, `git add .`, or `git add -A` was performed. The pre-existing dirty worktree was preserved.
