# Phase 2.7B E2E-006 Request Idempotency Acceptance Report

## 1. Baseline Request

The baseline was the already successful Turn 163: Account=8456, Conversation=874, client_request_id=`phase27b-e2e005-researchpolicy-turn2-20260925-01`, Run=`wfr_0528728e8503405dad7b1fe0c7c30b39`. Its persisted canonical request contained a 41-character user input, 3 Note materials, and 0 Profile materials. The replay entrypoint loaded `request_payload` directly from durable Turn 163; no URL or token was printed or reconstructed manually.

## 2. Durable Idempotency Identity

Before replay there was exactly one matching durable row: Turn id=163, status=COMPLETED, with request fingerprint `cd73fa224b4c3c4efdb3aebe7838e18f719b97d08ba79ea98e9037318907d875`. Scope remained Account 8456 and Conversation 874. No cached/replayed response flag exists in the current API contract, so none was required.

## 3. Pre-Replay Baseline

- Agent Turns: 163 total; matching key count=1, id=163.
- Workflow Runs: 2449 total; target Run=`PARTIAL_SUCCESS`, checkpoint=5, execution_mode=RESUME.
- PromptRunLog: count/max id=2150/2150.
- MCP Tool Calls: count/max id=827/827.
- Workflow Operations: 241.
- Account Evidence: 2997; Note Evidence: 11140.
- Research Artifacts: 2907; Opportunities: 4034.

## 4. Exact Replay Request

An independent formal `POST /api/agent/turns` was sent with the exact persisted canonical payload, including the same Account, Conversation, client_request_id, user input, and materials. It did not call the idempotency service, Runtime, Workflow, LLM, or Provider directly and did not mutate the database.

## 5. Exact Replay Response

HTTP 200. Response identity: conversation_id=874, turn_id=163, run_ref=`wfr_0528728e8503405dad7b1fe0c7c30b39`, checkpoint_version=5, workflow status=`PARTIAL_SUCCESS`. The response is the persisted first result.

## 6. Turn Identity Verification

PASS. Agent Turn total remained 163. Matching key count remained exactly one and min/max id remained 163. No second Turn was created.

## 7. Run Identity Verification

PASS. Workflow Run total remained 2449. The same Run retained `PARTIAL_SUCCESS`, checkpoint=5, and execution_mode=RESUME. No second Run or checkpoint transition occurred.

## 8. LLM Replay Check

PASS. PromptRunLog remained count/max id=2150/2150. Control Semantic and Research Analysis were not called again.

## 9. Provider Replay Check

PASS. MCP Tool Call Log remained count/max id=827/827. Neither Account nor Note collection was called again. Together with unchanged PromptRunLog, this proves no LLM or XHS Provider replay; latency alone was not used as evidence.

## 10. Operation / Evidence / Artifact Check

All values remained unchanged after exact replay and after mismatch: Operations=241; Account/Note Evidence=2997/11140; Research Artifacts=2907; Opportunities=4034. Artifact creation did not execute again and no business side effect was duplicated.

## 11. Payload Mismatch Replay

A second formal HTTP request kept the same Account, Conversation, client_request_id, and materials, while appending one safe sentence to the user message. It introduced no new URL or dangerous action.

## 12. Mismatch Protection

HTTP 409 with code=`REQUEST_IDENTITY_MISMATCH` and message=`client_request_id 已用于不同请求。`. The API did not return the old result as though the payload matched, and did not create or execute a new request. All durable counts and max IDs remained at baseline.

## 13. Product Defect

None. Exact replay reused the durable result without execution, and mismatch replay was rejected before execution.

## 14. E2E-006 Final Status

`E2E-006 = PASS / DURABLE REQUEST IDEMPOTENCY VERIFIED / FROZEN`.

## 15. 面试资产

New Q&A=0; updated existing idempotency Q&A=1. Equal HTTP response content or low latency alone cannot establish idempotency; durable request fingerprint, Turn identity, Run identity, and unchanged LLM/MCP/Operation/Evidence/Artifact records jointly prove it.

## 16. 下一步

E2E-007 Account Boundary. Do not start the Testing Track yet.

## 17. Git

No product code was changed. The temporary replay helper was deleted after acceptance. No commit, reset, restore, clean, stash, `git add .`, or `git add -A` was performed.
