from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

from app.agent.context.contracts import ObjectRef, OpportunityCollection, ResolvedObjectType, StructuredContext, TrustedContextRef
from app.agent.context.repository_reader import RepositoryContextIdentityReader
from app.agent.control.conversation_context import ConversationTurnContextOwner
from app.agent.control.current_turn_materials import (
    CurrentMaterialType,
    CurrentTurnMaterialNormalizer,
    NormalizedCurrentMaterial,
)
from app.agent.conversation_v2.agent import build_conversation_agent
from app.agent.conversation_v2.capabilities import CAPABILITIES
from app.agent.conversation_v2.decision_context import (
    CanonicalTurnContextBuilder,
    DecisionObjectType,
    PendingFact,
    pending_requirements_satisfied,
)
from app.agent.conversation_v2.deps import ConversationAgentDeps
from app.agent.conversation_v2.execution_gate import ExecutionGate, ExecutionGateInput, ExecutionMode
from app.agent.conversation_v2.history import ConversationHistoryAdapter
from app.agent.conversation_v2.outcomes import TurnExecutionLedger
from app.agent.conversation_v2.response_mapper import ConversationResponseMapper
from app.agent.conversation_v2.workspace import TrustedWorkspaceBuilder
from app.agent.schemas.execution import AgentTurnResult, ArtifactType, WorkflowStatus
from app.agent.workflows.definitions import WorkflowId
from app.runtime.agent_runtime import AgentRuntime
from app.schemas.unified_agent import AgentTurnMaterials
from app.services.agent_conversation_sev import AgentConversationService


class ConversationExecutionTrace(BaseModel):
    model_config = ConfigDict(extra="forbid")

    conversation_id: int
    agent_run_id: str
    selected_high_level_tool: str | None = None
    workflow_run_ref: str | None = None
    workflow_status: str | None = None
    execution_mode: str | None = None
    execution_reason_code: str | None = None
    execution_confidence: float | None = None
    current_material_facts: list[dict[str, object]] = Field(default_factory=list)
    eligible_workflow_tools: list[str] = Field(default_factory=list)


