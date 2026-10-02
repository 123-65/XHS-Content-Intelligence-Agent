from sqlalchemy import select

from app.models.workflow_operation import WorkflowOperation


class WorkflowOperationRepository:
    """Flush-only persistence for successful durable side-effect operations."""

    def __init__(self, db):
        self.db = db

    def get_succeeded(self, run_ref: str, operation_key: str) -> WorkflowOperation | None:
        statement = select(WorkflowOperation).where(
            WorkflowOperation.run_ref == run_ref,
            WorkflowOperation.operation_key == operation_key,
        )
        return self.db.execute(statement).scalar_one_or_none()

    def create_succeeded(
        self,
        *,
        run_ref: str,
        workflow_name: str,
        operation_key: str,
        tool_name: str,
        identity_fingerprint: str,
        result_snapshot: dict,
    ) -> WorkflowOperation:
        record = WorkflowOperation(
            run_ref=run_ref,
            workflow_name=workflow_name,
            operation_key=operation_key,
            tool_name=tool_name,
            identity_fingerprint=identity_fingerprint,
            result_snapshot=result_snapshot,
        )
        self.db.add(record)
        self.db.flush()
        return record
