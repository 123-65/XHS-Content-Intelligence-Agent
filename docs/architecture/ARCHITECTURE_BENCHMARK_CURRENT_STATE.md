# Architecture Benchmark — Current State

> Phase A read-only audit. Snapshot date: 2026-09-28. This document records the checked-out implementation; it does not propose a new architecture. `KEEP / ADAPT / REMOVE / UNKNOWN` in section 14 are mappings against the supplied frozen target architecture, not implementation work performed in this phase.

## 1. Current Request Path

### Canonical `POST /api/agent/turns` path

1. Frontend `AgentChatView.send()` calls `agentChat.sendNewTurn(text, materials)`; `useAgentChatStore.sendNewTurn()` adds `conversation_id`, `account_ref`, optional `workspace_selection`, typed `materials`, and a new `client_request_id`; `sendAgentTurn()` posts to `/api/agent/turns`. Evidence: `frontend/src/views/AgentChatView.vue::send`, `frontend/src/stores/agentChat.ts::sendNewTurn/dispatch`, `frontend/src/api/unifiedAgent.ts::sendAgentTurn`.
2. FastAPI validates `AgentTurnRequest` and calls `UnifiedAgentService.handle_turn()`. Evidence: `backend/app/api/unified_agent.py::create_agent_turn`, `backend/app/schemas/unified_agent.py::AgentTurnRequest`.
3. `handle_turn()` fingerprints the complete request and reserves an `agent_turn` idempotency row. A matching `(account_ref, client_request_id)` is replayed only if the fingerprint matches. Evidence: `backend/app/services/unified_agent_sev.py::UnifiedAgentService.handle_turn/_replay`, `backend/app/repositories/agent_turn_repo.py::AgentTurnRepository`, `backend/app/models/agent_turn.py::AgentTurn`.
4. `_conversation()` creates or ownership-checks an active conversation. `CurrentTurnMaterialNormalizer.normalize()` deterministically extracts supported XHS Profile/Note URLs from raw text and merges them with typed `materials`. `_workspace()` converts client IDs to ownership-checked `TrustedContextRef`; `_execution_context()` creates the server-owned collection/evidence scopes. The user message is persisted before orchestration. Evidence: `backend/app/services/unified_agent_sev.py::UnifiedAgentService._conversation/_workspace/_execution_context/handle_turn`, `backend/app/agent/control/current_turn_materials.py::CurrentTurnMaterialNormalizer`, `backend/app/services/agent_conversation_sev.py::AgentConversationService`, `backend/app/repositories/agent_conversation_repo.py::AgentConversationRepository.add_message`.
5. `_orchestrator()` wires `ControlAgentSemanticLayer(LLMClient)`, `ContextResolver`, `DeterministicPlanner`, `PlanExecutionService`, `AgentRuntime`, and `ConversationTurnContextOwner`. No `action_handlers` are supplied by the production composition root. Evidence: `backend/app/services/unified_agent_sev.py::UnifiedAgentService._orchestrator`.
6. `AgentTurnOrchestrator.handle_turn()` loads structured conversation state, calls the semantic LLM on the current turn only, overlays server-authorized material URLs, applies the pre-Workflow Research material continuation rule, removes external-material pseudo-references, and calls `ContextResolver.resolve()`. Evidence: `backend/app/agent/control/orchestrator.py::AgentTurnOrchestrator.handle_turn/_semantic_turn_text/_resume_preworkflow_research_material/_exclude_external_material_references`, `backend/app/agent/control/semantic_layer.py::ControlAgentSemanticLayer.understand`, `backend/app/agent/context/resolver.py::ContextResolver.resolve`.
7. If `active_pending_run_ref` exists, `_maybe_resume()` loads the durable run and may call `AgentRuntime.resume(WorkflowResumeRequest)`. Otherwise `DeterministicPlanner.plan()` maps Intent → RuntimeAction and, for the five business intents, Intent → Skill → Workflow plus a typed Workflow input. Evidence: `backend/app/agent/control/orchestrator.py::AgentTurnOrchestrator._maybe_resume`, `backend/app/agent/control/resume_builders.py::build_resume_input`, `backend/app/agent/planning/planner.py::DeterministicPlanner.plan`, `backend/app/agent/planning/input_builders.py::build_workflow_input`, `backend/app/agent/skills/registry.py::INTENT_TO_SKILL`.
8. Non-Workflow actions end in `_handle_control()`. Workflow actions go through `PlanExecutionService.execute()` → `AgentRuntime.start()` → `build_workflow_handler()` → the concrete Workflow → Workflow-owned calls to `build_tool_handler()` → Domain Tool → service/repository/provider. Evidence: `backend/app/agent/control/orchestrator.py::_handle_control`, `backend/app/agent/planning/execution_service.py::PlanExecutionService.execute`, `backend/app/runtime/agent_runtime.py::AgentRuntime.start`, `backend/app/agent/workflows/implementation_registry.py::build_workflow_handler`, `backend/app/agent/tools/implementation_registry.py::build_tool_handler`.
9. `AgentRuntime` creates/claims/checkpoints the durable run; artifact writes use `DurableOperationExecutor` when runtime identity is present. The orchestrator copies result identities into `AgentConversation.current_state`; the service completes the idempotent Turn row and persists the assistant message. Evidence: `backend/app/runtime/agent_runtime.py::AgentRuntime.start/_save_result`, `backend/app/services/workflow_run_sev.py::WorkflowRunService.create_run/mark_running/save_checkpoint`, `backend/app/runtime/durable_operation.py::DurableOperationExecutor`, `backend/app/agent/control/orchestrator.py::_apply_runtime_results/_update_recent`, `backend/app/services/unified_agent_sev.py::handle_turn`.

### Named components requested by the audit

| Concern | Current owner and actual role |
|---|---|
| `_handle_control` | `backend/app/agent/control/orchestrator.py::AgentTurnOrchestrator._handle_control`; hardcoded RESPOND, unbound QUERY, confirmation-only update stubs, and non-mutating cancel acknowledgement. |
| Semantic Frame / Intent classifier | `backend/app/agent/control/semantic_layer.py::ControlAgentSemanticLayer.understand` uses an LLM to produce `TaskSemanticFrame`; the 12-value enum is `backend/app/agent/schemas/semantic.py::Intent`. |
| RuntimeAction | `backend/app/agent/schemas/execution.py::RuntimeAction`; selected deterministically in `backend/app/agent/planning/planner.py::DeterministicPlanner._action`. |
| `action_handlers` | Optional map in `AgentTurnOrchestrator.__init__`; production `UnifiedAgentService._orchestrator()` supplies none. |
| Planner | `backend/app/agent/planning/planner.py::DeterministicPlanner`; no LLM, fixed registries and typed builders. |
| Resolver | `backend/app/agent/context/resolver.py::ContextResolver`; identity/ownership lookup through `RepositoryContextIdentityReader`. |
| Pending | `backend/app/agent/schemas/interaction.py::PendingInteraction`; stored either in pre-run conversation state or durable Workflow state/run. |
| Resume | `AgentTurnOrchestrator._maybe_resume` → `backend/app/runtime/workflow_resume.py::WorkflowResumeService.resume` → concrete `Workflow.resume`. |
| Workspace selection | `WorkspaceSelectionRequest` → `UnifiedAgentService._workspace()` → `StructuredContext` → `ContextResolver`; details in section 4. |

