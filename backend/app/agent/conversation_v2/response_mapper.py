from app.agent.conversation_v2.outcomes import ConversationResponse, ConversationResponseKind, TurnExecutionLedger
from app.agent.schemas.execution import AgentTurnResult, RuntimeAction, WorkflowStatus
from app.agent.schemas.interaction import PendingInteraction, PendingInteractionType
from app.agent.schemas.semantic import Intent


_INTENT_BY_TOOL = {
    "run_research": Intent.RESEARCH,
    "run_content_strategy": Intent.CONTENT_STRATEGY,
    "run_content_creation": Intent.CONTENT_CREATE,
    "run_content_refinement": Intent.CONTENT_REFINE,
    "run_post_publish_review": Intent.POST_PUBLISH_REVIEW,
}


class ConversationResponseMapper:
    def map(self, response: ConversationResponse, ledger: TurnExecutionLedger) -> AgentTurnResult:
        outcome = ledger.last
        if outcome is not None:
            intent = _INTENT_BY_TOOL[outcome.tool_name]
            pending = None
            action = RuntimeAction.EXECUTE_PLAN
            if outcome.status == WorkflowStatus.WAITING_USER:
                action = RuntimeAction.CLARIFY
                pending = PendingInteraction(
                    type=PendingInteractionType.CLARIFICATION,
                    reason=outcome.user_message,
                    required_fields=outcome.required_fields,
                    options=[],
                    related_run_ref=outcome.run_ref,
                    resume_token=f"conversation-v2:{outcome.run_ref or outcome.tool_name}",
                )
            return AgentTurnResult(
                action=action,
                intent=intent,
                run_ref=outcome.run_ref,
                checkpoint_version=outcome.checkpoint_version,
                message=outcome.user_message,
                artifacts=outcome.artifact_refs,
                pending_interaction=pending,
                warnings=outcome.warnings,
                error={
                    "code": outcome.error_code,
                    **({"safe_message": outcome.safe_error_message} if outcome.safe_error_message else {}),
                } if outcome.error_code else None,
                status=outcome.status,
            )

        if response.response_kind == ConversationResponseKind.NEED_USER_INPUT:
            required_fields = [
                field for field in response.required_fields
                if field not in {"message", "response_kind", "required_fields"}
            ] or ["revision_direction"]
            return AgentTurnResult(
                action=RuntimeAction.CLARIFY,
                intent=Intent.UNKNOWN,
                message=response.message,
                pending_interaction=PendingInteraction(
                    type=PendingInteractionType.CLARIFICATION,
                    reason=response.message,
                    required_fields=required_fields,
                    options=[],
                    resume_token="conversation-v2:clarification",
                ),
                status=WorkflowStatus.WAITING_USER,
            )
        warnings = ["UNSUPPORTED_CAPABILITY"] if response.response_kind == ConversationResponseKind.UNSUPPORTED else []
        return AgentTurnResult(
            action=RuntimeAction.RESPOND,
            intent=Intent.UNKNOWN if response.response_kind == ConversationResponseKind.UNSUPPORTED else Intent.GENERAL_CHAT,
            message=response.message,
            warnings=warnings,
            status=WorkflowStatus.SUCCESS,
        )
