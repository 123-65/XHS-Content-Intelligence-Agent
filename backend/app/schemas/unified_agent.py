from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.agent.schemas.execution import AgentTurnResult
from app.runtime.agent_runtime import AgentRuntimeResult


class WorkspaceSelectionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    research_ref: int | None = Field(default=None, gt=0)
    strategy_ref: int | None = Field(default=None, gt=0)
    opportunity_ref: int | None = Field(default=None, gt=0)
    draft_ref: int | None = Field(default=None, gt=0)
    published_note_ref: int | None = Field(default=None, gt=0)


class AgentTurnMaterials(BaseModel):
    model_config = ConfigDict(extra="forbid")
    note_urls: list[str] = Field(default_factory=list, max_length=20)
    profile_urls: list[str] = Field(default_factory=list, max_length=20)


class AgentTurnRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    conversation_id: int | None = Field(default=None, gt=0)
    text: str = Field(min_length=1, max_length=20000)
    account_ref: int = Field(gt=0)
    workspace_selection: WorkspaceSelectionRequest | None = None
    materials: AgentTurnMaterials = Field(default_factory=AgentTurnMaterials)
    client_request_id: str = Field(min_length=1, max_length=128)


class AgentTurnResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    conversation_id: int
    turn_id: int
    turn: AgentTurnResult


class AgentRunResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    run_ref: str
    workflow_name: str
    account_ref: int
    status: str
    checkpoint_version: int
    pending_interaction: Any | None = None
    result: Any | None = None
    warnings: list[str] = Field(default_factory=list)
    error: Any | None = None

    @classmethod
    def from_runtime(cls, result: AgentRuntimeResult):
        return cls(**result.model_dump(include=set(cls.model_fields)))