## 2. Intent Matrix

All semantic rows are produced by `ControlAgentSemanticLayer.understand()` using `TaskSemanticFrame`. Action eligibility is fixed by `backend/app/agent/intents.py::INTENT_TO_ALLOWED_RUNTIME_ACTIONS`; production has no installed control `action_handlers`.

| Intent | RuntimeAction | Handler? | Planner? | Workflow? | Tool? | Fallback / final status | Audit mark |
|---|---|---:|---:|---|---|---|---|
| `GENERAL_CHAT` | `RESPOND` | No production handler | Yes, action only | No | No | `_handle_control` returns fixed greeting and `SUCCESS` | `HARDCODED`, `ACTIVE` |
| `RESEARCH` | `EXECUTE_PLAN` or `CLARIFY` | Workflow handler | Yes | `RESEARCH_V1` | Fixed allowlist | Run result; missing material → `WAITING_USER` | `ACTIVE` |
| `CONTENT_STRATEGY` | `EXECUTE_PLAN` or `CLARIFY` | Workflow handler | Yes | `CONTENT_STRATEGY_V1` | Fixed allowlist | Missing Research → `WAITING_USER` | `ACTIVE` |
| `CONTENT_CREATE` | `EXECUTE_PLAN` or `CLARIFY` | Workflow handler | Yes | `CONTENT_CREATION_V1` | Fixed allowlist | Missing Strategy/Opportunity → `WAITING_USER` | `ACTIVE` |
| `CONTENT_REFINE` | `EXECUTE_PLAN` or `CLARIFY` | Workflow handler | Yes | `CONTENT_REFINEMENT_V1` | Fixed allowlist | Missing Draft/feedback → `WAITING_USER` | `ACTIVE` |
| `POST_PUBLISH_REVIEW` | `EXECUTE_PLAN` or `CLARIFY` | Workflow handler | Yes | `POST_PUBLISH_REVIEW_V1` | Fixed allowlist | Missing PublishedNote → `WAITING_USER` | `ACTIVE` |
| `QUERY_PROFILE` | `QUERY` | None | Yes, action only | No | No | `CONTROL_QUERY_HANDLER_UNAVAILABLE`, `FAILED` | `UNIMPLEMENTED`, `ACTIVE` classifier |
| `UPDATE_PROFILE` | `CONFIRM` | None | Yes, action only | No | No | confirmation Pending, `WAITING_USER`; no confirmed-command continuation | `UNIMPLEMENTED`, `HARDCODED` |
| `QUERY_HISTORY` | `QUERY` | None | Yes, action only | No | No | `CONTROL_QUERY_HANDLER_UNAVAILABLE`, `FAILED` | `UNIMPLEMENTED`, `ACTIVE` classifier |
| `UPDATE_STRATEGY` | `CONFIRM` | None | Yes, action only | No | No | confirmation Pending, `WAITING_USER`; no confirmed-command continuation | `UNIMPLEMENTED`, `HARDCODED` |
| `CANCEL_TASK` | `CANCEL` | Hardcoded acknowledgement only | Yes, action only | No | No | does not mutate Runtime; warning, `PENDING` | `UNIMPLEMENTED`, `HARDCODED` |
| `UNKNOWN` | `CLARIFY` | Hardcoded clarification | Yes | No | No | `TURN_CLARIFICATION`, `WAITING_USER` | `HARDCODED`, `ACTIVE` |

Evidence: `backend/app/agent/schemas/semantic.py::Intent/TaskSemanticFrame`; `backend/app/agent/intents.py::BUSINESS_INTENTS/INTENT_TO_ALLOWED_RUNTIME_ACTIONS`; `backend/app/agent/planning/planner.py::DeterministicPlanner.plan/_action`; `backend/app/agent/control/orchestrator.py::AgentTurnOrchestrator._handle_control/_clarification`; `backend/app/agent/skills/registry.py::INTENT_TO_SKILL`; `backend/app/agent/workflows/implementation_registry.py::WORKFLOW_HANDLER_REGISTRY`.

The older, still-registered `/agent/chat/execute-workflow` owns a second Intent/Router/Planner/dispatch stack under `backend/app/agent/product_entry/*`; it is not in the `/api/agent/turns` chain. Evidence: `backend/app/main.py::create_app`, `backend/app/api/agent_chat.py::execute_workflow_agent_chat`, `backend/app/agent/product_entry/chat_service.py::AgentChatWorkflowExecuteService.execute_workflow` (`DUPLICATED`).

## 3. Conversation History

| Question | Current code fact |
|---|---|
| Does every model call receive full recent conversation? | No. The canonical Turn path never loads `AgentConversationMessage` rows for model input. `ControlAgentSemanticLayer` receives only `_semantic_turn_text(turn)`. |
| What does a model receive instead? | Control Semantic receives current text plus counts/placeholders for typed current-turn URLs. Business LLM calls receive Workflow-prepared growth/artifact/evidence/metric payloads, constraints, and stable identities—not chat messages. |
| Where is history trimmed? | UI history paging uses 40 messages; repository paging applies `limit`. The legacy `/agent/chat/execute-workflow` path loads 20 by default in `prepare_agent_request()`. The canonical `/api/agent/turns` model path has no message-history trimming because it does not load messages at all. Structured conversation references are trimmed independently to 20 refs and 5 opportunity collections. |
| Which LLM calls know no previous Turn text? | Control Semantic, Research Analysis, Strategy, Draft, Draft Review, Draft Revision, and Post-Publish Review on the canonical path. They may know derived structured identities/facts from `current_state` or Workflow inputs, but not earlier message text. |
| Does `GENERAL_CHAT` really call an LLM? | Yes only for classification into `GENERAL_CHAT`; the reply itself is not generated by an LLM. `_handle_control()` returns the fixed greeting. |
| Does normal conversation have a separate system prompt? | No generative conversation prompt exists. The only prompt used on a normal-chat Turn is the Control Semantic system prompt; the final response is hardcoded. |

Storage and read evidence: `backend/app/models/agent_conversation.py::AgentConversation/AgentConversationMessage`; `backend/app/models/agent_turn.py::AgentTurn`; `backend/app/repositories/agent_conversation_repo.py::add_message/list_messages`; `backend/app/services/agent_conversation_sev.py::prepare_agent_request` (legacy path only); `frontend/src/stores/agentChat.ts::loadRecentConversation/loadEarlierMessages`.

Canonical non-injection evidence: `backend/app/services/unified_agent_sev.py::handle_turn`; `backend/app/agent/control/orchestrator.py::_semantic_turn_text`; `backend/app/agent/control/prompts.py::build_semantic_user_prompt`; `backend/app/agent/control/conversation_context.py::ConversationTurnContextOwner.load/save`.

