import hashlib
import json

from app.agent.context.contracts import ObjectRef, ResolvedObjectType, StructuredContext, TrustedContextRef
from app.agent.context.repository_reader import RepositoryContextIdentityReader
from app.agent.context.resolver import ContextResolver
from app.agent.control.conversation_context import ConversationTurnContextOwner
from app.agent.control.current_turn_materials import CurrentTurnMaterialNormalizer
from app.agent.control.orchestrator import AgentTurnOrchestrator
from app.agent.control.semantic_layer import ControlAgentSemanticLayer
from app.agent.control.turn_contracts import AgentTurnInput
from app.agent.conversation_v2.service import ConversationalAgentService
from app.agent.planning.execution_service import PlanExecutionService
from app.agent.planning.planner import DeterministicPlanner
from app.agent.schemas.execution import AgentTurnResult
from app.agent.tools.access_scopes import EvidenceAccessScope
from app.agent.tools.execution_context import ToolExecutionContext
from app.agent.tools.xhs_contracts import CollectionAccessScope, CollectionAuthorizationSource
from app.llm.client import LLMClient
from app.core.config import settings
from app.repositories.agent_turn_repo import AgentTurnRepository
from app.runtime.agent_runtime import AgentRuntime
from app.schemas.agent_conversation import ConversationCreate, ConversationMessageCreate, ConversationMessageType, ConversationRole
from app.schemas.unified_agent import AgentRunResponse, AgentTurnRequest, AgentTurnResponse
from app.services.agent_conversation_sev import AgentConversationService
from app.services.workflow_run_sev import WorkflowRunService
from app.services.workflow_run_sev import WorkflowRunServiceError


class UnifiedAgentError(RuntimeError):
    def __init__(self, code, message): super().__init__(message); self.code = code


