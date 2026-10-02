# ENV-008 Research Analysis Model Diagnostic

## 1. Diagnostic Contract

One isolated real call used the canonical `LLMStructuredCompetitorAnalyzer`, with SDK retries=0, Adapter attempts=1, timeout=120 seconds, no E2E/Workflow execution, and no Artifact or business-data writes. The only workload change was model override from `qwen3.8-2.4t-a95b` to the already configured `qwen3.8-flash`. `enable_thinking` was not explicitly set, matching the strong-model Analysis call.

## 2. Identical Workload Verification

Evidence was read from Run `wfr_14dee8edbef24079a30e5420cbfb451d` durable state and validated as the same `CompetitorEvidence`: Note refs 10998/10999/11000, Account ref 2914, 0 Comments, 0 OCR. Canonical compact evidence serialization was 3,899 characters; the earlier PostgreSQL JSON text measurement was approximately 4,052 characters because of representation whitespace. The same `CompetitorSemanticResult`, `competitor_semantic_analysis/v1`, System Prompt, schema construction, and `CompetitorGroundingValidator` were used. No Evidence, Prompt, or Schema field was removed.

## 3. Strong Model Baseline

`qwen3.8-2.4t-a95b`, timeout=120 seconds: attempt 1 failed at 104,711 ms with Connection error; attempt 2 failed at 120,745 ms with request timeout. No structured response reached parsing or validation.

## 4. Flash Model Result

Provider=`qwen`, model=`qwen3.8-flash`, is_mock=false, timeout=120, SDK retries=0, Adapter attempt total=1, `enable_thinking` not explicitly set. The single call ended after 121,279 ms. Provider result=`PROVIDER_FAILED / LLM_PROVIDER_UNAVAILABLE`; attempt latency=121,276 ms and `retry_exhausted=true`.

## 5. Structured Validation

FAIL / NOT REACHED. The Provider returned no usable structured payload. JSON structured parse, Pydantic `CompetitorSemanticResult` validation, ten-section completeness checks, and post-parse grounding validation could not run. Therefore Flash did not meet the diagnostic success contract.

## 6. Latency Comparison

- Strong: 104.7 seconds Connection error, then 120.7 seconds timeout.
- Flash: one 121.3-second provider failure at the same finite deadline.

For this Analysis workload, Flash did not provide the latency improvement previously observed on Control Semantic.

## 7. Reliability Comparison

Neither model produced a valid response for this exact Research Analysis workload under the 120-second budget. Strong produced one connection error and one timeout; Flash produced one deadline-aligned provider failure. No claim about content quality can be made because neither result reached Schema validation.

## 8. Decision

Do not route Research Analysis to `qwen3.8-flash` based on this evidence. It failed the required SUCCESS + structured validation + field completeness + bounded latency rule. Do not try an unverified second model in this turn.

## 9. Recommended Production Routing

No production routing change. Keep the current frozen Control Semantic route unchanged and keep the default Research model configuration unchanged until a separate Prompt/Schema optimization RCA is completed. A second model candidate may be considered only if it is explicitly enumerated as available by the current Provider/configuration and separately authorized.

## 10. ENV-008 Status

`ENV-008 = STRONG AND FLASH MODELS FAILED CURRENT RESEARCH ANALYSIS CONTRACT WITHIN 120S / MODEL ROUTING DIAGNOSTIC COMPLETE / OPEN`.

## 11. E2E-005 是否可继续

不可继续。`E2E-005 = BLOCKED BY ENV-008`。本轮未执行 E2E-005。

## 12. 面试资产

新增 Q&A=0；更新已有 per-task model routing Q&A=1。真实对比证明模型路由不能只依赖模型名称或其他 Agent node 的 latency，必须用当前 task 的完整 Prompt/Schema/Evidence 合同验证。

## 13. Git

No production routing or product code was changed in this diagnostic. The temporary diagnostic entrypoint was removed after the single call. No commit, reset, restore, clean, stash, `git add .`, or `git add -A` was performed.

Side-effect verification: Workflow Run/checkpoint/Pending remained unchanged; max PromptRunLog ID remained 2140 because an in-memory recorder was used; global Operations=234, Research Artifacts=2904, Opportunities=4027, Account Evidence=2993, Note Evidence=11133.
