from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.agent.schemas.execution import ArtifactRef, WorkflowStatus


class WorkflowToolOutcome(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tool_name: str
    workflow_name: str
    status: WorkflowStatus
    user_message: str
    run_ref: str | None = None
    checkpoint_version: int | None = None
    artifact_refs: list[ArtifactRef] = Field(default_factory=list)
    required_fields: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    error_code: str | None = None
    safe_error_message: str | None = None


class TurnExecutionLedger(BaseModel):
    model_config = ConfigDict(extra="forbid")

    outcomes: list[WorkflowToolOutcome] = Field(default_factory=list)

    def record(self, outcome: WorkflowToolOutcome) -> WorkflowToolOutcome:
        self.outcomes.append(outcome)
        return outcome

    @property
    def last(self) -> WorkflowToolOutcome | None:
        return self.outcomes[-1] if self.outcomes else None


class ConversationResponseKind(StrEnum):
    RESPOND = "RESPOND"
    NEED_USER_INPUT = "NEED_USER_INPUT"
    UNSUPPORTED = "UNSUPPORTED"


class ConversationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message: str
    response_kind: ConversationResponseKind = ConversationResponseKind.RESPOND
    required_fields: list[str] = Field(default_factory=list)