class UnifiedAgentService:
    """HTTP 与 AgentTurnOrchestrator 之间唯一应用服务。"""

    def __init__(self, db, *, orchestrator=None, runtime=None, conversational_service=None):
        self.db = db
        self.conversations = AgentConversationService(db)
        self.turns = AgentTurnRepository(db)
        self.reader = RepositoryContextIdentityReader(db)
        self.runtime = runtime or AgentRuntime(WorkflowRunService(db))
        self.orchestrator = orchestrator
        self.conversational_service = conversational_service

    def handle_turn(self, request: AgentTurnRequest) -> AgentTurnResponse:
        payload = request.model_dump(mode="json")
        fingerprint = hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        existing = self.turns.get_by_request(request.account_ref, request.client_request_id)
        if existing:
            return self._replay(existing, fingerprint)

        conversation_id = self._conversation(request)
        item = self.turns.reserve(
            account_id=request.account_ref, conversation_id=conversation_id,
            client_request_id=request.client_request_id, request_fingerprint=fingerprint,
            request_payload=payload, result_payload=None, error_message=None,
        )
        if item is None:
            return self._replay(self.turns.get_by_request(request.account_ref, request.client_request_id), fingerprint)
        try:
            normalized = CurrentTurnMaterialNormalizer().normalize_with_provenance(request.text, request.materials)
            normalized_materials = normalized.materials
            normalized_request = request.model_copy(update={"materials": normalized_materials})
            workspace = self._workspace(request)
            execution_context = self._execution_context(normalized_request)
            user_message = self.conversations.repo.add_message(self.conversations._get(conversation_id), ConversationMessageCreate(role=ConversationRole.USER, content=request.text, message_type=ConversationMessageType.TEXT, metadata_payload={"turn_id": item.id, "client_request_id": request.client_request_id}))
            conversation_service = None
            if settings.agent_entry_mode == "conversation_v2" and self.orchestrator is None:
                conversation_service = self.conversational_service or ConversationalAgentService(
                    self.db, self.runtime
                )
                result = conversation_service.handle_turn(
                    account_ref=request.account_ref,
                    conversation_id=conversation_id,
                    current_user_message_id=user_message.id,
                    text=request.text,
                    materials=normalized_materials,
                    material_provenance=tuple(normalized.items),
                    workspace_selection=workspace,
                    execution_context=execution_context,
                )
            else:
                orchestrator = self.orchestrator or self._orchestrator()
                result = orchestrator.handle_turn(
                    AgentTurnInput(account_ref=request.account_ref, text=request.text, conversation_id=conversation_id, note_urls=normalized_materials.note_urls, profile_urls=normalized_materials.profile_urls),
                    execution_context,
                    workspace_selection=workspace,
                )
            response = AgentTurnResponse(conversation_id=conversation_id, turn_id=item.id, turn=result)
            self.turns.complete(item, response.model_dump(mode="json"))
            trace = conversation_service.last_trace.model_dump(mode="json") if conversation_service and conversation_service.last_trace else {}
            self.conversations.repo.add_message(self.conversations._get(conversation_id), ConversationMessageCreate(role=ConversationRole.ASSISTANT, content=result.message, message_type=ConversationMessageType.AGENT_RESPONSE, metadata_payload={"turn_id": item.id, "action": result.action.value, "intent": result.intent.value, "status": result.status.value, "run_ref": result.run_ref, **trace}))
            return response
        except Exception as exc:
            self.turns.fail(item, str(exc))
            raise

    def get_run(self, run_ref, account_ref):
        try:
            result = self.runtime.get_run(run_ref)
        except WorkflowRunServiceError as exc:
            raise UnifiedAgentError(exc.code, str(exc)) from exc
        if result.account_ref != account_ref:
            raise UnifiedAgentError("RUN_ACCOUNT_MISMATCH", "Run 不属于当前 Account。")
        return AgentRunResponse.from_runtime(result)

    def _conversation(self, request):
        if request.conversation_id is None:
            return self.conversations.create_conversation(ConversationCreate(account_id=request.account_ref)).id
        try:
            conversation = self.conversations.get_conversation(request.conversation_id)
        except ValueError as exc:
            raise UnifiedAgentError("CONVERSATION_NOT_FOUND", str(exc)) from exc
        if conversation.status != "ACTIVE":
            raise UnifiedAgentError("CONVERSATION_NOT_ACTIVE", "Conversation 当前不可用。")
        if conversation.account_id not in (None, request.account_ref) or conversation.current_state.active_account_id not in (None, request.account_ref):
            raise UnifiedAgentError("CONVERSATION_ACCOUNT_MISMATCH", "Conversation 不属于当前 Account。")
        return conversation.id

    def _workspace(self, request):
        selection = request.workspace_selection
        if selection is None: return StructuredContext()
        mapping = {
            "research_ref": ResolvedObjectType.RESEARCH,
            "strategy_ref": ResolvedObjectType.CONTENT_STRATEGY,
            "opportunity_ref": ResolvedObjectType.CONTENT_OPPORTUNITY,
            "draft_ref": ResolvedObjectType.DRAFT,
            "published_note_ref": ResolvedObjectType.PUBLISHED_NOTE,
        }
        refs = []
        for field, kind in mapping.items():
            value = getattr(selection, field)
            if value is None: continue
            ref = ObjectRef(type=kind, id=value)
            identity = self.reader.get_identity(ref)
            if identity is None: raise UnifiedAgentError("WORKSPACE_REFERENCE_NOT_FOUND", f"{field} 不存在。")
            if identity.account_ref != request.account_ref: raise UnifiedAgentError("WORKSPACE_ACCOUNT_MISMATCH", f"{field} 不属于当前 Account。")
            refs.append(TrustedContextRef(ref=ref, account_ref=request.account_ref))
        return StructuredContext(references=refs)

    def _execution_context(self, request):
        materials = request.materials
        collection = CollectionAccessScope(workspace_account_ref=request.account_ref, authorization_source=CollectionAuthorizationSource.USER_PROVIDED, allowed_note_urls=tuple(materials.note_urls), allowed_profile_urls=tuple(materials.profile_urls))
        return ToolExecutionContext(db=self.db, evidence_access_scope=EvidenceAccessScope.deny_all(), collection_access_scope=collection)

    def _orchestrator(self):
        semantic = ControlAgentSemanticLayer(LLMClient())
        resolver = ContextResolver(self.reader)
        planner = DeterministicPlanner()
        execution = PlanExecutionService(self.runtime)
        owner = ConversationTurnContextOwner(self.conversations)
        return AgentTurnOrchestrator(semantic_layer=semantic, context_resolver=resolver, planner=planner, plan_execution_service=execution, runtime=self.runtime, context_owner=owner)

    @staticmethod
    def _replay(item, fingerprint):
        if item is None: raise UnifiedAgentError("REQUEST_IN_PROGRESS", "请求正在处理中。")
        if item.request_fingerprint != fingerprint: raise UnifiedAgentError("REQUEST_IDENTITY_MISMATCH", "client_request_id 已用于不同请求。")
        if item.status == "PROCESSING": raise UnifiedAgentError("REQUEST_IN_PROGRESS", "相同请求正在处理中。")
        if item.status == "FAILED": raise UnifiedAgentError("REQUEST_PREVIOUSLY_FAILED", item.error_message or "首次请求失败。")
        return AgentTurnResponse.model_validate(item.result_payload)
