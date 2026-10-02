# Phase B1 Conversational Agent Runtime

## Before

Canonical `POST /api/agent/turns` previously entered `ControlAgentSemanticLayer`, mapped text to one of twelve intents, passed through `DeterministicPlanner`, and then selected a handler or workflow. Conversation messages were persisted, but the canonical control path did not reconstruct them as model history.

## After

The default canonical path is now:

`CurrentTurnMaterialNormalizer → ConversationHistoryLoader + TrustedWorkspaceSnapshot + current turn → Pydantic AI Agent → direct response or one high-level workflow tool → AgentRuntime → existing Workflow → existing Domain Tools`.

`UnifiedAgentService` remains responsible for request fingerprinting, idempotency, conversation/account validation, workspace ownership validation, USER/ASSISTANT persistence, and the public response contract. `ConversationalAgentService` owns only the new conversational control plane.

## Pydantic AI boundary

The top-level agent uses `pydantic-ai==2.51.0` with the existing Alibaba OpenAI-compatible endpoint, the existing API key/base URL, `LLM_CONTROL_SEMANTIC_MODEL` or `qwen3.8-flash`, thinking disabled, and a 30-second timeout. It does not replace `LLMClient` inside Research, Strategy, Draft, Revision, or Review workflows. No Pydantic Graph, Memory, Evals, or separate persistence store is used by application code.

## Conversation history

`ConversationHistoryLoader` reads at most 20 server-side PostgreSQL messages before the just-saved current USER message. USER visible text becomes `UserPromptPart`; ASSISTANT visible text becomes `TextPart`; message order is preserved. The current turn is supplied only as `user_prompt`, so it is not duplicated. Client-uploaded message history is not accepted.

## Trusted workspace and materials

Workspace refs first pass the existing `UnifiedAgentService._workspace()` account-ownership checks. The agent sees a compact typed projection with object type, canonical ref, and a minimal summary—not full artifact bodies. When only an Opportunity is selected, its Strategy is derived through persisted repository lineage and accepted only when the Strategy owner matches the already validated Opportunity owner.

Current XHS URLs continue to be normalized before agent execution. High-level tools prefer current-turn material and may fall back only to recent authorized material reconstructed from the same conversation.

## Five high-level workflow tools

The model can call only:

1. `run_research(goal)`
2. `run_content_strategy(goal)`
3. `run_content_creation(goal)`
4. `run_content_refinement(instruction)`
5. `run_post_publish_review(goal)`

Account, conversation, artifact, draft, publication, and URL identity never appear in model tool parameters. Each adapter reads trusted dependencies, constructs an existing Workflow input, invokes the existing `AgentRuntime`, and returns `WorkflowToolOutcome`. The existing 17 Domain Tools remain private to deterministic Workflow implementations.

## Status mapping

`TurnExecutionLedger` records every selected high-level tool, Workflow, run ref, status, artifact refs, and safe error code. `ConversationResponseMapper` treats the ledger as authoritative: `FAILED` and `WAITING_USER` cannot be overwritten by optimistic model prose. With no tool call, structured `ConversationResponse` maps direct conversation to the existing `AgentTurnResult` contract. Unsupported requests remain successful conversational responses with `UNSUPPORTED_CAPABILITY`, not executable plans.

## Legacy rollback

`AGENT_ENTRY_MODE=conversation_v2` is the default. Setting it to `legacy` restores the previous semantic/planner/orchestrator path without changing the endpoint or frontend contract. Legacy code is retained for migration comparison and rollback.