## 4. Workspace Context

The frontend producer is `ArtifactDetailShell.selectAndReturn()` or an explicit list/detail action. The carrier is Pinia `workspace_selection`, then `AgentTurnRequest.workspace_selection`. The backend turns each ID into an ownership-checked `TrustedContextRef`. The resolver uses flat references with priority 2. Evidence: `frontend/src/components/ArtifactDetailShell.vue::selectAndReturn`, `frontend/src/stores/agentChat.ts::setWorkspaceSelection/sendNewTurn`, `backend/app/schemas/unified_agent.py::WorkspaceSelectionRequest`, `backend/app/services/unified_agent_sev.py::_workspace`, `backend/app/agent/context/resolver.py::ContextResolver`.

| Object | Producer | Carrier | Consumer | Lost at / current boundary |
|---|---|---|---|---|
| Research | `ResearchDetailView` selects `{research_ref}` | Pinia → request DTO → `StructuredContext.references` | Resolver → `_strategy()` Workflow input builder | Not lost when selected and owned; semantic prompt itself never sees the ID. Evidence: `frontend/src/views/agent/ResearchDetailView.vue`, `backend/app/agent/planning/input_builders.py::_strategy`. |
| Strategy | `StrategyDetailView` can select `{strategy_ref}` | Same flat-ref carrier | Resolver can resolve `ACTIVE_STRATEGY`; `_creation()` can consume one Strategy | A Strategy alone is insufficient for creation because `_creation()` also requires one Opportunity. Evidence: `frontend/src/views/agent/StrategyDetailView.vue`, `backend/app/agent/planning/input_builders.py::_creation`. |
| Draft | `DraftListView` or `DraftDetailView` selects `{draft_ref}` | Same flat-ref carrier | Resolver → `_refinement()` → `CONTENT_REFINEMENT_V1` | Works when the selection remains in the Pinia store and semantic intent is refinement. Without selected/recent Draft identity, “这篇” resolves to `REFERENCE_CONTEXT_MISSING`. Evidence: `frontend/src/views/agent/DraftListView.vue`, `frontend/src/views/agent/DraftDetailView.vue`, `backend/app/agent/context/resolver.py::_resolve_required_context/_deictic`, `backend/app/agent/planning/input_builders.py::_refinement`. |
| PublishedNote | `PublicationDetailView.startReview()` selects `{published_note_ref}` | Same flat-ref carrier | Resolver → `_post_publish()` → review Workflow | Not copied into recent context by `_update_recent`; therefore “复盘这篇” works with explicit workspace selection, but otherwise requires a semantic temporal/latest reference that the reader can resolve. Evidence: `frontend/src/views/agent/PublicationDetailView.vue::startReview`, `backend/app/agent/control/orchestrator.py::_update_recent`, `backend/app/agent/planning/input_builders.py::_post_publish`. |
| Review | Review list/detail is read-only navigation; no `review_ref` exists in `WorkspaceSelectionRequest` | None | No Resolver object type/input-builder consumer | Lost at frontend/DTO boundary. `ResolvedObjectType` also has no Review member. Evidence: `frontend/src/views/agent/ReviewListView.vue`, `backend/app/schemas/unified_agent.py::WorkspaceSelectionRequest`, `backend/app/agent/context/contracts.py::ResolvedObjectType`. |

Additional Strategy → Draft break: `StrategyDetailView.choose()` sends only `{opportunity_ref}`. `_workspace()` preserves only that flat Opportunity ref and does not carry its Strategy lineage as an `OpportunityCollection`; `_creation()` requires both Opportunity and Strategy. The resolver can derive Strategy only from an existing structured opportunity collection, not by repository lineage lookup at this stage. Evidence: `frontend/src/views/agent/StrategyDetailView.vue::choose`, `backend/app/services/unified_agent_sev.py::_workspace`, `backend/app/agent/context/resolver.py::_set_strategy_for_opportunity`, `backend/app/agent/planning/input_builders.py::_creation`.

Why explicit Draft modification can work while deictic phrases fail: explicit selection supplies a trusted ID before planning. Phrases such as “这篇”, “这个策略”, “刚才的策略”, and “复盘这篇” depend on (a) the semantic LLM emitting the matching `SemanticReferenceType`, and (b) a matching flat reference/opportunity collection being present in workspace or `recent_context`. Chat message text is never searched. Missing identity produces `REFERENCE_CONTEXT_MISSING`; a Strategy without Opportunity instead produces planner missing input. Evidence: `backend/app/agent/control/semantic_layer.py::understand`, `backend/app/agent/context/resolver.py::_resolve_one/_deictic`, `backend/app/agent/control/conversation_context.py::load`, `backend/app/agent/planning/input_builders.py`.

## 5. Material Flow

Current raw-text path:

`AgentChatView.draftText` → request `text` → `UnifiedAgentService.handle_turn()` → `CurrentTurnMaterialNormalizer.normalize(text, materials)` → `AgentTurnMaterials(note_urls, profile_urls)` → `AgentTurnInput` + `CollectionAccessScope` → ephemeral `CurrentTurnMaterialCandidate` and authoritative frame URL fields → Research input/Resume input.

Evidence: `frontend/src/views/AgentChatView.vue::send`; `backend/app/services/unified_agent_sev.py::handle_turn/_execution_context`; `backend/app/agent/control/current_turn_materials.py::CurrentTurnMaterialNormalizer`; `backend/app/agent/control/orchestrator.py::_current_turn_materials/_authoritative_current_turn_note_urls`; `backend/app/agent/planning/input_builders.py::_research`; `backend/app/agent/control/resume_builders.py::_research`.

Current contracts:

- URL extractor and deterministic material normalizer: present in `CurrentTurnMaterialNormalizer._urls_in_source_order/_classify`.
- Typed request material DTO: present as `AgentTurnMaterials` in `backend/app/schemas/unified_agent.py`.
- Resolver-side typed material: present as `CurrentTurnMaterialCandidate`; it is not a `SemanticReference` and never claims a persisted DB ID. Evidence: `backend/app/agent/context/contracts.py::CurrentTurnMaterialCandidate/MaterialSatisfiedReference`.
- Supported backend raw-text forms are only `xiaohongshu.com` or `www.xiaohongshu.com` with `/user/profile/...` or `/explore/...`. `xhslink.com` and `/discovery/item/...` are accepted by the frontend Note validator but not by the backend raw-text normalizer or `_current_turn_materials`. Evidence: `frontend/src/views/AgentChatView.vue::isXhsNoteUrl`, `backend/app/agent/control/current_turn_materials.py::_classify`, `backend/app/agent/control/orchestrator.py::_current_turn_materials`.

Why URLs reached the Reference Resolver historically: Control Semantic could reconstruct raw URLs and emit reference objects. Current code masks typed URLs from the semantic text and `_exclude_external_material_references()` removes Research material-like references before resolution. Evidence: `backend/app/agent/control/orchestrator.py::_semantic_turn_text/_exclude_external_material_references`; historical defect record: `docs/testing/REAL_E2E_ACCEPTANCE_REPORT.md` (DEFECT-001/002 and E2E-005 narrative).

