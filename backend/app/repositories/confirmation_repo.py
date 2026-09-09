from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.account import AccountProfile
from app.models.confirmation_audit_log import ConfirmationAuditLog
from app.models.confirmation_decision import ConfirmationDecision
from app.models.confirmation_task import ConfirmationTask
from app.models.content_draft import ContentDraft
from app.models.content_experiment import ContentExperiment
from app.models.review_report import ReviewReport


class ConfirmationRepository:
    """Database access layer for human confirmation."""

    def __init__(self, db: Session):
        """Initialize the repository."""
        self.db = db

    def get_account(self, account_id: int) -> AccountProfile | None:
        """Get an account profile by ID."""
        return self.db.get(AccountProfile, account_id)

    def get_experiment(self, experiment_id: int) -> ContentExperiment | None:
        """Get an experiment by ID."""
        return self.db.get(ContentExperiment, experiment_id)

    def get_draft(self, draft_id: int) -> ContentDraft | None:
        """Get a draft by ID."""
        return self.db.get(ContentDraft, draft_id)

    def get_review_report(self, report_id: int) -> ReviewReport | None:
        """Get a review report by ID."""
        return self.db.get(ReviewReport, report_id)

    def create_task(self, fields: dict) -> ConfirmationTask:
        """Create a confirmation task."""
        task = ConfirmationTask(**fields)
        self.db.add(task)
        self.db.commit()
        self.db.refresh(task)
        return task

    def get_task(self, task_id: int) -> ConfirmationTask | None:
        """Get a confirmation task by ID."""
        return self.db.get(ConfirmationTask, task_id)

    def list_pending_tasks(self, account_id: int | None = None) -> list[ConfirmationTask]:
        """List pending confirmation tasks."""
        stmt = select(ConfirmationTask).where(ConfirmationTask.status == "PENDING")
        if account_id is not None:
            stmt = stmt.where(ConfirmationTask.account_id == account_id)
        stmt = stmt.order_by(ConfirmationTask.created_at.asc(), ConfirmationTask.id.asc())
        return list(self.db.execute(stmt).scalars().all())

    def list_decisions(self, task_id: int) -> list[ConfirmationDecision]:
        """List decisions for a task."""
        stmt = select(ConfirmationDecision).where(ConfirmationDecision.task_id == task_id).order_by(ConfirmationDecision.created_at.asc(), ConfirmationDecision.id.asc())
        return list(self.db.execute(stmt).scalars().all())

    def list_audit_logs(self, task_id: int) -> list[ConfirmationAuditLog]:
        """List audit logs for a task."""
        stmt = select(ConfirmationAuditLog).where(ConfirmationAuditLog.task_id == task_id).order_by(ConfirmationAuditLog.created_at.asc(), ConfirmationAuditLog.id.asc())
        return list(self.db.execute(stmt).scalars().all())

    def create_decision(self, task_id: int, data) -> ConfirmationDecision:
        """Create a decision for a task."""
        decision = ConfirmationDecision(task_id=task_id, **data.model_dump())
        self.db.add(decision)
        self.db.commit()
        self.db.refresh(decision)
        return decision

    def create_audit_log(self, fields: dict) -> ConfirmationAuditLog:
        """Create an audit log record."""
        log = ConfirmationAuditLog(**fields)
        self.db.add(log)
        self.db.commit()
        self.db.refresh(log)
        return log

    def update_task_status(self, task: ConfirmationTask, status: str, invalidated_reason: str | None = None) -> ConfirmationTask:
        """Update a confirmation task status."""
        task.status = status
        if invalidated_reason:
            task.invalidated_reason = invalidated_reason
        self.db.commit()
        self.db.refresh(task)
        return task

    def update_object_status(self, obj, status: str) -> None:
        """Update a target object status when it exposes a status field."""
        if hasattr(obj, "status"):
            obj.status = status
            self.db.commit()

    def list_pending_publish_tasks_for_draft(self, draft_id: int) -> list[ConfirmationTask]:
        """List pending publish confirmations for a draft."""
        stmt = select(ConfirmationTask).where(
            ConfirmationTask.confirmation_type == "PUBLISH_CONFIRM",
            ConfirmationTask.target_type == "CONTENT_DRAFT",
            ConfirmationTask.target_id == draft_id,
            ConfirmationTask.status == "PENDING",
        )
        return list(self.db.execute(stmt).scalars().all())
