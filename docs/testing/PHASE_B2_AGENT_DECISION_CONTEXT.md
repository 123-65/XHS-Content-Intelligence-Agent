# Phase B2 Agent Decision Context

## Result

Phase B2 now uses one server-built decision projection before Pydantic AI tool selection:

`CanonicalTurnContext → Tool Capability / Eligibility Policy → LLM Semantic Selection → Workflow Validation`

The change does not restore the legacy 12-Intent Router, add an Intent enum, alter the five Workflow responsibilities, or add a database migration.

## CanonicalTurnContext

The runtime-only contract contains current material type/count/provenance, verified Workspace and recent object types, verified resumable Pending state, and candidate Workflow tools. It contains no API keys, cookies, secrets, unverified client refs, raw URLs, or full Artifact bodies. The same object is consumed by runtime instructions, `FilteredToolset`, and the final objective tool guard.

## Material Provenance

`CurrentTurnMaterialNormalizer` now preserves `CURRENT_TEXT`, `EXPLICIT_MATERIAL`, and `BOTH`. If one URL occurs in both text and the Material Panel, it remains one canonical material with `source=BOTH`; Provider input remains deduplicated.

## Tool Capability Registry

| Tool | Current material capability | Verified context capability |
|---|---|---|
| `run_research` | External XHS Profile / Note | May bootstrap without material |
| `run_content_strategy` | none | Research Artifact |
| `run_content_creation` | none | Opportunity with verified Strategy lineage |
| `run_content_refinement` | none | Draft |
| `run_post_publish_review` | none | PublishedNote |

This is input compatibility, not intent classification. When several compatible tools exist, the LLM still uses the latest user text and conversation history to choose among them.

## Eligibility Candidate Set and Current Turn Authority

- `CONVERSATION` exposes zero Workflow tools.
- `BUSINESS_ACTION` exposes only tools allowed by the capability policy.
- Unconsumed current-turn materials take authority over stale Workspace/Recent objects.
- With no current material, verified Workspace/Recent objects add compatible candidates; `run_research` remains available as the missing-material bootstrap.
- A verified Research Pending continuation whose required material is satisfied exposes only `run_research`.

The final `_validate_tool_selection` no longer parses capability, greeting, preference, title, or revision keywords. It only rejects objective eligibility, material-capability, or Pending-workflow contradictions.

## Pending Singleton Filtering

Pending continuation is exposed only after read-only validation of account ownership, `RESEARCH_V1` workflow type, `WAITING_USER` status, non-null Pending interaction, exact checkpoint version, and required-field compatibility. It resumes through the persisted run/checkpoint and does not start a second run.

## Model-visible Context

The model receives only material type/count/source, trusted object types, Pending summary, and candidate tool names. Raw URLs remain in deps and Workflow payloads and are no longer duplicated into runtime instructions.

## D03 Before / After

Before this change, D03 could enter Research but UI/Trace could not prove all three Profile URLs reached the tool layer, while BUSINESS_ACTION exposed all five Workflow tools.

After this change, headed Edge submitted D03 through the visible Material Panel:

- Network materials: 3 Profile URLs;
- Canonical context: `EXTERNAL_XHS_PROFILE × 3`, `EXPLICIT_MATERIAL`;
- eligible tools: only `run_research`;
- selected tool: `run_research` without a corrective retry;
- Workflow: `RESEARCH_V1`, `START`, `PARTIAL_SUCCESS`;
- Workflow input: 3 distinct Profile URL hashes;
- collected Account refs: 3 distinct refs;
- all sources: `XHS_MCP / xiaohongshu_mcp / is_mock=false`;
- Research Artifact: `3038`;
- run: `wfr_30289cbccdd645b1a2f392588a76b207`.

## Model Switch Verification

- Old model: `qwen3.8-flash`
- New model: `qwen3.7-flash-2026-07-15`
- Main model remains `LLM_MODEL=qwen3.8-2.4t-a95b`.
- ExecutionGate real call “你有记忆吗”: `CONVERSATION / MEMORY_QUESTION`; PromptRunLog `2445`, structured `SUCCESS`, `is_mock=false`, new model.
- D03 ExecutionGate: PromptRunLog `2446`, `SUCCESS`, `is_mock=false`, new model.
- D03 Research Analysis: PromptRunLog `2447`, structured `SUCCESS`, `is_mock=false`, new model.
- D03 Pydantic AI tool calling selected `run_research` from the singleton candidate set.
- No fallback to `qwen3.8-flash` was observed in the new calls.

## Verification

- Targeted decision-context/entry regression: `119 passed`.
- Full backend regression: `783 passed / 3 skipped`.
- Migration: `0`.

## Continued B2 Real UI Verification

Headed Edge continued from the verified D03 state without replaying R01/R02/R03:

| Case | Verified candidate tools | LLM-selected tool | Workflow result | Artifact evidence |
|---|---|---|---|---|
| B03, Research to Strategy | `run_research`, `run_content_strategy` | `run_content_strategy` | `CONTENT_STRATEGY_V1 / SUCCESS` | Strategy `136`; Opportunities `4317`, `4318`, `4319` |
| B04, Opportunity to Draft | `run_research`, `run_content_creation` | `run_content_creation` | `CONTENT_CREATION_V1 / PARTIAL_SUCCESS` | Draft `2697`; warning `DRAFT_REVIEW_FAILED` |
| B06, PublishedNote to Review | `run_research`, `run_post_publish_review` | `run_post_publish_review` | `POST_PUBLISH_REVIEW_V1 / PARTIAL_SUCCESS` | Review `2155`; public/private metrics remained `UNKNOWN` |

All three turns were classified as `BUSINESS_ACTION`. Their current-turn material facts were empty, so eligibility was derived from verified Workspace/Recent business objects rather than keyword routing. The LLM retained semantic choice between the bootstrap Research tool and the single context-compatible downstream tool.

Prompt evidence for these turns was non-mock and reported no provider fallback. ExecutionGate logs `2448`, `2449`, `2451`, and `2454`, plus Post Review log `2455`, used `qwen3.7-flash-2026-07-15`. Strategy and Draft generation/review continued to use the unchanged main model `qwen3.8-2.4t-a95b`. No new call used or fell back to `qwen3.8-flash`.

The two `PARTIAL_SUCCESS` results are not tool-selection failures: B04 persisted the Draft before its review warning, while B06 completed the review with unavailable public/private metrics represented as unknown. No database migration, B3 work, or repeat Research collection was performed.