Historical/unit E2E construction audit:

- Several orchestration tests construct `AgentTurnInput(... note_urls/profile_urls=...)`, `TaskSemanticFrame(... note_urls=...)`, `CurrentTurnMaterialCandidate`, or `CollectionAccessScope` directly. This verifies downstream behavior but bypasses browser raw text → HTTP DTO → normalizer. Evidence: `backend/tests/test_phase2_5d_agent_turn_orchestration.py::collection_context/note_collection_context` and its material/resume tests; `backend/tests/test_phase2_5b_context_resolver.py` direct `TaskSemanticFrame/SemanticReference` cases.
- A current API-level test covers raw text extraction through `UnifiedAgentService.handle_turn()`. Dedicated normalizer tests cover Profile, Note, Markdown, punctuation, merge, and dedupe. Evidence: `backend/tests/test_phase2_6a_unified_agent_api.py::test_service_normalizes_plain_chat_url_before_orchestrator_and_collection_scope`, `backend/tests/test_current_turn_material_normalizer.py`.
- The current supported full Profile/Note URL continuation is statically wired to resume. Therefore the blanket statement “帮我分析同行账号 → URL cannot Resume” is not a current-code invariant. The historical real-E2E breakpoint was invalid Semantic `note_urls` overriding/contaminating authorized typed materials; current `authoritative_note_urls or frame.note_urls` and `_resume_preworkflow_research_material()` close that path. Remaining code-visible failure cases include a new conversation/no shared `conversation_id`, backend-unsupported URL forms, or no valid material after normalization. Evidence: `backend/app/agent/control/orchestrator.py::handle_turn/_resume_preworkflow_research_material`; `docs/testing/REAL_E2E_ACCEPTANCE_REPORT.md` E2E-005 defect and fix record.

## 6. Tool Architecture

All descriptions and schemas come from `backend/app/agent/tools/registry.py::TOOL_REGISTRY`; names/effects come from `backend/app/agent/tools/definitions.py::ToolName/ToolEffect`; class bindings come from `backend/app/agent/tools/implementation_registry.py::TOOL_HANDLER_REGISTRY/build_tool_handler`.

| Tool | Description / schema source | Model calls it? | Planner calls it? | Workflow direct call | Domain implementation and lower owner | Real / fallback |
|---|---|---:|---:|---|---|---|
| `query_growth_context` | Registry; `QueryGrowthContextInput/Result` | No | No | All five | `QueryGrowthContextTool` → account/publication repositories | Real DB read; missing sections explicit |
| `query_artifact` | Registry; `QueryArtifactInput/ArtifactResult` | No | No | All five as needed | `QueryArtifactTool` → research/strategy/draft/publication repositories | Real DB read |
| `retrieve_research_evidence` | Registry; `RetrieveResearchEvidenceInput/EvidenceBundle` | No | No | Research/Create/Refine | `RetrieveResearchEvidenceTool` → `CompetitorReportRepository`, access scope | Real DB read; deny-all default |
| `query_post_publish_metrics` | Registry; typed metric contracts | No | No | Review | `QueryPostPublishMetricsTool` → `PublicationRepository`/`DraftRepository` | Real DB read; UNKNOWN metrics preserved |
| `collect_xhs_notes` | Registry; XHS contracts | No | No | Research/Review | `CollectXhsNotesTool` → `XhsCollectorService` or `PublishedNoteRefreshService` → `XiaohongshuMcpProvider` + import repositories | Real provider; explicit error/partial success, no mock fallback |
| `collect_xhs_accounts` | Registry; XHS contracts | No | No | Research | `CollectXhsAccountsTool` → `XhsCollectorService` → `XiaohongshuMcpProvider` + import repositories | Real provider; explicit error/partial success |
| `analyze_research` | Registry; semantic contracts | No | No | Research | `AnalyzeResearchTool` → `LLMStructuredCompetitorAnalyzer` → `LLMClient/provider` + grounding validator | Real LLM; no rule fallback |
| `generate_content_strategy` | Registry; semantic contracts | No | No | Strategy | `GenerateContentStrategyTool` → `ContentStrategyService.generate_semantic` → `LLMClient/provider` | Real LLM; explicit failure |
| `generate_draft` | Registry; semantic contracts | No | No | Creation | `GenerateDraftTool` → `DraftGenerationService.generate_semantic` → `LLMClient/provider` | Real LLM; explicit failure |
| `review_draft` | Registry; semantic contracts / `DraftReviewLLMResult` | No | No | Creation | `ReviewDraftTool` → `DraftReviewService.review_semantic` → `LLMClient/provider` | Real LLM; explicit failure |
| `revise_draft` | Registry; semantic contracts | No | No | Refinement | `ReviseDraftTool` → `DraftRevisionService.revise_semantic` → `LLMClient/provider` | Real LLM; explicit failure |
| `analyze_post_publish_review` | Registry; semantic contracts | No | No | Review | `AnalyzePostPublishReviewTool` → `PostPublishReviewService.review_semantic` → `LLMClient/provider` | Real LLM; explicit failure |
| `create_research_artifact` | Registry; artifact contracts | No | No | Research | `CreateResearchArtifactTool` → assembler + `CompetitorReportRepository` | Real transactional write |
| `create_content_strategy_artifact` | Registry; artifact contracts | No | No | Strategy | `CreateContentStrategyArtifactTool` → `ContentStrategyRepository` | Real transactional write |
| `create_draft_version` | Registry; artifact contracts | No | No | Creation/Refinement | `CreateDraftVersionTool` → `DraftRepository` | Real transactional/idempotent operation write |
| `create_post_publish_review_artifact` | Registry; artifact contracts | No | No | Review | `CreatePostPublishReviewArtifactTool` → `PublicationRepository` | Real transactional write |
| `create_strategy_candidate` | Registry; artifact contracts | No | No | Review | `CreateStrategyCandidateTool` → `PublicationRepository` | Real transactional write; remains `PROPOSED` |

Tool call sites are the concrete Workflow `_run()` methods and their `_call()` wrappers in `backend/app/agent/workflows/{research,content_strategy,content_creation,content_refinement,post_publish_review}.py`. Artifact transaction/idempotency behavior is in `backend/app/agent/tools/artifact_tools.py::ArtifactToolBase._run` and `backend/app/runtime/durable_operation.py::DurableOperationExecutor`.

**Selection fact:** the model does not receive tool schemas and does not freely choose a tool. Control Semantic chooses only a `TaskSemanticFrame`; `DeterministicPlanner` selects the Workflow from fixed Intent/Skill registries; each Workflow invokes a hardcoded ordered Tool list constrained by its allowlist. Actual chain: `LLM Intent → deterministic Planner → fixed Workflow → hardcoded Tool sequence`. Evidence: `backend/app/agent/control/prompts.py::SEMANTIC_SYSTEM_PROMPT` rule 7, `backend/app/agent/planning/planner.py::DeterministicPlanner`, `backend/app/agent/workflows/registry.py::WORKFLOW_REGISTRY`, concrete Workflow `_run()` methods.

