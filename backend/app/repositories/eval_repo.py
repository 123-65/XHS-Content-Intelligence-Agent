from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.models.eval_case import EvalCase
from app.models.eval_run import EvalRun
from app.schemas.eval import EvalCaseCreate, EvalRunCreate


class EvalRepository:
    """Database access layer for evaluation records."""

    def __init__(self, db: Session):
        """Initialize the evaluation repository."""
        self.db = db

    def upsert_case(self, data: EvalCaseCreate) -> EvalCase:
        """Create or update an evaluation case by suite and key."""
        case = (
            self.db.query(EvalCase)
            .filter(EvalCase.suite_name == data.suite_name, EvalCase.case_key == data.case_key)
            .one_or_none()
        )
        if not case:
            case = EvalCase(**data.model_dump())
            self.db.add(case)
        else:
            payload = data.model_dump()
            for key, value in payload.items():
                setattr(case, key, value)
        self.db.commit()
        self.db.refresh(case)
        return case

    def create_run(self, data: EvalRunCreate) -> EvalRun:
        """Create an evaluation run record."""
        run = EvalRun(**data.model_dump(), finished_at=datetime.now(UTC).replace(tzinfo=None))
        self.db.add(run)
        self.db.commit()
        self.db.refresh(run)
        return run
