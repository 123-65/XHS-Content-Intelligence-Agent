from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from app.enums.confirmation import ConfirmationDecisionType, ConfirmationTaskStatus, ConfirmationType
from app.models.confirmation_task import ConfirmationTask
from app.models.content_draft import ContentDraft
from app.models.content_experiment import ContentExperiment
from app.models.review_report import ReviewReport
from app.repositories.confirmation_repo import ConfirmationRepository
from app.schemas.confirmation import (
    ConfirmationAuditLogResponse,
    ConfirmationDecisionCreate,
    ConfirmationDecisionResponse,
    ConfirmationTaskCreate,
    ConfirmationTaskResponse,
    PendingConfirmationResponse,
)


TARGET_BY_CONFIRMATION_TYPE = {
    ConfirmationType.EXPERIMENT_CONFIRM: "CONTENT_EXPERIMENT",
    ConfirmationType.DRAFT_CONFIRM: "CONTENT_DRAFT",
    ConfirmationType.REVIEW_CONFIRM: "REVIEW_REPORT",
    ConfirmationType.PUBLISH_CONFIRM: "CONTENT_DRAFT",
    ConfirmationType.HIGH_RISK_CONFIRM: "HIGH_RISK_TARGET",
}

IGNORED_DECISIONS_FOR_HIGH_RISK = {
    ConfirmationDecisionType.PAUSED,
    ConfirmationDecisionType.CANCELLED,
}


@dataclass(frozen=True)
class TargetContext:
    """Resolved target object and account metadata."""

    target: Any
    target_type: str
    target_id: int
    account_id: int
    target_version: int | None
    snapshot: dict