## 7. Workflow Architecture

All five handlers are real and registered in `backend/app/agent/workflows/implementation_registry.py::WORKFLOW_HANDLER_REGISTRY`; all declare `resumable=True` in `backend/app/agent/workflows/registry.py::WORKFLOW_REGISTRY`.

| Workflow | Entry / required context | Deterministic steps and tools | Resume | Artifact output | Frozen target mapping |
|---|---|---|---|---|---|
| Research | `ResearchWorkflow.execute`; account, goal, at least URL/evidence | growth context → artifact context → account/note collection → evidence retrieval/adapter/gate → LLM analysis → artifact creation; 7-tool allowlist | `resume()` merges constraints/evidence and skips completed state | Research artifact ref | Direct `Workflow Tool` candidate: `RESEARCH_V1` |
| Content Strategy | `ContentStrategyWorkflow.execute`; account, goal, Research ref | growth context → Research query → LLM strategy → strategy artifact; 4 tools | `resume()` can fill Research ref | Strategy artifact + opportunity refs | Direct `Workflow Tool` candidate: `CONTENT_STRATEGY_V1` |
| Content Creation | `ContentCreationWorkflow.execute`; account, Strategy ref, Opportunity ref | growth context → Strategy/Opportunity query → evidence → LLM draft → Draft V1 → LLM review; 7 tools | `resume()` fills immutable missing identities | Draft root/version + review result (review not persisted here) | Direct `Workflow Tool` candidate: `CONTENT_CREATION_V1` |
| Content Refinement | `ContentRefinementWorkflow.execute`; account, Draft ref, feedback | Draft query → Opportunity query → evidence → LLM revision → append Draft version; 5 tools | `resume()` fills Draft/feedback, rejects root/base-version changes | Same Draft root, new version | Direct `Workflow Tool` candidate: `CONTENT_REFINEMENT_V1` |
| Post Publish Review | `PostPublishReviewWorkflow.execute`; account, PublishedNote ref, window | growth context → metrics → published Draft/Strategy/Opportunity → optional refresh → LLM review → review artifact → proposed candidates; 7 tools | `resume()` fills note/window without changing identity | Review artifact + candidate refs | Direct `Workflow Tool` candidate: `POST_PUBLISH_REVIEW_V1` |

Evidence for contracts and exact step IDs: `backend/app/agent/workflows/research.py::ResearchWorkflowInput/STEP_IDS/ResearchWorkflow`; `content_strategy.py::ContentStrategyWorkflowInput/STEP_IDS/ContentStrategyWorkflow`; `content_creation.py::ContentCreationWorkflowInput/STEP_IDS/ContentCreationWorkflow`; `content_refinement.py::ContentRefinementWorkflowInput/STEP_IDS/ContentRefinementWorkflow`; `post_publish_review.py::PostPublishReviewWorkflowInput/STEP_IDS/PostPublishReviewWorkflow`.

“Workflow Tool candidate” above means the existing Workflow already has a typed entry, typed result, registry identity, durable start/resume path, and a bounded tool allowlist. It does not mean such an adapter exists today; no current model-callable Workflow Tool registry is present.

## 8. Pending Resume

### Durable Workflow Pending

`PendingInteraction` contains `type`, `reason`, `required_fields`, `options`, `related_run_ref`, and `resume_token`. A Workflow WAITING state is stored both inside serialized Workflow state and the `workflow_run.pending_interaction` snapshot. `WorkflowRunService.save_checkpoint()` enforces that WAITING requires Pending and non-WAITING forbids it. Run identity is `run_ref`; optimistic identity is `checkpoint_version`; operation-level idempotency is stored by `workflow_operation`. Evidence: `backend/app/agent/schemas/interaction.py::PendingInteraction`; `backend/app/models/workflow_run.py::WorkflowRun`; `backend/app/models/workflow_operation.py::WorkflowOperation`; `backend/app/services/workflow_run_sev.py::WorkflowRunService.save_checkpoint`; `backend/app/runtime/workflow_resume.py::WorkflowResumeRequest/WorkflowResumeService._load_waiting`.

Structured E2E resumes because tests explicitly persist a WAITING run, Pending, checkpoint, and then send matching typed `new_input`/context or construct the semantic/material values directly. Evidence: `backend/tests/test_phase2_4b_cross_request_resume.py`, `backend/tests/test_phase2_5d_agent_turn_orchestration.py::test_start_waiting_then_reply_resumes_same_run_without_new_start` and authoritative material resume tests.

### Pre-Workflow Pending

If planning cannot start Research because material is absent, no durable run exists. The orchestrator stores `active_pending_interaction` and `active_pending_semantic_frame` in `AgentConversation.current_state` while `active_pending_run_ref` remains null. The next supported URL turn is merged by `_resume_preworkflow_research_material()` and starts a new run rather than calling Runtime resume. Evidence: `backend/app/agent/control/orchestrator.py::handle_turn/_resume_preworkflow_research_material`; `backend/app/agent/control/conversation_context.py::ConversationTurnContextOwner.save`.

The real current discontinuities are:

1. `_maybe_resume()` is gated by `active_pending_run_ref`; pre-Workflow Pending uses a separate special case, not the general resume service.
2. Control confirmations (`UPDATE_PROFILE`, `UPDATE_STRATEGY`) return Pending but are not saved by `_handle_control()` and have no `EXECUTE_CONFIRMED_COMMAND` continuation.
3. A follow-up only resumes within the same canonical conversation because pending identity is held in `AgentConversation.current_state`.
4. Backend-unsupported raw URL forms normalize to no material even if the frontend validator accepts them.

Evidence: `backend/app/agent/control/orchestrator.py::_maybe_resume/_handle_control`; `backend/app/services/unified_agent_sev.py::_conversation`; `backend/app/agent/control/current_turn_materials.py::_classify`; `frontend/src/views/AgentChatView.vue::isXhsNoteUrl`.

The historical black-box “URL cannot Resume” breakpoint is recorded in `docs/testing/REAL_E2E_ACCEPTANCE_REPORT.md`: semantic reconstruction produced invalid note candidates and `build_resume_input()` consumed them before provider execution. The checked-out orchestrator now gives server-authorized structured Note materials precedence, so supported full URLs no longer follow that historical path.

## 9. Memory

