from dataclasses import dataclass

from pydantic_ai.messages import ModelMessage, ModelRequest, ModelResponse, TextPart, UserPromptPart

from app.repositories.agent_conversation_repo import AgentConversationRepository


@dataclass(frozen=True)
class ConversationHistory:
    messages: list[ModelMessage]
    user_texts: tuple[str, ...]


class ConversationHistoryLoader:
    """Loads server-owned history, excluding the already persisted current USER row."""

    def __init__(self, db):
        self.repo = AgentConversationRepository(db)

    def load(self, *, conversation_id: int, account_ref: int, before_message_id: int, limit: int = 20) -> ConversationHistory:
        conversation = self.repo.get(conversation_id)
        if conversation is None:
            raise ValueError("CONVERSATION_NOT_FOUND")
        if conversation.account_id not in (None, account_ref):
            raise ValueError("CONVERSATION_ACCOUNT_MISMATCH")
        rows = self.repo.list_messages(conversation_id, limit=min(limit, 20), before_id=before_message_id)
        result: list[ModelMessage] = []
        user_texts: list[str] = []
        for row in rows:
            content = (row.content or "").strip()
            if not content:
                continue
            if row.role == "USER":
                result.append(ModelRequest(parts=[UserPromptPart(content=content)]))
                user_texts.append(content)
            elif row.role == "ASSISTANT":
                result.append(ModelResponse(parts=[TextPart(content=content)]))
        return ConversationHistory(messages=result, user_texts=tuple(user_texts))


ConversationHistoryAdapter = ConversationHistoryLoader
