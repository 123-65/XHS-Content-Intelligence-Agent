from datetime import UTC, datetime

from sqlalchemy import update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.workflow_run import WorkflowRun


class WorkflowRunRepositoryError(RuntimeError):
    """带稳定错误码的 Workflow Run persistence 错误。"""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


class WorkflowRunRepository:
    """WorkflowRun 的唯一数据库访问层。"""

    def __init__(self, db: Session):
        self.db = db

    def create_run(self, **fields) -> WorkflowRun:
        """创建 version=1 的 durable Workflow Run。"""
        run = WorkflowRun(**fields, checkpoint_version=1)
        self.db.add(run)
        try:
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise WorkflowRunRepositoryError("WORKFLOW_RUN_CONFLICT", "run_ref 已存在。") from exc
        self.db.refresh(run)
        return run

    def get_by_run_ref(self, run_ref: str) -> WorkflowRun | None:
        """按稳定外部引用读取 Run。"""
        return self.db.query(WorkflowRun).filter(WorkflowRun.run_ref == run_ref).one_or_none()

    def save_checkpoint(self, run_ref: str, expected_checkpoint_version: int, *, expected_execution_token=None, **fields) -> WorkflowRun:
        """用 compare-and-swap 保存 checkpoint，拒绝 stale writer。"""
        values = {**fields, "checkpoint_version": expected_checkpoint_version + 1, "updated_at": _now()}
        result = self.db.execute(
            update(WorkflowRun)
            .where(
                WorkflowRun.run_ref == run_ref,
                WorkflowRun.checkpoint_version == expected_checkpoint_version,
                *((WorkflowRun.execution_token == expected_execution_token,) if expected_execution_token is not None else ()),
            )
            .values(**values)
        )
        if result.rowcount != 1:
            self.db.rollback()
            if self.get_by_run_ref(run_ref) is None:
                raise WorkflowRunRepositoryError("WORKFLOW_RUN_NOT_FOUND", "Workflow Run 不存在。")
            current = self.get_by_run_ref(run_ref)
            if expected_execution_token is not None and current and current.execution_token != expected_execution_token:
                raise WorkflowRunRepositoryError("WORKFLOW_EXECUTION_FENCED", "Workflow execution token is no longer current.")
            raise WorkflowRunRepositoryError("WORKFLOW_CHECKPOINT_CONFLICT", "Workflow checkpoint 已被其他请求更新。")
        self.db.commit()
        return self.get_by_run_ref(run_ref)

    def mark_completed(self, run_ref: str, expected_checkpoint_version: int, **fields) -> WorkflowRun:
        """保存成功或部分成功终态。"""
        return self.save_checkpoint(run_ref, expected_checkpoint_version, completed_at=_now(), **fields)

    def mark_failed(self, run_ref: str, expected_checkpoint_version: int, **fields) -> WorkflowRun:
        """保存失败终态。"""
        return self.save_checkpoint(run_ref, expected_checkpoint_version, completed_at=_now(), **fields)

    def mark_cancelled(self, run_ref: str, expected_checkpoint_version: int, **fields) -> WorkflowRun:
        """保存取消终态。"""
        return self.save_checkpoint(run_ref, expected_checkpoint_version, completed_at=_now(), **fields)


def _now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)