| Memory kind | Stored? | Retrieved? | Injected into model? | Consumed? | Confirmed before write? | Evidence |
|---|---:|---:|---:|---:|---:|---|
| Conversation messages | Yes | UI yes; canonical agent no | No | No by canonical LLMs | N/A | `AgentConversationMessage`; `AgentConversationRepository.add_message/list_messages`; `UnifiedAgentService.handle_turn` does not call `list_messages` |
| Workspace/recent structured context | Yes in `AgentConversation.current_state` | Yes each Turn | Not in Control prompt; identities/facts feed Resolver/Workflow | Yes by Resolver/input builders | Written from owned workspace/result identities | `ConversationTurnContextOwner.load/save`; `AgentTurnOrchestrator._update_recent` |
| Strategy memory | Yes, `strategy_memory` | Yes through `QueryGrowthContextTool` (validated memories only) | Yes for Strategy and Post-Publish semantic payloads through growth context | Yes in `ContentStrategyWorkflow` and `PostPublishReviewWorkflow` | `StrategyMemoryService.confirm_candidate()` requires `confirmed=True`, but no route to this service is registered in current `main.py` | `PublicationRepository.list_strategy_memories/create_memory`; `QueryGrowthContextTool`; `content_strategy.py::_run`; `post_publish_review.py::_run`; `strategy_memory_sev.py::confirm_candidate` |
| Account memory/profile | Yes, `account_profile` | Yes in every Workflow via `query_growth_context` | Selected fields are injected into business semantic payloads | Yes | Writes occur through account APIs/services, not the conversational confirmation stub | `models/account.py::AccountProfile`; `QueryGrowthContextTool._fill_section`; Workflow `_run()` methods |
| User preference memory | `tone_preference`, `risk_preference`, `forbidden_topics` are stored on Account | Account row is retrieved, but canonical `GrowthContextResult.account` omits these fields | No on canonical Workflow path | No on canonical Workflow path | Account update confirmation is not implemented in `_handle_control` | `models/account.py::AccountProfile`; `query_tools.py::QueryGrowthContextTool._fill_section`; `orchestrator.py::_handle_control` |

Important boundary: the existence of `backend/app/context/context_builder.py::ContextBuilder` and context-slot/memory models does not establish use by `/api/agent/turns`; that path does not call `ContextBuilder`. Likewise legacy `AgentConversationService.prepare_agent_request()` injects recent messages only for `/agent/chat/execute-workflow`, not for the canonical Turn endpoint. Evidence: `backend/app/services/unified_agent_sev.py::UnifiedAgentService._orchestrator/handle_turn`; `backend/app/agent/product_entry/chat_service.py::AgentChatWorkflowExecuteService.execute_workflow`.

## 10. LLM Calls

Provider retry is centralized in `backend/app/llm/providers/base.py::BaseLLMProvider.generate_text/generate_structured` using `settings.llm_max_retries` (default 2) and exponential wait. Default timeout is `settings.llm_timeout_seconds` (30 s) unless a call overrides it. Provider construction has no mock or provider fallback. Evidence: `backend/app/llm/client.py::LLMClient`; `backend/app/llm/router.py::build_llm_provider`; `backend/app/core/config.py::Settings`.

### Canonical `/api/agent/turns` call sites

| Call | File / function | Model policy | Prompt location | Input | Structured output | App retry / timeout |
|---|---|---|---|---|---|---|
| Control Semantic | `backend/app/agent/control/semantic_layer.py::ControlAgentSemanticLayer.understand` | `llm_control_semantic_model` or global model; thinking false | `backend/app/agent/control/prompts.py` (`CENTRALIZED_PROMPT`) | current Turn only + material counts/placeholders | `TaskSemanticFrame` | max 2 semantic attempts; provider default 30 s |
| Research Analysis | `backend/app/analysis/competitor/llm_analyzer.py::LLMStructuredCompetitorAnalyzer.analyze` | `llm_research_analysis_model`, configured thinking | local `SYSTEM_PROMPT` + local builder (`INLINE_PROMPT`) | adapted `CompetitorEvidence` | `CompetitorSemanticResult` | provider retry; 120 s default override |
| Strategy | `backend/app/services/content_strategy_sev.py::ContentStrategyService.generate_semantic` | global model | inline in function (`INLINE_PROMPT`) | authorized growth context, Research, history/memory, constraints | `GeneratedContentStrategy` | provider retry; default 30 s |
| Draft | `backend/app/services/draft_generation_sev.py::DraftGenerationService.generate_semantic` | global model | inline in function (`INLINE_PROMPT`) | Strategy, Opportunity, content goal, growth/evidence, constraints | `DraftContent` | provider retry; default 30 s |
| Draft Review | `backend/app/services/draft_review_sev.py::DraftReviewService.review_semantic` | global model | inline in function (`INLINE_PROMPT`) | prepared Draft + authorized evidence | `DraftReviewLLMResult` | provider retry; default 30 s |
| Revision | `backend/app/services/draft_revision_sev.py::DraftRevisionService.revise_semantic` | `llm_draft_revision_model` or global; optional thinking | inline plus local output contract (`INLINE_PROMPT`) | source Draft, explicit feedback, constraints, evidence | `DraftRevisionLLMResult` | provider retry; revision timeout or 30 s |
| Review | `backend/app/services/post_publish_review_v0_sev.py::PostPublishReviewService.review_semantic` | review model or global; optional thinking | inline in function (`INLINE_PROMPT`) | PublishedNote lineage, public/private metrics, growth/memory | `PostPublishReviewLLMResult` | provider retry; review timeout or 30 s |

The six business calls are reached through `backend/app/agent/tools/semantic_tools.py::{AnalyzeResearchTool,GenerateContentStrategyTool,GenerateDraftTool,ReviewDraftTool,ReviseDraftTool,AnalyzePostPublishReviewTool}.execute`.

### Other production-code call sites

- Compatibility service methods in the same files also call the LLM: `ContentStrategyService._generate_strategy`, `DraftGenerationService.generate`, `DraftReviewService.review`, `DraftRevisionService.revise`, and `PostPublishReviewService.review`. They are not called by the canonical Workflows, which use the `*_semantic` methods. Prompts are inline and outputs are the same domain schemas. Evidence: the named functions in `backend/app/services/{content_strategy,draft_generation,draft_review,draft_revision,post_publish_review_v0}_sev.py`.
- `backend/app/api/provider_health_rout.py::provider_health` calls `LLMClient.generate_text()` as an operational health call. `backend/app/api/llm.py` contains text/structured test calls, but its router is not registered by `backend/app/main.py::create_app`; these are not current HTTP production surfaces.
- The legacy `/agent/chat/execute-workflow` creates `_UnavailableLLMClient`; deterministic recognized branches may proceed, while any router/planner LLM attempt raises and is converted to safe UNKNOWN/blocked output. Evidence: `backend/app/agent/product_entry/chat_service.py::build_agent_chat_workflow_execute_service/_UnavailableLLMClient`, `backend/app/agent/product_entry/pipeline.py::_route/_plan`.

## 11. Prompt Locations

