from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field

from app.agent.context.contracts import StructuredContext
from app.agent.schemas.interaction import PendingInteraction
from app.agent.schemas.semantic import TaskSemanticFrame


class AgentTurnInput(BaseModel):
    """用户可提交的最小 Turn；不接受 Intent、Workflow、State 或可信 Ref。"""

    model_config = ConfigDict(extra="forbid")

    account_ref: int = Field(gt=0)
    text: str = Field(min_length=1)
    conversation_id: int | None = Field(default=None, gt=0)
    note_urls: list[str] = Field(default_factory=list)
    profile_urls: list[str] = Field(default_factory=list)


class TurnContextState(BaseModel):
    """Conversation 中只保存 identity/selection 与 pending identity。"""

    model_config = ConfigDict(extra="forbid")

    recent_context: StructuredContext = Field(default_factory=StructuredContext)
    active_pending_run_ref: str | None = None
    active_pending_checkpoint_version: int | None = None
    active_pending_interaction: PendingInteraction | None = None
    active_pending_semantic_frame: TaskSemanticFrame | None = None


class TurnContextOwner(Protocol):
    def load(self, conversation_id: int | None, account_ref: int) -> TurnContextState: ...
    def save(self, conversation_id: int | None, account_ref: int, state: TurnContextState) -> None: ...
