import json
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.core.config import settings
from app.llm.client import LLMClient
from app.llm.errors import LLMError


class ExecutionMode(StrEnum):
    CONVERSATION = "CONVERSATION"
    BUSINESS_ACTION = "BUSINESS_ACTION"


class ExecutionGateReason(StrEnum):
    META_QUESTION = "META_QUESTION"
    CASUAL_CONVERSATION = "CASUAL_CONVERSATION"
    CAPABILITY_QUESTION = "CAPABILITY_QUESTION"
    IDENTITY_OR_PERSONA = "IDENTITY_OR_PERSONA"
    MEMORY_QUESTION = "MEMORY_QUESTION"
    FOLLOW_UP_EXPLANATION = "FOLLOW_UP_EXPLANATION"
    EXPLICIT_BUSINESS_ACTION = "EXPLICIT_BUSINESS_ACTION"
    PENDING_CONTINUATION = "PENDING_CONTINUATION"
    AMBIGUOUS = "AMBIGUOUS"


class ExecutionGateInput(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    latest_user_text: str = Field(min_length=1)
    current_material_types: tuple[str, ...] = ()
    workspace_object_type: tuple[str, ...] = ()
    recent_business_context_types: tuple[str, ...] = ()
    active_pending_type: str | None = None


class ExecutionGateResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    mode: ExecutionMode
    confidence: float = Field(ge=0, le=1)
    reason_code: ExecutionGateReason


EXECUTION_GATE_PROMPT_KEY = "conversation_execution_gate"
EXECUTION_GATE_PROMPT_VERSION = "v2"
EXECUTION_GATE_TIMEOUT_SECONDS = 15

EXECUTION_GATE_SYSTEM_PROMPT = """You are an execution permission gate. You classify only whether the latest user turn permits business workflow tools.

Return one structured ExecutionGateResult. Never select a workflow, intent, tool, plan, or object ID.

Modes:
- CONVERSATION: expose zero workflow tools.
- BUSINESS_ACTION: the conversational agent may choose among its five workflow tools.

The latest user turn is authoritative. History is not provided and cannot turn a current conversational question into an action request.

Choose CONVERSATION for greetings, thanks, casual chat, capability or tool questions, identity/persona requests, memory questions, meta questions, explanations of earlier answers, definitions, questions about whether a feature exists, and ambiguous requests. Examples include asking what content strategy or review means, asking whether drafts can be edited, asking why automatic publishing is unavailable, or assigning a temporary name inside this conversation.

Choose BUSINESS_ACTION only when the latest turn explicitly asks the system to execute a business action now: research an account/note, create strategy from research, write from an opportunity, concretely revise a draft, or review a published note.

Important minimal pair:
- “为什么这类笔记容易火” without a specific current material is a general explanation, so choose CONVERSATION.
- “分析这篇为什么容易火” with NOTE in current_material_types explicitly commands analysis of that note, so choose BUSINESS_ACTION with EXPLICIT_BUSINESS_ACTION.
- The imperative verb “分析” is an execution request; do not reduce it to FOLLOW_UP_EXPLANATION when a specific current material is present.

Execution permission is separate from input completeness. “帮我分析一个同行账号” explicitly requests research now and is BUSINESS_ACTION even when no URL is present; the workflow tool is responsible for asking for the missing authorized Profile URL. Do not label an explicit action AMBIGUOUS merely because its required material is missing.

Pending continuation exception: when active_pending_type is present and the latest turn/current material supplies the requested continuation (for example a Profile URL after the assistant requested one), choose BUSINESS_ACTION with PENDING_CONTINUATION.

Context types only establish whether a referenced object or continuation exists. Their mere presence never grants execution permission.

If confidence is below 0.75, use CONVERSATION. Prefer one missed workflow over an unnecessary workflow call.
"""


class ExecutionGate:
    def __init__(self, llm_client=None):
        self._llm_client = llm_client

    def classify(self, data: ExecutionGateInput) -> ExecutionGateResult:
        try:
            client = self._llm_client or LLMClient()
            response = client.generate_structured(
                prompt=(
                    "Classify this bounded execution-gate input. It contains no full conversation history or artifact contents.\n"
                    f"<execution_gate_input>{json.dumps(data.model_dump(mode='json'), ensure_ascii=False)}</execution_gate_input>"
                ),
                schema_model=ExecutionGateResult,
                system_prompt=EXECUTION_GATE_SYSTEM_PROMPT,
                model=settings.llm_control_semantic_model or "qwen3.7-flash-2026-07-15",
                extra_body={"enable_thinking": False},
                timeout_seconds=EXECUTION_GATE_TIMEOUT_SECONDS,
                prompt_key=EXECUTION_GATE_PROMPT_KEY,
                prompt_version=EXECUTION_GATE_PROMPT_VERSION,
            )
            result = ExecutionGateResult.model_validate(response.data)
        except (LLMError, ValidationError, ValueError, TypeError):
            return self.safe_conversation_result()
        return self._enforce_boundary(result)

    @staticmethod
    def safe_conversation_result() -> ExecutionGateResult:
        return ExecutionGateResult(
            mode=ExecutionMode.CONVERSATION,
            confidence=0,
            reason_code=ExecutionGateReason.AMBIGUOUS,
        )

    @staticmethod
    def _enforce_boundary(result: ExecutionGateResult) -> ExecutionGateResult:
        if result.confidence < 0.75:
            return result.model_copy(
                update={"mode": ExecutionMode.CONVERSATION, "reason_code": ExecutionGateReason.AMBIGUOUS}
            )
        allowed_business_reasons = {
            ExecutionGateReason.EXPLICIT_BUSINESS_ACTION,
            ExecutionGateReason.PENDING_CONTINUATION,
        }
        if result.mode == ExecutionMode.BUSINESS_ACTION and result.reason_code not in allowed_business_reasons:
            return result.model_copy(
                update={"mode": ExecutionMode.CONVERSATION, "reason_code": ExecutionGateReason.AMBIGUOUS}
            )
        return result