| Prompt key | Location | Governance status |
|---|---|---|
| `control_agent_semantic_layer:v2` | `backend/app/agent/control/prompts.py::SEMANTIC_SYSTEM_PROMPT/build_semantic_user_prompt` | `CENTRALIZED_PROMPT` |
| `competitor_semantic_analysis:v1` | `backend/app/analysis/competitor/llm_analyzer.py::SYSTEM_PROMPT/LLMStructuredCompetitorAnalyzer.analyze` | `INLINE_PROMPT` (module-local) |
| `content_strategy_semantic:v1` | `backend/app/services/content_strategy_sev.py::generate_semantic` | `INLINE_PROMPT` |
| `draft_generation_semantic:v1` | `backend/app/services/draft_generation_sev.py::generate_semantic` | `INLINE_PROMPT` |
| `draft_review_semantic:v1` | `backend/app/services/draft_review_sev.py::review_semantic` | `INLINE_PROMPT` |
| `draft_revision_semantic` | `backend/app/services/draft_revision_sev.py::revise_semantic` | `INLINE_PROMPT` |
| `post_publish_review_semantic:v2` | `backend/app/services/post_publish_review_v0_sev.py::review_semantic` | `INLINE_PROMPT` |

Prompt identity/version is recorded by `backend/app/llm/client.py::LLMClient.generate_structured` and attempt evidence by `backend/app/llm/evidence.py::PromptRunEvidenceRecorder`; this records metadata but does not centralize prompt text.

## 12. Fallbacks

| Type | Actual path | Status semantics |
|---|---|---|
| Hardcoded normal-chat response | `backend/app/agent/control/orchestrator.py::_handle_control` returns “你好，我可以帮你研究、策划、创作和优化小红书内容。” when no handler exists | `SUCCESS`; this is the exact requested string/path |
| Unimplemented query | same function, QUERY without handler | explicit warning, `FAILED`; no fake query data |
| Confirmation without executor | same function, CONFIRM | Pending `CONTROL_COMMAND_CONFIRMATION`, `WAITING_USER`; not persisted/resumable by this path |
| Cancel without capability | same function, CANCEL | acknowledgement + warning, `PENDING`; run is unchanged |
| Unsupported/missing plan | `AgentTurnOrchestrator.handle_turn` | explicit `FAILED` or `WAITING_USER` |
| Semantic schema exhaustion | `ControlAgentSemanticLayer.understand/_mixed_goal_fallback` | returns `UNKNOWN` frame and clarification; no fake business success |
| Tool failures | Tool base `_failure` methods | `ToolResult(success=False, data=None, error=...)`; schema forbids failure with data |
| Provider fallback | `LLMClient` / `llm.router` | none; missing/unavailable provider raises |
| Collection partial success | `XhsCollectionToolBase` / normalize methods | success only when at least one item is real; warnings and failed items retained |
| Legacy entry build/execute failure | `backend/app/api/agent_chat.py::_UnavailableWorkflowExecuteService/execute_workflow_agent_chat` | fixed failed response “Agent Chat workflow execution failed” |
| Legacy router/planner failure | `backend/app/agent/product_entry/pipeline.py::_safe_router_result/_safe_plan` | safe UNKNOWN/clarification, no execution |

No canonical semantic Tool has a mock/fake-success fallback: `backend/app/agent/tools/semantic_tools.py::SemanticToolBase._failure`; no LLM provider fallback: `backend/app/llm/client.py::LLMClient.__init__/generate_structured`, `backend/app/llm/router.py::configured_provider_name/build_llm_provider`.

## 13. Duplicate Runtime Concerns

The following are marked only as `DUPLICATED_RUNTIME_CONCERN`; no deletion decision is made here.

| Current component | Runtime concern duplicated | Evidence |
|---|---|---|
| `AgentConversationRepository` + `UnifiedAgentService` | message persistence and conversation/session assembly | `backend/app/repositories/agent_conversation_repo.py`; `backend/app/services/unified_agent_sev.py::handle_turn` |
| `AgentTurnRepository` fingerprint/replay | request/run idempotency | `backend/app/repositories/agent_turn_repo.py`; `UnifiedAgentService._replay` |
| `ControlAgentSemanticLayer` + 12 Intent gate | intent routing/structured routing | `backend/app/agent/control/semantic_layer.py`; `backend/app/agent/intents.py` |
| `DeterministicPlanner` + Skill/Workflow registries | plan and capability routing | `backend/app/agent/planning/planner.py`; `backend/app/agent/skills/registry.py`; `backend/app/agent/workflows/registry.py` |
| Workflow `_call()` + tool implementation registry | tool dispatch/retry loop | concrete Workflow files; `backend/app/agent/tools/implementation_registry.py` |
| `AgentRuntime`, `WorkflowRunService`, `WorkflowResumeService`, recovery/operation ledger | run state, pending/checkpoint, resume, recovery, exactly-once operation dispatch | `backend/app/runtime/*`; `backend/app/services/workflow_run_sev.py`; `backend/app/models/workflow_run.py`; `backend/app/models/workflow_operation.py` |
| `ConversationTurnContextOwner` | short-term structured memory stitching | `backend/app/agent/control/conversation_context.py` |
| Legacy `product_entry` Router/Planner/Executor/trace stack alongside canonical Turn stack | second intent routing, planning, dispatch, trace, message persistence | `backend/app/agent/product_entry/*`; `backend/app/api/agent_chat.py`; `backend/app/main.py::create_app` |

Each row: `DUPLICATED_RUNTIME_CONCERN`.

## 14. Current → Target Mapping

Target components are restricted to the frozen list supplied for this audit.

