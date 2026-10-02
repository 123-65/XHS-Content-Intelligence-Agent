# Functional Baseline v1.1 Current Snapshot

## 1. Environment

- Product entry: `http://127.0.0.1:5173`
- Execution: real Microsoft Edge UI through browser automation; DOM, Network, Console, and visible Trace UI only.
- Account: Account 8456, selected from the rendered account dropdown (`E2E 考公考编验收 20260923`).
- XHS material: complete authorized URLs read from `xhs链接.md`; no token or query parameter was removed.
- No SQL, repository call, direct backend API, direct Workflow/Tool invocation, or test fixture was used.

## 2. Snapshot Identity

Git HEAD was `ec101d4e7ce6484ee4617e0d334a60757b532014` in a pre-existing dirty worktree. Runtime parity was independently verified in `docs/eval/results/runtime_parity_verification.json`: the running bind-mounted backend matched the audited worktree for all four sampled source hashes. This report therefore freezes the effective current snapshot, not the older v1 snapshot.

## 3. Case Results

| Result | Cases |
|---|---|
| PASS | A01, C03, C09, G03 |
| FAIL | A03, A04, A05, A07, A08, B01, B03, B04, B05, B06, C01, C02, D01, D02, E01, E02, E05, G01, H01, J06, K01, L02, M04, N05 |
| BLOCKED | None |
| UNVERIFIED | D03, J01 |

Detailed per-case evidence is in `results/functional_baseline_v1_1_results.jsonl`.

## 4. PASS/FAIL/BLOCKED/UNVERIFIED

- Case count: 30
- PASS: 4
- FAIL: 24
- BLOCKED: 0
- UNVERIFIED: 2
- Executed Pass Rate: **13.33%**. UNKNOWN/UNVERIFIED evidence was not removed from the denominator.

## 5. Conversation

A01 passed: natural greeting, no Workflow run, `GENERAL_CHAT / RESPOND / SUCCESS`. Response quality was 4/5.

## 6. Capability

A03/A04/A05 all failed. “你能做什么”, Skill, and Tool questions returned the same generic greeting. The UI marked them SUCCESS despite not answering the requested capability question, so all three count as fake success.

## 7. Boundary

A07/A08 did not claim automatic publish/comment success, but they asked for operational parameters instead of explicitly stating the unsupported boundary. Both failed expected behavior without fake success.

## 8. Intent

- B01 correctly routed a raw Profile URL to Research, then failed in the provider layer.
- B03 and B06 retained their selected workspace objects but ended in visible send errors after the full 150-second limits; no Turn result was observable.
- B04 recognized `CONTENT_CREATE` but lost the selected strategy/content-opportunity reference.
- B05 routed and executed refinement, created V12, but changed neither title nor body while declaring success.

## 9. Material

- Profile normalization passed for B01, D01, and E01.
- Note normalization no longer produced `REFERENCE_CONTEXT_MISSING` for D02/E02, but those cases were routed to publication review.
- D03 entered Research with three intact Profile URLs, but current UI/Trace could not prove that all three reached the tool layer. It is UNVERIFIED, not PASS.

## 10. Context

C02 and C03 resolved Draft 2625; C03 kept Conversation #1603 across the second instruction and actually shortened the draft on the second turn. C01 still treated “这篇” as missing despite the selected Draft. C09 correctly asked for an object in an empty workspace, although the UI reduced the missing field to “必要信息”.

## 11. Research

D01 and E01 reached `RESEARCH / EXECUTE_PLAN`, proving current-turn Profile normalization, but ended `FAILED / PROVIDER_NOT_CONFIGURED`. D01's final Research status is FAILED. E02 was intent-misrouted. E05 never performed either requested account study and repeatedly requested `research_artifact_ref`.

## 12. Strategy

G01 waited the full 150 seconds and ended in a visible send error with no strategy artifact. G03 passed the functional grounding boundary by requesting Research context instead of inventing a strategy; its field-level UX remains poor.

## 13. Draft

H01 recognized `CONTENT_CREATE` but rejected both the selected strategy and content opportunity as `REFERENCE_CONTEXT_MISSING`, so no draft was created.

## 14. Revision

- B05 and C02 created new Draft versions without changing title or body, while reporting completion.
- C03's first turn was another no-op success, but its second same-conversation turn changed the body and satisfied the context-resume objective.
- J01: Workflow Execution PASS; Revision Fidelity UNVERIFIED; Testability FAIL; overall UNVERIFIED. Network evidence showed a changed title and unchanged body, but the ordinary business UI did not expose a body comparison.
- J06 confused instruction ambiguity with missing object context.

