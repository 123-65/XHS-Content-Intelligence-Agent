import hashlib
import json
from dataclasses import dataclass
from types import MappingProxyType
from typing import Callable

from pydantic import BaseModel
from sqlalchemy.exc import IntegrityError

from app.agent.tools.artifact_contracts import (
    AppendDraftVersionInput,
    CreateContentStrategyArtifactInput,
    CreateContentStrategyArtifactResult,
    CreateDraftV1Input,
    CreateDraftVersionInput,
    CreateDraftVersionResult,
    CreatePostPublishReviewArtifactInput,
    CreatePostPublishReviewArtifactResult,
    CreateResearchArtifactInput,
    CreateResearchArtifactResult,
    CreateStrategyCandidateInput,
    CreateStrategyCandidateResult,
)
from app.agent.tools.definitions import ToolName, ToolResult
from app.agent.tools.execution_context import RuntimeExecutionIdentity
from app.repositories.workflow_operation_repo import WorkflowOperationRepository


class DurableOperationError(RuntimeError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class OperationDescriptor:
    operation_key: str
    identity_fingerprint: str


SIDE_EFFECT_RESULT_REGISTRY = MappingProxyType({
    ToolName.CREATE_RESEARCH_ARTIFACT: CreateResearchArtifactResult,
    ToolName.CREATE_CONTENT_STRATEGY_ARTIFACT: CreateContentStrategyArtifactResult,
    ToolName.CREATE_DRAFT_VERSION: CreateDraftVersionResult,
    ToolName.CREATE_POST_PUBLISH_REVIEW_ARTIFACT: CreatePostPublishReviewArtifactResult,
    ToolName.CREATE_STRATEGY_CANDIDATE: CreateStrategyCandidateResult,
})


def _fingerprint(payload: dict) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def describe_operation(tool_name: ToolName, data: BaseModel) -> OperationDescriptor:
    if tool_name == ToolName.CREATE_RESEARCH_ARTIFACT:
        typed = data if isinstance(data, CreateResearchArtifactInput) else CreateResearchArtifactInput.model_validate(data)
        identity = {"account_ref": typed.account_ref}
        key = f"{tool_name.value}:singleton"
    elif tool_name == ToolName.CREATE_CONTENT_STRATEGY_ARTIFACT:
        typed = data if isinstance(data, CreateContentStrategyArtifactInput) else CreateContentStrategyArtifactInput.model_validate(data)
        identity = {"account_ref": typed.account_ref, "research_artifact_ref": typed.research_artifact_ref}
        key = f"{tool_name.value}:singleton"
    elif tool_name == ToolName.CREATE_DRAFT_VERSION:
        typed_input = data if isinstance(data, CreateDraftVersionInput) else CreateDraftVersionInput.model_validate(data)
        typed = typed_input.root
        if isinstance(typed, CreateDraftV1Input):
            identity = {"action": typed.action, "account_ref": typed.account_ref, "strategy_artifact_ref": typed.strategy_artifact_ref, "opportunity_ref": typed.opportunity_ref}
        elif isinstance(typed, AppendDraftVersionInput):
            identity = {"action": typed.action, "draft_ref": typed.draft_ref, "parent_draft_ref": typed.parent_draft_ref}
        else:
            raise DurableOperationError("OPERATION_IDENTITY_INVALID", "Unsupported draft operation identity")
        key = f"{tool_name.value}:singleton"
    elif tool_name == ToolName.CREATE_POST_PUBLISH_REVIEW_ARTIFACT:
        typed = data if isinstance(data, CreatePostPublishReviewArtifactInput) else CreatePostPublishReviewArtifactInput.model_validate(data)
        identity = {"account_ref": typed.account_ref, "published_note_ref": typed.published_note_ref, "draft_ref": typed.draft_ref, "strategy_ref": typed.strategy_ref, "opportunity_ref": typed.opportunity_ref}
        key = f"{tool_name.value}:singleton"
    elif tool_name == ToolName.CREATE_STRATEGY_CANDIDATE:
        typed = data if isinstance(data, CreateStrategyCandidateInput) else CreateStrategyCandidateInput.model_validate(data)
        index = typed.candidate.candidate_index
        identity = {"account_ref": typed.account_ref, "post_publish_review_ref": typed.post_publish_review_ref, "candidate_index": index}
        key = f"{tool_name.value}:{index}"
    else:
        raise DurableOperationError("OPERATION_TOOL_UNSUPPORTED", f"Unsupported durable tool: {tool_name}")
    return OperationDescriptor(key, _fingerprint(identity))


class DurableOperationExecutor:
    def __init__(self, db, identity: RuntimeExecutionIdentity, repository: WorkflowOperationRepository | None = None):
        self.db = db
        self.identity = identity
        self.repository = repository or WorkflowOperationRepository(db)

    def execute(self, tool_name: ToolName, data: BaseModel, business_write: Callable[[], ToolResult]) -> ToolResult:
        descriptor = describe_operation(tool_name, data)
        existing = self.repository.get_succeeded(self.identity.run_ref, descriptor.operation_key)
        if existing is not None:
            return self._restore(existing, tool_name, descriptor)
        try:
            result = business_write()
            if not result.success:
                self.db.rollback()
                return result
            self.repository.create_succeeded(
                run_ref=self.identity.run_ref,
                workflow_name=self.identity.workflow_name,
                operation_key=descriptor.operation_key,
                tool_name=tool_name.value,
                identity_fingerprint=descriptor.identity_fingerprint,
                result_snapshot=result.model_dump(mode="json"),
            )
            self.db.commit()
            return result
        except IntegrityError:
            self.db.rollback()
            winner = self.repository.get_succeeded(self.identity.run_ref, descriptor.operation_key)
            if winner is None:
                raise
            return self._restore(winner, tool_name, descriptor)
        except Exception:
            self.db.rollback()
            raise

    @staticmethod
    def _restore(record, tool_name: ToolName, descriptor: OperationDescriptor) -> ToolResult:
        if record.tool_name != tool_name.value or record.identity_fingerprint != descriptor.identity_fingerprint:
            raise DurableOperationError("OPERATION_IDENTITY_MISMATCH", "Durable operation identity does not match the stored result")
        output_type = SIDE_EFFECT_RESULT_REGISTRY[tool_name]
        return ToolResult[output_type].model_validate(record.result_snapshot)