| Current component | Target component | KEEP | ADAPT | REMOVE | UNKNOWN | Evidence / factual reason |
|---|---|:---:|:---:|:---:|:---:|---|
| `CurrentTurnMaterialNormalizer` | Material Normalizer | ✓ |  |  |  | Already deterministic/pure; `backend/app/agent/control/current_turn_materials.py` |
| `AgentConversation` + message repository/service | Conversation Session | ✓ |  |  |  | Durable session/messages; `models/agent_conversation.py`, `repositories/agent_conversation_repo.py` |
| `ConversationTurnContextOwner` + `StructuredContext` | Workspace Context |  | ✓ |  |  | Carries refs/pending, but not message history and not Review; `control/conversation_context.py`, `context/contracts.py` |
| Frontend `workspace_selection` | Workspace Context |  | ✓ |  |  | Carries five flat IDs; Strategy/Opportunity lineage gap; frontend store + `UnifiedAgentService._workspace` |
| `ControlAgentSemanticLayer` + `AgentTurnOrchestrator` | Conversational Agent |  | ✓ |  |  | LLM understands only current Turn; control reply/query/tool selection is still Intent-gated; `control/semantic_layer.py`, `control/orchestrator.py` |
| `Tool/Workflow/Skill registries` | Capability Registry | ✓ |  |  |  | Frozen names, schemas, allowlists and implementations; `agent/{tools,workflows,skills}/registry.py` |
| `QueryGrowthContextTool`, `QueryArtifactTool`, `RetrieveResearchEvidenceTool`, `QueryPostPublishMetricsTool` | Query Tool | ✓ |  |  |  | Typed read-only tools; `agent/tools/query_tools.py` |
| Five Workflow classes + runtime start boundary | Workflow Tool |  | ✓ |  |  | Existing typed/resumable workflows, but not currently model-callable tools; `agent/workflows/*`, `runtime/agent_runtime.py` |
| Five Workflow classes | Workflow | ✓ |  |  |  | Real deterministic workflows; `WORKFLOW_HANDLER_REGISTRY` |
| 17 canonical Tool handler classes | Domain Tool | ✓ |  |  |  | All registered and real; `TOOL_HANDLER_REGISTRY` |
| Domain services (`ContentStrategyService`, Draft services, collector, review service) | Service | ✓ |  |  |  | Current business owners under `backend/app/services` |
| Canonical repositories | Repository | ✓ |  |  |  | Ownership/persistence reads and writes under `backend/app/repositories` |
| LLM providers, `XiaohongshuMcpProvider`, OCR provider | Provider | ✓ |  |  |  | `backend/app/llm/providers/*`, `collectors/xhs/xiaohongshu_mcp_provider.py`, `collectors/ocr/provider.py` |
| `AgentRuntime` + Workflow run/operation persistence | Runtime Persistence | ✓ |  |  |  | Durable runs/checkpoints/operations; `backend/app/runtime/*`, `models/workflow_run.py`, `models/workflow_operation.py` |
| Prompt-run evidence, resolution trace, legacy entry trace, developer trace | Trace |  | ✓ |  |  | Multiple trace owners rather than one path; `llm/evidence.py`, `context/contracts.py::ResolutionTrace`, `product_entry/trace.py`, `services/developer_trace_sev.py` |
| 12-Intent action matrix and `_handle_control` control branches | Conversational Agent |  | ✓ |  |  | Frozen target says only five Workflow labels remain; current hard gate still active; `agent/intents.py`, `planning/planner.py`, `control/orchestrator.py` |
| Legacy `/agent/chat/execute-workflow` stack | Conversational Agent |  |  |  | ✓ | Still registered and functionally separate; target disposition cannot be derived solely from current code; `api/agent_chat.py`, `agent/product_entry/*` |
| `ContextBuilder`/slot subsystem not called by canonical Turn | Workspace Context |  |  |  | ✓ | Exists but canonical reachability/use is absent; `backend/app/context/*`, `services/unified_agent_sev.py` |

## 15. Unknowns

1. **Deployment snapshot vs dirty worktree:** the repository contains many modified/deleted/untracked files. This audit describes the current filesystem, not a committed release. Evidence: read-only `git status --short` on 2026-09-28; no git mutation was performed.
2. **Runtime behavior of the real LLM classifier for each phrase:** prompts and schemas are known, but exact classification of “这篇/这个策略/刚才的策略/复盘这篇” is model output and cannot be proven statically. Code behavior after a given `SemanticReferenceType` is documented in section 4. Evidence: `ControlAgentSemanticLayer.understand`, `ContextResolver._resolve_one`.
3. **Current black-box reproduction of the historical URL resume defect:** the historical report records the old failure and fix; static current code routes supported full URLs correctly. No state-mutating real E2E was run in this read-only audit. Evidence: `docs/testing/REAL_E2E_ACCEPTANCE_REPORT.md`; current normalizer/orchestrator functions in section 5.
4. **Review as selectable workspace object:** no DTO or resolver enum exists; whether the frozen target expects Review selection through another identity is not expressed in code. Evidence: `WorkspaceSelectionRequest`, `ResolvedObjectType`.
5. **Legacy endpoint consumers:** `/agent/chat/execute-workflow` is registered, but current frontend uses `/api/agent/turns`; external callers cannot be determined from this repository. Evidence: `backend/app/main.py::create_app`, `frontend/src/api/unifiedAgent.ts`.
6. **Strategy-memory confirmation reachability outside this app:** `StrategyMemoryService.confirm_candidate()` exists, but no current registered API route calls it. External direct service use is UNKNOWN. Evidence: `backend/app/services/strategy_memory_sev.py`, `backend/app/main.py::create_app`.

## 16. Evidence Paths

Primary evidence index (all paths relative to `xhs-growth-agent/`):

- HTTP/composition: `backend/app/api/unified_agent.py::create_agent_turn`; `backend/app/services/unified_agent_sev.py::UnifiedAgentService`; `backend/app/schemas/unified_agent.py`; `backend/app/main.py::create_app`.
- Frontend carrier: `frontend/src/views/AgentChatView.vue`; `frontend/src/stores/agentChat.ts`; `frontend/src/types/unifiedAgent.ts`; `frontend/src/components/ArtifactDetailShell.vue`; artifact detail/list views under `frontend/src/views/agent/`.
- Semantic/control: `backend/app/agent/control/semantic_layer.py::ControlAgentSemanticLayer`; `control/prompts.py`; `control/orchestrator.py::AgentTurnOrchestrator`; `control/current_turn_materials.py`; `control/conversation_context.py`; `control/resume_builders.py`; `control/turn_contracts.py`.
- Contracts/routing: `backend/app/agent/schemas/{semantic,execution,interaction,planning}.py`; `backend/app/agent/intents.py`; `backend/app/agent/planning/{planner,input_builders,execution_service}.py`; `backend/app/agent/skills/registry.py`.
- Context: `backend/app/agent/context/{contracts,resolver,repository_reader}.py`.
- Tools: `backend/app/agent/tools/{definitions,registry,implementation_registry,query_tools,xhs_tools,semantic_tools,artifact_tools}.py` plus their `*_contracts.py` files.
- Workflows: `backend/app/agent/workflows/{registry,implementation_registry,research,content_strategy,content_creation,content_refinement,post_publish_review}.py`.
- Runtime: `backend/app/runtime/{agent_runtime,workflow_resume,workflow_recovery,durable_operation,workflow_contract_registry,workflow_initial_state_registry}.py`; `backend/app/services/workflow_run_sev.py`; `backend/app/models/{workflow_run,workflow_operation}.py`.
- Conversation/Turn persistence: `backend/app/models/{agent_conversation,agent_turn}.py`; `backend/app/repositories/{agent_conversation_repo,agent_turn_repo}.py`; `backend/app/services/agent_conversation_sev.py`.
- LLM: `backend/app/llm/{client,router,evidence}.py`; `backend/app/llm/providers/base.py`; `backend/app/core/config.py`; semantic service call sites listed in sections 10–11.
- Domain storage/providers: `backend/app/repositories/*`; `backend/app/services/*`; `backend/app/collectors/xhs/xiaohongshu_mcp_provider.py`; `backend/app/services/xhs_collector_sev.py`.
- Tests/historical black-box evidence: `backend/tests/test_current_turn_material_normalizer.py`; `test_phase2_5b_context_resolver.py`; `test_phase2_5d_agent_turn_orchestration.py`; `test_phase2_6a_unified_agent_api.py`; `test_phase2_4b_cross_request_resume.py`; `frontend/tests/chat-composer-materials.test.mjs`; `docs/testing/REAL_E2E_ACCEPTANCE_REPORT.md`.
- Duplicate legacy stack: `backend/app/api/agent_chat.py`; `backend/app/agent/product_entry/{chat_service,pipeline,llm_router,task_planner,executor,trace,business_handlers}.py`.

No production code, tests, database, dependency, git index, or commit was changed during this audit.