class ConversationalAgentService:
    def __init__(self, db, runtime: AgentRuntime, *, agent=None, invoker=None, execution_gate=None):
        self.db = db
        self.runtime = runtime
        self.agent = agent
        self.invoker = invoker or runtime
        self.execution_gate = execution_gate or ExecutionGate()
        self.history = ConversationHistoryAdapter(db)
        self.workspace_builder = TrustedWorkspaceBuilder(db)
        self.identity_reader = RepositoryContextIdentityReader(db)
        self.decision_context_builder = CanonicalTurnContextBuilder()
        self.conversations = AgentConversationService(db)
        self.context_owner = ConversationTurnContextOwner(self.conversations)
        self.mapper = ConversationResponseMapper()
        self.last_trace: ConversationExecutionTrace | None = None

    def handle_turn(
        self,
        *,
        account_ref: int,
        conversation_id: int,
        current_user_message_id: int,
        text: str,
        materials: AgentTurnMaterials,
        material_provenance: tuple[NormalizedCurrentMaterial, ...],
        workspace_selection: StructuredContext,
        execution_context,
    ) -> AgentTurnResult:
        history = self.history.load(
            conversation_id=conversation_id,
            account_ref=account_ref,
            before_message_id=current_user_message_id,
            limit=20,
        )
        recent_materials = CurrentTurnMaterialNormalizer().normalize(
            "\n".join(history.user_texts), AgentTurnMaterials()
        )
        turn_state = self.context_owner.load(conversation_id, account_ref)
        workspace = self.workspace_builder.build(workspace_selection)
        trusted_recent = self._verified_recent_context(turn_state.recent_context, account_ref)
        recent_context = self.workspace_builder.recent(trusted_recent)
        material_types = frozenset(item.material_type for item in material_provenance)
        pending = self._validated_pending(turn_state, account_ref, material_types)
        decision_context = self.decision_context_builder.build(
            current_materials=material_provenance,
            workspace=workspace,
            recent=recent_context,
            pending=pending,
        )
        gate_object_names = {
            DecisionObjectType.RESEARCH_ARTIFACT: "RESEARCH",
            DecisionObjectType.CONTENT_STRATEGY: "CONTENT_STRATEGY",
            DecisionObjectType.OPPORTUNITY: "CONTENT_OPPORTUNITY",
            DecisionObjectType.DRAFT: "DRAFT",
            DecisionObjectType.PUBLISHED_NOTE: "PUBLISHED_NOTE",
        }
        gate_input = ExecutionGateInput(
            latest_user_text=text,
            current_material_types=tuple(
                "NOTE" if item == CurrentMaterialType.EXTERNAL_XHS_NOTE else "PROFILE"
                for item in decision_context.current_material_types
            ),
            workspace_object_type=tuple(
                gate_object_names[item.object_type]
                for item in decision_context.workspace_objects
            ),
            recent_business_context_types=tuple(
                gate_object_names[item.object_type]
                for item in decision_context.recent_object_types
            ),
            active_pending_type=pending.workflow_type.value if pending and pending.resumable else None,
        )
        gate_result = self.execution_gate.classify(gate_input)
        ledger = TurnExecutionLedger()
        deps = ConversationAgentDeps(
            account_ref=account_ref,
            conversation_id=conversation_id,
            current_text=text,
            runtime=self.runtime,
            execution_context=execution_context,
            trusted_workspace=workspace,
            recent_context=recent_context,
            current_materials=materials,
            recent_note_urls=tuple(recent_materials.note_urls),
            recent_profile_urls=tuple(recent_materials.profile_urls),
            capabilities=CAPABILITIES,
            turn_execution_ledger=ledger,
            workflow_invoker=self.invoker,
            execution_gate=gate_result,
            decision_context=decision_context,
            active_pending_run_ref=turn_state.active_pending_run_ref,
            active_pending_checkpoint_version=turn_state.active_pending_checkpoint_version,
        )
        agent = self.agent or build_conversation_agent()
        agent_run_id = str(uuid4())
        run = agent.run_sync(
            text,
            message_history=history.messages,
            deps=deps,
            run_id=agent_run_id,
        )
        result = self.mapper.map(run.output, ledger)
        if gate_result.mode == ExecutionMode.CONVERSATION and ledger.outcomes:
            raise RuntimeError("CONVERSATION_WORKFLOW_TOOL_CALL_FORBIDDEN")
        self._save_recent_context(turn_state, workspace_selection, result, account_ref, conversation_id)
        outcome = ledger.last
        self.last_trace = ConversationExecutionTrace(
            conversation_id=conversation_id,
            agent_run_id=str(getattr(run, "run_id", None) or agent_run_id),
            selected_high_level_tool=outcome.tool_name if outcome else None,
            workflow_run_ref=outcome.run_ref if outcome else None,
            workflow_status=outcome.status.value if outcome else result.status.value,
            execution_mode=gate_result.mode.value,
            execution_reason_code=gate_result.reason_code.value,
            execution_confidence=gate_result.confidence,
            current_material_facts=[
                item.model_dump(mode="json") for item in decision_context.current_materials
            ],
            eligible_workflow_tools=list(decision_context.candidate_tools),
        )
        return result

    def _verified_recent_context(self, context: StructuredContext, account_ref: int) -> StructuredContext:
        def owned(item: TrustedContextRef) -> bool:
            identity = self.identity_reader.get_identity(item.ref)
            return identity is not None and identity.account_ref == account_ref == item.account_ref

        references = [item for item in context.references if owned(item)]
        collections = [
            collection
            for collection in context.opportunity_collections
            if owned(collection.strategy_ref)
            and collection.opportunity_refs
            and all(owned(item) for item in collection.opportunity_refs)
        ]
        return StructuredContext(
            references=references,
            opportunity_collections=collections,
            review_refs=list(context.review_refs),
        )

    def _validated_pending(
        self,
        state,
        account_ref: int,
        material_types: frozenset[CurrentMaterialType],
    ) -> PendingFact | None:
        if state.active_pending_run_ref is None or state.active_pending_checkpoint_version is None:
            return None
        try:
            run = self.runtime.get_run(state.active_pending_run_ref)
            workflow_type = WorkflowId(run.workflow_name)
        except (ValueError, TypeError, RuntimeError):
            return None
        if (
            run.account_ref != account_ref
            or run.status != WorkflowStatus.WAITING_USER
            or run.pending_interaction is None
            or run.checkpoint_version != state.active_pending_checkpoint_version
            or workflow_type != WorkflowId.RESEARCH_V1
        ):
            return None
        required_fields = tuple(run.pending_interaction.required_fields)
        return PendingFact(
            workflow_type=workflow_type,
            required_fields=required_fields,
            resumable=True,
            requirements_satisfied=pending_requirements_satisfied(
                workflow_type,
                required_fields,
                material_types,
            ),
        )

    def _save_recent_context(self, state, selection: StructuredContext, result: AgentTurnResult, account_ref: int, conversation_id: int) -> None:
        references = list(state.recent_context.references)
        references.extend(selection.references)
        opportunity_collections = list(state.recent_context.opportunity_collections)
        review_refs = list(state.recent_context.review_refs)
        artifact_mapping = {
            ArtifactType.RESEARCH: ResolvedObjectType.RESEARCH,
            ArtifactType.CONTENT_STRATEGY: ResolvedObjectType.CONTENT_STRATEGY,
            ArtifactType.CONTENT_OPPORTUNITY: ResolvedObjectType.CONTENT_OPPORTUNITY,
            ArtifactType.DRAFT: ResolvedObjectType.DRAFT,
        }
        if result.status in {WorkflowStatus.SUCCESS, WorkflowStatus.PARTIAL_SUCCESS}:
            for artifact in result.artifacts:
                if kind := artifact_mapping.get(artifact.type):
                    references.append(TrustedContextRef(
                        ref=ObjectRef(type=kind, id=artifact.id),
                        account_ref=account_ref,
                    ))
                elif artifact.type == ArtifactType.POST_PUBLISH_REVIEW:
                    review_refs.append(artifact.id)
            strategy_refs = [item.id for item in result.artifacts if item.type == ArtifactType.CONTENT_STRATEGY]
            opportunity_refs = [item.id for item in result.artifacts if item.type == ArtifactType.CONTENT_OPPORTUNITY]
            if strategy_refs and opportunity_refs:
                opportunity_collections.append(OpportunityCollection(
                    strategy_ref=TrustedContextRef(
                        ref=ObjectRef(type=ResolvedObjectType.CONTENT_STRATEGY, id=strategy_refs[-1]),
                        account_ref=account_ref,
                    ),
                    opportunity_refs=[
                        TrustedContextRef(
                            ref=ObjectRef(type=ResolvedObjectType.CONTENT_OPPORTUNITY, id=ref),
                            account_ref=account_ref,
                        )
                        for ref in opportunity_refs
                    ],
                ))
        deduplicated = {}
        for item in references:
            deduplicated[(item.ref.type.value, item.ref.id)] = item
        state.recent_context = state.recent_context.model_copy(
            update={
                "references": list(deduplicated.values())[-20:],
                "opportunity_collections": opportunity_collections[-5:],
                "review_refs": list(dict.fromkeys(review_refs))[-20:],
            }
        )
        state.active_pending_run_ref = result.run_ref if result.pending_interaction else None
        state.active_pending_checkpoint_version = result.checkpoint_version if result.pending_interaction else None
        state.active_pending_interaction = result.pending_interaction
        self.context_owner.save(conversation_id, account_ref, state)
