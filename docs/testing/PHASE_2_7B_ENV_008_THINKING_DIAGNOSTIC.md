# ENV-008 Research Analysis Thinking Diagnostic

## 1. Diagnostic Contract

One isolated real call used canonical `LLMStructuredCompetitorAnalyzer`, `competitor_semantic_analysis/v1`, and `CompetitorSemanticResult`. Provider=`qwen`, model=`qwen3.8-flash`, timeout=120 seconds, OpenAI SDK retries=0, Adapter logical attempts=1. No E2E or Workflow was executed.

## 2. Identical Workload Verification

The call restored `CompetitorEvidence` read-only from Run `wfr_14dee8edbef24079a30e5420cbfb451d`: 3 Notes (10998/10999/11000), 1 Account (2914), 0 Comments, and 0 OCR. Canonical compact evidence serialization was 3,899 characters. Evidence assembly, System Prompt, Schema, model, and grounding validator were unchanged from the previous Flash diagnostic.

## 3. Thinking Configuration

The only workload-policy variable was explicit `extra_body={"enable_thinking": false}`. This was injected only by the temporary diagnostic client wrapper and did not alter product code or production configuration.

## 4. Flash Result

SUCCESS. The single real Provider attempt completed in 20,575 ms; attempt evidence reported 20,571 ms. Provider result=`SUCCESS`, attempt=1/1, retry_exhausted=false.

## 5. Structured Validation

PASS. JSON structured parse passed, Pydantic `CompetitorSemanticResult` validation passed, all 10 top-level sections were present under the current contract, and the existing deterministic `CompetitorGroundingValidator` passed.

## 6. Latency

20.575 seconds, materially below the fixed 120-second Research Analysis budget (about 17% of the budget).

## 7. Comparison With Previous Flash Run

- Flash with thinking not explicitly configured: 121,279 ms, Provider failure, no structured payload.
- Flash with `enable_thinking=false`: 20,575 ms, Provider success, Schema/Pydantic/grounding PASS.

The model, evidence, Prompt, Schema, timeout, and single-attempt policy were held constant. This isolates thinking policy as the observed differentiator; it does not make a subjective content-quality claim beyond the existing deterministic validations.

## 8. RCA Update

The previous attribution to model or Schema alone was incomplete. For this online structured workload, the default/non-explicit thinking path is incompatible with the required latency/reliability contract, while explicit non-thinking mode satisfies it in this controlled call. Prompt/Schema optimization should not precede validating this execution-policy route in production configuration and E2E.

## 9. Production Recommendation

Recommend a separately authorized minimal production change for Research Analysis only: `LLM_RESEARCH_ANALYSIS_MODEL=qwen3.8-flash` plus explicit `enable_thinking=false`, while retaining timeout=120, SDK retry=0, the existing structured contract, and unchanged Control Semantic routing. This diagnostic did not apply that change.

## 10. ENV-008 Status

`ENV-008 = THINKING-MODE RCA COMPLETE / FLASH NON-THINKING PATH VERIFIED / PRODUCTION ROUTING NOT YET IMPLEMENTED / OPEN`.

## 11. E2E-005 是否可继续

Not yet. `E2E-005 = BLOCKED BY ENV-008` until the recommended production routing/execution-policy change is separately implemented and regression-verified. E2E-005 was not executed.

## 12. 面试资产

New Q&A=0; updated the existing per-task execution-policy Q&A=1. Routing is a tuple of model, thinking mode, timeout, retry policy, and structured contract, and must be verified against the node's real workload.

## 13. Git

No product code, production configuration, Prompt, Schema, Workflow, or routing was changed. The temporary diagnostic entrypoint was removed after the call. No commit, reset, restore, clean, stash, or broad add was performed.

Side-effect verification after the call: Run remained FAILED/checkpoint=5/execution_mode=RESUME with pending state unchanged; max PromptRunLog ID=2140; Workflow Operations=234; Research Artifacts=2904; Opportunities=4027; Account/Note Evidence=2993/11133.
