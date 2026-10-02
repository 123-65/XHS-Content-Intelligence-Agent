# Phase 2.7B E2E-007 Account Boundary Acceptance Report

## 1. Baseline Conversation

Conversation 874 was read-only verified before the request. Its durable owner was Account 8456. Active pending run/checkpoint were empty and active pending interaction was JSON null. Latest valid Turn was 163 and latest Run was `wfr_0528728e8503405dad7b1fe0c7c30b39`, `PARTIAL_SUCCESS`, checkpoint=5.

## 2. Account A

Account A=8456, the canonical owner of Conversation 874.

## 3. Account B

Account B=1, selected read-only from an existing Account row with ID different from 8456. No private profile fields were read or reported and no test Account was created.

## 4. Pre-Request Baseline

- Agent Turn count/max=163/163.
- WorkflowRun count/max=2449/2502.
- PromptRunLog count/max=2150/2150.
- MCP Tool Call count/max=827/827.
- Workflow Operation count/max=241/241.
- Research Artifact count/max=2907/2949.
- Account Evidence count/max=2997/2997.
- Note Evidence count/max=11140/11140.
- Opportunity count/max=4034/4118.

## 5. Cross-Account Request

A formal `POST /api/agent/turns` used Account B=1, Conversation=874, new client_request_id=`phase27b-e2e007-cross-account-20260925-01`, and a safe account-information/general-chat message. It included no XHS URL, material, Artifact ref, run_ref, or Pending token.

## 6. Boundary Response

HTTP 403, code=`CONVERSATION_ACCOUNT_MISMATCH`, message=`Conversation 不属于当前 Account。`. The first valid request established HTTP 403; an identical valid request was used to read the error JSON because PowerShell did not expose the first response body. A separate malformed curl diagnostic returned 422 at JSON parsing and never entered product request handling. All attempts remained before Turn reservation and had zero side effects.

## 7. Turn Creation Check

PASS. Agent Turn count/max remained 163/163 after the cross-account rejection. The Account B client_request_id matched zero durable Turn rows. Account B received no Turn identity and did not reuse Account A's Turn.

## 8. Run Creation Check

PASS. WorkflowRun count/max remained 2449/2502. No Run identity was returned or created and the existing Account A Run was unchanged.

## 9. LLM / Provider Replay Check

PASS. PromptRunLog remained 2150/2150 and MCP Tool Calls remained 827/827 after rejection. Therefore the request did not reach Control Semantic, any other LLM call, XHS Provider, or Workflow execution.

## 10. Operation / Artifact / Evidence Check

PASS. After rejection: Operation=241/241, Research Artifact=2907/2949, Account Evidence=2997/2997, Note Evidence=11140/11140, and Opportunity=4034/4118. No side effect was created.

## 11. Conversation State Integrity

PASS. Conversation owner remained 8456; active pending run/checkpoint remained empty and active pending interaction remained null. Latest valid Turn remained 163 immediately after rejection. Account A recent references were unchanged and none were returned to Account B.

## 12. Correct-Account Positive Control

A new formal request used Account A=8456, Conversation=874, client_request_id=`phase27b-e2e007-owner-positive-20260925-01`, and `Hello.`. It completed as Turn 164 with `GENERAL_CHAT / RESPOND / SUCCESS`, no run_ref, no Pending, and no Artifact. Only the expected Control Semantic OBS 2151 was added (`qwen3.8-flash`, is_mock=false, SUCCESS, 3498 ms). WorkflowRun, MCP, Operation, Artifact, Evidence, and Opportunity counts remained unchanged. Conversation ownership remained 8456.

## 13. Product Defect

None. Conversation ownership was enforced before Turn reservation and Agent execution.

## 14. E2E-007 Final Status

`E2E-007 = PASS / CONVERSATION ACCOUNT BOUNDARY VERIFIED / FROZEN`.

## 15. 面试资产

New Q&A=0; updated existing Account/Context Identity Q&A=1. An `account_id` filter only at downstream Repository queries is insufficient because Conversation owns durable recent context, Pending, and workspace references. The boundary must run before Turn reservation and Agent execution; unchanged Turn, Run, LLM, MCP, Operation, Artifact, and Evidence records prove the rejection happened at the correct layer.

## 16. 下一步

E2E-008 Manual Publish Exact Draft Version. Do not start the Testing Track yet.

## 17. Git

No product code was changed. No commit, reset, restore, clean, stash, `git add .`, or `git add -A` was performed.
