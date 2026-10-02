# ENV-008 Research Analysis Production Policy and E2E-005 Final Acceptance

## 1. Frozen Production Policy

Canonical Settings now define Research Analysis independently: model=`qwen3.8-flash`, timeout=120 seconds, and `enable_thinking=false`. `LLMStructuredCompetitorAnalyzer` passes those settings through the existing `model`, `timeout_seconds`, and `extra_body` call parameters. Prompt, Schema, Evidence assembly, Workflow, Resume, Provider classes, and retry architecture were not changed.

## 2. Other LLM Boundaries

Runtime after backend recreation: provider=`qwen`, default model=`qwen3.8-2.4t-a95b`; Control Semantic=`qwen3.8-flash` + thinking=false + default 30-second timeout; Research Analysis=`qwen3.8-flash` + thinking=false + 120 seconds. SDK `max_retries=0`; Adapter attempt total=2 remains the only structured retry owner; is_mock=false. Draft, Strategy, Review, and Revision retain the default model path.

## 3. Regression

- Targeted: 49 passed.
- Backend: 646 passed, 3 skipped, 18 warnings.
- Frontend: 7 passed; `vue-tsc --noEmit` passed; container production build passed.
- `git diff --check`: passed (line-ending warnings only).
- Alembic current=head=`c7d8e9f0a1b2`.
- Migration=0; New Route=0.

The first local test invocations did not enter test logic because the repository root lacked the `app` import path and the Windows Python lacked `psycopg2`; the canonical container run produced the results above. Host Vite was blocked by/unstable under the Windows execution environment after transform, while the canonical frontend container completed the same production build.

## 4. E2E Setup

Account=8456, Conversation=874. URLs came directly from root `xhs链接.md`. Two pre-run Turns created no Workflow Run: Turn 160 exposed PowerShell request-body encoding corruption, and Turn 161 used an English paraphrase that Planner interpreted as requiring an existing Research Artifact. Both stopped before Workflow execution and retained immutable request IDs. The accepted path used a new request ID and the previously verified Research wording encoded explicitly as UTF-8.

## 5. Turn 1

Turn 162 / request `phase27b-e2e005-researchpolicy-turn1-20260925-03`, total latency=162,241 ms. It submitted only one authorized Profile URL and created new Run `wfr_0528728e8503405dad7b1fe0c7c30b39`. Result=`WAITING_USER`, checkpoint=3, execution_mode=START. `collection_accounts=SUCCESS`, account Evidence ref=2914, and Evidence Gate persisted `RESEARCH_V1_RESUME` requiring `note_urls,evidence_refs`.

## 6. Turn 2 / Resume

Turn 163 / request `phase27b-e2e005-researchpolicy-turn2-20260925-01`, total latency=177,635 ms. It submitted only the three authorized Note materials through a new `POST /api/agent/turns`; no run_ref was passed and Runtime/checkpoint/database were not called directly. The same Run resumed, checkpoint 3→5, execution_mode=RESUME. `growth_context=SKIPPED`, `collection_accounts=SKIPPED`, and `collection_notes=SUCCESS`.

`processed_note_urls` exactly equals the three current-Turn authoritative URLs. Collected refs=10998/10999/11000, account ref remains 2914, and Provider evidence remains real/non-mock.

## 7. Research Analysis

OBS 2150: provider=`qwen`, model=`qwen3.8-flash`, is_mock=false, prompt=`competitor_semantic_analysis/v1`, schema=`CompetitorSemanticResult`, attempt=1/2, status=SUCCESS, latency=27,274 ms, no retry. Live policy confirms thinking=false and timeout=120 seconds. JSON parse and Pydantic validation passed in the Provider; canonical Analyzer returned only after deterministic grounding validation passed. Workflow `analysis=SUCCESS`.

## 8. Final Workflow and Artifact

Run final status=`PARTIAL_SUCCESS` because OCR was not configured and Comment collection was partial; this is an accepted successful terminal state with no Workflow error. `artifact_creation=SUCCESS`; Research Artifact 2949 has account_id=8456, account Evidence=[2914], Note Evidence=[10999,11000,10998], note_count=3, comment_count=0, status=SUCCESS. Durable operation 241 binds Run `wfr_0528728e8503405dad7b1fe0c7c30b39` to `create_research_artifact:singleton` and Artifact 2949.

## 9. Pending and Duplication

Run state/result pending is null, Public Run API returns null, and Conversation `active_pending_run_ref`, checkpoint, and interaction are null. PostgreSQL JSONB stores a JSON null value rather than SQL NULL in the aggregate column; ORM/public semantics correctly restore `None` and there is no stale Pending object.

Baseline→final: Workflow Runs 2448→2449 (exactly one accepted new Run); Operations 240→241 (exactly one Artifact operation); Research Artifacts 2906→2907 (exactly one); Opportunities 4032→4034 (two expected report-bundle opportunities); Account Evidence 2997→2997 and Note Evidence 11140→11140 (existing canonical records reused, no duplicates).

## 10. Final Status

`ENV-008 = RESOLVED / REAL ANALYSIS WORKLOAD VERIFIED / FROZEN`.

`E2E-005 = PASS / REAL PENDING-RESUME-ANALYSIS-ARTIFACT PATH VERIFIED / FROZEN`.

`DEFECT-013 = FIXED / REGRESSION VERIFIED / REAL RESUME VERIFIED / FROZEN` remains unchanged. E2E-006 and the Testing Track were not executed.

## 11. Git

No commit, reset, restore, clean, stash, `git add .`, or `git add -A` was performed. The pre-existing dirty worktree was preserved.
