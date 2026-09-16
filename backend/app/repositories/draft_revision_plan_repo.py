from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.draft_revision_plan import DraftRevisionPlan
from app.schemas.draft_revision_plan import DraftRevisionPlanCreate


class DraftRevisionPlanRepository:
    """Database access for B10 draft revision plans."""

    def __init__(self, db: Session):
        self.db = db

    def create(self, data: DraftRevisionPlanCreate) -> DraftRevisionPlan:
        plan = DraftRevisionPlan(**data.model_dump())
        self.db.add(plan)
        self.db.commit()
        self.db.refresh(plan)
        return plan

    def get_by_id(self, plan_id: int) -> DraftRevisionPlan | None:
        return self.db.get(DraftRevisionPlan, plan_id)

    def list_by_draft(self, draft_id: int) -> list[DraftRevisionPlan]:
        stmt = (
            select(DraftRevisionPlan)
            .where(DraftRevisionPlan.draft_id == draft_id)
            .order_by(DraftRevisionPlan.id.desc())
        )
        return list(self.db.execute(stmt).scalars().all())
