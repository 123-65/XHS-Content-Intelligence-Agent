from app.agent.context.contracts import OpportunityCollection, StructuredContext, TrustedContextRef
from app.agent.control.turn_contracts import TurnContextState
from app.agent.schemas.interaction import PendingInteraction
from app.agent.schemas.semantic import TaskSemanticFrame
from app.schemas.agent_conversation import ConversationCurrentState


class ConversationTurnContextOwner:
    """复用 AgentConversation.current_state JSON 的内部 context owner。"""

    def __init__(self, conversation_service):
        self.service = conversation_service

    def load(self, conversation_id, account_ref):
        if conversation_id is None:
            return TurnContextState()
        state = self.service.get_state(conversation_id)
        if state.active_account_id not in (None, account_ref):
            raise ValueError("CONVERSATION_ACCOUNT_MISMATCH")
        return TurnContextState(
            recent_context=StructuredContext(
                references=[TrustedContextRef.model_validate(item) for item in state.recent_references],
                opportunity_collections=[OpportunityCollection.model_validate(item) for item in state.recent_opportunity_collections],
                review_refs=list(state.recent_review_refs),
            ),
            active_pending_run_ref=state.active_pending_run_ref,
            active_pending_checkpoint_version=state.active_pending_checkpoint_version,
            active_pending_interaction=PendingInteraction.model_validate(state.active_pending_interaction) if state.active_pending_interaction else None,
            active_pending_semantic_frame=TaskSemanticFrame.model_validate(state.active_pending_semantic_frame) if state.active_pending_semantic_frame else None,
        )

    def save(self, conversation_id, account_ref, state):
        if conversation_id is None:
            return
        conversation = self.service._get(conversation_id)
        current = ConversationCurrentState.model_validate(conversation.current_state or {})
        current.active_account_id = account_ref
        current.recent_references = [item.model_dump(mode="json") for item in state.recent_context.references][-20:]
        current.recent_opportunity_collections = [item.model_dump(mode="json") for item in state.recent_context.opportunity_collections][-5:]
        current.recent_review_refs = list(state.recent_context.review_refs)[-20:]
        current.active_pending_run_ref = state.active_pending_run_ref
        current.active_pending_checkpoint_version = state.active_pending_checkpoint_version
        current.active_pending_interaction = state.active_pending_interaction.model_dump(mode="json") if state.active_pending_interaction else None
        current.active_pending_semantic_frame = state.active_pending_semantic_frame.model_dump(mode="json") if state.active_pending_semantic_frame else None
        self.service.repo.update_state(conversation, current.model_dump(mode="json"), account_id=account_ref)