class ConfirmationService:
    """Human-in-the-loop confirmation gateway service."""

    def __init__(self, db: Session):
        """Initialize the confirmation service."""
        self.repo = ConfirmationRepository(db)

    def create_task(self, data: ConfirmationTaskCreate) -> ConfirmationTaskResponse:
        """Create a human confirmation task and initial audit log."""
        context = self._resolve_context(data)
        risk_level = self._risk_level(data.confirmation_type, context)
        fields = {
            "account_id": data.account_id or context.account_id,
            "confirmation_type": data.confirmation_type.value,
            "target_type": context.target_type,
            "target_id": context.target_id,
            "target_version": context.target_version,
            "status": ConfirmationTaskStatus.PENDING.value,
            "summary": self._summary(data.confirmation_type, context),
            "recommendation": self._recommendation(data.confirmation_type, risk_level, context),
            "risk_level": risk_level,
            "risk_reason": self._risk_reason(data.confirmation_type, context),
            "payload_snapshot": {**context.snapshot, "extra_context": data.extra_context},
            "created_by": data.created_by,
        }
        if data.confirmation_type == ConfirmationType.PUBLISH_CONFIRM:
            self.invalidate_publish_confirmations_for_draft(context.target_id, context.target_version or 0, "new publish confirmation created")
        task = self.repo.create_task(fields)
        self._audit(task.id, "CREATED", None, task.status, data.created_by, "confirmation task created", {})
        return self.get_task(task.id)

    def list_pending_tasks(self, account_id: int | None = None) -> PendingConfirmationResponse:
        """List pending tasks and lazily invalidate stale publish confirmations."""
        tasks = [self._ensure_stale_publish_task_invalidated(task) for task in self.repo.list_pending_tasks(account_id)]
        pending = [self._build_response(task) for task in tasks if task.status == ConfirmationTaskStatus.PENDING.value]
        return PendingConfirmationResponse(account_id=account_id, count=len(pending), tasks=pending)

    def get_task(self, task_id: int) -> ConfirmationTaskResponse:
        """Get a confirmation task with decisions and audit logs."""
        task = self._get_task_or_raise(task_id)
        return self._build_response(self._ensure_stale_publish_task_invalidated(task))

    def submit_decision(self, task_id: int, data: ConfirmationDecisionCreate) -> ConfirmationTaskResponse:
        """Submit a human decision and write audit records."""
        task = self._ensure_stale_publish_task_invalidated(self._get_task_or_raise(task_id))
        self._ensure_task_can_decide(task)
        self._ensure_high_risk_not_ignored(task, data)
        previous_status = task.status
        self.repo.create_decision(task.id, data)
        updated = self.repo.update_task_status(task, data.decision.value)
        self._audit(task.id, "DECISION_SUBMITTED", previous_status, updated.status, data.decided_by, data.comment, data.revision_request)
        self._apply_target_transition(updated, data)
        return self.get_task(updated.id)

    def invalidate_publish_confirmations_for_draft(self, draft_id: int, current_version: int, reason: str = "draft version changed") -> int:
        """Invalidate pending publish confirmations when the draft version changes."""
        tasks = self.repo.list_pending_publish_tasks_for_draft(draft_id)
        stale_tasks = [task for task in tasks if task.target_version != current_version]
        for task in stale_tasks:
            previous_status = task.status
            self.repo.update_task_status(task, ConfirmationTaskStatus.INVALIDATED.value, reason)
            self._audit(task.id, "INVALIDATED", previous_status, ConfirmationTaskStatus.INVALIDATED.value, "system", reason, {"current_version": current_version})
        return len(stale_tasks)

    def _resolve_context(self, data: ConfirmationTaskCreate) -> TargetContext:
        """Resolve task target, account ID, version, and snapshot."""
        target_type = data.target_type or TARGET_BY_CONFIRMATION_TYPE[data.confirmation_type]
        resolver = {
            "CONTENT_EXPERIMENT": self._experiment_context,
            "CONTENT_DRAFT": self._draft_context,
            "REVIEW_REPORT": self._review_context,
            "HIGH_RISK_TARGET": self._generic_high_risk_context,
        }.get(target_type)
        if not resolver:
            raise ValueError(f"Unsupported confirmation target type: {target_type}")
        return resolver(data)

    def _experiment_context(self, data: ConfirmationTaskCreate) -> TargetContext:
        """Resolve an experiment target context."""
        experiment = self.repo.get_experiment(data.target_id)
        if not experiment:
            raise ValueError("Content experiment does not exist")
        account_id = data.account_id or experiment.account_id
        return TargetContext(experiment, "CONTENT_EXPERIMENT", experiment.id, account_id, None, self._experiment_snapshot(experiment))

    def _draft_context(self, data: ConfirmationTaskCreate) -> TargetContext:
        """Resolve a draft target context."""
        draft = self.repo.get_draft(data.target_id)
        if not draft:
            raise ValueError("Content draft does not exist")
        experiment = self.repo.get_experiment(draft.experiment_id)
        if not experiment:
            raise ValueError("Content experiment does not exist")
        account_id = data.account_id or experiment.account_id
        return TargetContext(draft, "CONTENT_DRAFT", draft.id, account_id, draft.version, self._draft_snapshot(draft))

    def _review_context(self, data: ConfirmationTaskCreate) -> TargetContext:
        """Resolve a review report target context."""
        report = self.repo.get_review_report(data.target_id)
        if not report:
            raise ValueError("Review report does not exist")
        draft = self.repo.get_draft(report.draft_id)
        if not draft:
            raise ValueError("Content draft does not exist")
        experiment = self.repo.get_experiment(draft.experiment_id)
        if not experiment:
            raise ValueError("Content experiment does not exist")
        account_id = data.account_id or experiment.account_id
        return TargetContext(report, "REVIEW_REPORT", report.id, account_id, None, self._review_snapshot(report))

    def _generic_high_risk_context(self, data: ConfirmationTaskCreate) -> TargetContext:
        """Resolve a generic high-risk target context."""
        if data.account_id is None:
            raise ValueError("account_id is required for HIGH_RISK_CONFIRM without a concrete target_type")
        if not self.repo.get_account(data.account_id):
            raise ValueError("Account profile does not exist")
        snapshot = {"target_id": data.target_id, "extra_context": data.extra_context}
        return TargetContext(None, "HIGH_RISK_TARGET", data.target_id, data.account_id, None, snapshot)

    def _risk_level(self, confirmation_type: ConfirmationType, context: TargetContext) -> str:
        """Calculate task risk level from type and target snapshot."""
        if confirmation_type == ConfirmationType.HIGH_RISK_CONFIRM:
            return "HIGH"
        return str(context.snapshot.get("risk_level") or "LOW").upper()

    def _risk_reason(self, confirmation_type: ConfirmationType, context: TargetContext) -> str:
        """Build a human-readable risk reason."""
        risk_points = context.snapshot.get("risk_points") or context.snapshot.get("issues") or []
        if confirmation_type == ConfirmationType.HIGH_RISK_CONFIRM:
            return "High-risk operation requires an explicit human decision."
        if risk_points:
            return f"Target has risk evidence: {risk_points}"
        return "No high-risk evidence was found in the target snapshot."

    def _summary(self, confirmation_type: ConfirmationType, context: TargetContext) -> str:
        """Build a confirmation task summary."""
        builders: dict[ConfirmationType, Callable[[TargetContext], str]] = {
            ConfirmationType.EXPERIMENT_CONFIRM: lambda item: f"Confirm experiment: {item.snapshot.get('experiment_name')}",
            ConfirmationType.DRAFT_CONFIRM: lambda item: f"Confirm draft v{item.target_version}: {item.snapshot.get('recommended_title') or item.snapshot.get('title')}",
            ConfirmationType.REVIEW_CONFIRM: lambda item: f"Confirm review report: score={item.snapshot.get('score')}, passed={item.snapshot.get('passed')}",
            ConfirmationType.PUBLISH_CONFIRM: lambda item: f"Confirm publish readiness for draft v{item.target_version}: {item.snapshot.get('recommended_title') or item.snapshot.get('title')}",
            ConfirmationType.HIGH_RISK_CONFIRM: lambda item: f"Confirm high-risk target {item.target_type}#{item.target_id}",
        }
        return builders[confirmation_type](context)

    def _recommendation(self, confirmation_type: ConfirmationType, risk_level: str, context: TargetContext) -> str:
        """Build a system recommendation for the task."""
        high_risk_recommendation = "Review risk evidence carefully. Do not approve unless the operator has checked the target manually."
        default_recommendations = {
            ConfirmationType.EXPERIMENT_CONFIRM: "Approve only if the hypothesis, metric, and fallback strategy are clear.",
            ConfirmationType.DRAFT_CONFIRM: "Approve only if the draft is aligned with the experiment and has no unsafe claims.",
            ConfirmationType.REVIEW_CONFIRM: "Approve only if review issues are acceptable or already resolved.",
            ConfirmationType.PUBLISH_CONFIRM: "Approve only if the current draft version is still the intended version. This does not publish automatically.",
            ConfirmationType.HIGH_RISK_CONFIRM: high_risk_recommendation,
        }
        return high_risk_recommendation if risk_level == "HIGH" else default_recommendations[confirmation_type]

    def _ensure_task_can_decide(self, task: ConfirmationTask) -> None:
        """Ensure a task can still accept a human decision."""
        if task.status != ConfirmationTaskStatus.PENDING.value:
            raise ValueError(f"Confirmation task is not pending: {task.status}")

    def _ensure_high_risk_not_ignored(self, task: ConfirmationTask, data: ConfirmationDecisionCreate) -> None:
        """Block ignore-like decisions for high-risk tasks."""
        if task.risk_level == "HIGH" and data.decision in IGNORED_DECISIONS_FOR_HIGH_RISK:
            raise ValueError("High-risk confirmation tasks cannot be paused or cancelled without an explicit approve/reject/revision decision")

    def _ensure_stale_publish_task_invalidated(self, task: ConfirmationTask) -> ConfirmationTask:
        """Invalidate a publish confirmation if its draft version is stale."""
        if task.confirmation_type != ConfirmationType.PUBLISH_CONFIRM.value or task.status != ConfirmationTaskStatus.PENDING.value:
            return task
        draft = self.repo.get_draft(task.target_id)
        if draft and task.target_version != draft.version:
            previous_status = task.status
            task = self.repo.update_task_status(task, ConfirmationTaskStatus.INVALIDATED.value, "draft version changed")
            self._audit(task.id, "INVALIDATED", previous_status, task.status, "system", "draft version changed", {"current_version": draft.version})
        return task

    def _apply_target_transition(self, task: ConfirmationTask, data: ConfirmationDecisionCreate) -> None:
        """Apply conservative target status transitions after a decision."""
        target = self._target_for_task(task)
        transitions = {
            ConfirmationDecisionType.APPROVED: {
                ConfirmationType.EXPERIMENT_CONFIRM.value: "APPROVED",
                ConfirmationType.DRAFT_CONFIRM.value: "REVIEWING",
                ConfirmationType.REVIEW_CONFIRM.value: "READY_TO_PUBLISH",
                ConfirmationType.PUBLISH_CONFIRM.value: "READY_TO_PUBLISH",
            },
            ConfirmationDecisionType.REJECTED: {},
            ConfirmationDecisionType.REVISION_REQUESTED: {"default": "REVISION_REQUESTED"},
            ConfirmationDecisionType.REGENERATE_REQUESTED: {"default": "REGENERATE_REQUESTED"},
            ConfirmationDecisionType.PAUSED: {"default": "PAUSED"},
            ConfirmationDecisionType.CANCELLED: {"default": "CANCELLED"},
        }
        status = transitions[data.decision].get(task.confirmation_type) or transitions[data.decision].get("default")
        if target is not None and status:
            self.repo.update_object_status(target, status)

    def _target_for_task(self, task: ConfirmationTask):
        """Load the target object for a task."""
        loaders = {
            "CONTENT_EXPERIMENT": self.repo.get_experiment,
            "CONTENT_DRAFT": self.repo.get_draft,
            "REVIEW_REPORT": self.repo.get_review_report,
        }
        loader = loaders.get(task.target_type)
        return loader(task.target_id) if loader else None

    def _build_response(self, task: ConfirmationTask) -> ConfirmationTaskResponse:
        """Build a task response with decisions and audit logs."""
        return ConfirmationTaskResponse.model_validate(
            {
                "id": task.id,
                "account_id": task.account_id,
                "confirmation_type": task.confirmation_type,
                "target_type": task.target_type,
                "target_id": task.target_id,
                "target_version": task.target_version,
                "status": task.status,
                "summary": task.summary,
                "recommendation": task.recommendation,
                "risk_level": task.risk_level,
                "risk_reason": task.risk_reason,
                "payload_snapshot": task.payload_snapshot,
                "invalidated_reason": task.invalidated_reason,
                "created_by": task.created_by,
                "created_at": task.created_at,
                "updated_at": task.updated_at,
                "decisions": [ConfirmationDecisionResponse.model_validate(item) for item in self.repo.list_decisions(task.id)],
                "audit_logs": [ConfirmationAuditLogResponse.model_validate(item) for item in self.repo.list_audit_logs(task.id)],
            }
        )

    def _audit(self, task_id: int, event_type: str, from_status: str | None, to_status: str, actor: str | None, reason: str | None, metadata: dict) -> None:
        """Write a confirmation audit log."""
        self.repo.create_audit_log(
            {
                "task_id": task_id,
                "event_type": event_type,
                "from_status": from_status,
                "to_status": to_status,
                "actor": actor,
                "reason": reason,
                "metadata_payload": metadata,
            }
        )

    def _get_task_or_raise(self, task_id: int) -> ConfirmationTask:
        """Return a task or raise a business error."""
        task = self.repo.get_task(task_id)
        if not task:
            raise ValueError("Confirmation task does not exist")
        return task

    def _experiment_snapshot(self, experiment: ContentExperiment) -> dict:
        """Create a snapshot for an experiment target."""
        return {
            "experiment_name": experiment.experiment_name,
            "hypothesis": experiment.hypothesis,
            "content_pillar": experiment.content_pillar,
            "primary_metric": experiment.primary_metric,
            "status": experiment.status,
            "risk_level": experiment.risk_level,
        }

    def _draft_snapshot(self, draft: ContentDraft) -> dict:
        """Create a snapshot for a draft target."""
        return {
            "title": draft.title,
            "recommended_title": draft.recommended_title,
            "cover_text": draft.cover_text,
            "body_text": draft.body_text,
            "tag_list": draft.tag_list,
            "version": draft.version,
            "status": draft.status,
        }

    def _review_snapshot(self, report: ReviewReport) -> dict:
        """Create a snapshot for a review report target."""
        return {
            "draft_id": report.draft_id,
            "passed": report.passed,
            "score": report.score,
            "risk_level": report.risk_level,
            "issues": report.issues,
            "suggestions": report.suggestions,
            "status": report.status,
        }