## 15. Memory

K01 failed. The preference statement was answered with the generic greeting; the next turn requested `opportunity_ref` instead of generating a title that respected the stated preference.

## 16. Pending Resume

L02 entered Pending correctly on turn one. The Profile URL on turn two became `QUERY_PROFILE / QUERY`, not resumed Research, and failed with `CONTROL_QUERY_HANDLER_UNAVAILABLE`.

## 17. Publication Review

B06 timed out at the full 150-second limit. N05 recognized `POST_PUBLISH_REVIEW`, but even with Published Note 592 / actual V2 selected, returned `这篇: REFERENCE_CONTEXT_MISSING`. No case proved correct V2 review execution.

## 18. Fake Success

Seven cases contained fake-success behavior: A03, A04, A05, B05, C02, C03, and K01. Fake Success Rate: **23.33%**. C03 remains an overall PASS for its second-turn resume objective, but its first turn is still counted as a no-op success.

## 19. Latency

- Average: 22.119 seconds
- Median: 4.491 seconds
- P95 (nearest rank): 150.512 seconds
- Min / Max: 2.203 / 150.519 seconds
- Protocol-limit failures: B03, B06, G01. Each was allowed its full 150-second category window.

## 20. Trace Observability

No evaluated case had a correlated product Trace. Business responses exposed string `wfr_*` run references, while the Trace console remained on unrelated numeric Run #1185 (`DemoDeveloperTraceWorkflow`). Tool Selection is therefore UNKNOWN for all 30 cases. Fixed Workflow tool calls were not re-labelled as agent-selected tools.

## 21. Critical Root-Cause Clusters

1. Generic `GENERAL_CHAT` behavior swallows capability and memory statements.
2. Workspace references are not reliably authoritative for Strategy, Draft pronouns, and Published Note pronouns.
3. Research material normalization is active, but the XHS collection provider is unavailable in the current runtime.
4. External Note analysis is routed to `POST_PUBLISH_REVIEW` rather than Research.
5. Strategy and publication-review requests can remain unresolved until the frontend exposes a send failure at 150 seconds.
6. Pending Research resume is reclassified as `QUERY_PROFILE` and hits an unavailable handler.
7. Revision Workflow can persist a new version and return SUCCESS without a content change.
8. Trace UI cannot correlate current business Workflow run references.

These are black-box clusters only; no database or source-level RCA was performed in this phase.

## 22. Baseline v1 vs v1.1 Differences

| Metric | v1 | v1.1 |
|---|---:|---:|
| PASS | 6 | 4 |
| FAIL | 24 | 24 |
| BLOCKED | 0 | 0 |
| UNVERIFIED | 0 | 2 |
| Executed Pass Rate | 20.00% | 13.33% |
| Material Extraction Accuracy (all-case denominator) | 0.00% | 20.00% |
| Fake Success Count | 3 | 7 |

The important improvement is that real Profile/Note URLs are now normalized instead of rejected as missing context. That exposed downstream failures: Provider configuration for Profile Research and intent misrouting for Note Research. B05/C02 also revealed no-op revision success in this snapshot. D03 and J01 moved to UNVERIFIED under the stricter evidence rules.

## 23. Frozen Before Metrics for Phase B

| Metric | Frozen value |
|---|---:|
| Case Count | 30 |
| Executed Pass Rate | 0.1333 |
| Intent Accuracy | 0.5667 |
| Material Extraction Accuracy | 0.2000 |
| Context Resolution Accuracy | 0.2000 |
| Workflow Routing Accuracy | 0.6333 |
| Final Action Completion | 0.1667 |
| Average Response Quality | 1.4000 |
| Fake Success Count / Rate | 7 / 0.2333 |
| Tool Selection UNKNOWN | 30 |

Every metric uses all 30 cases as its denominator. UNKNOWN is reported and penalizes the pass ratio instead of being excluded.

## 24. Git

No product code, Prompt, Intent, Resolver, Handler, Workflow, Tool, Provider, Frontend, dependency, or migration was modified. No `git add`, commit, reset, restore, clean, or stash was executed. The pre-existing dirty worktree was preserved.

This evaluation created only the three v1.1 baseline deliverables. Required UI execution created ordinary application records and advanced Draft 2625 from V11 to V16; there were no direct SQL/repository writes.

**Phase A.2 = COMPLETE / PRE-MIGRATION CURRENT SNAPSHOT BASELINE FROZEN**

Phase B was not started, and Pydantic AI was not installed.
