from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.draft_revision_apply import DraftRevisionApplyRequest, DraftRevisionApplyResponse
from app.services.draft_revision_apply_sev import DraftRevisionApplyNotFound, DraftRevisionApplyService

router = APIRouter(prefix="/agent/revision-plans", tags=["agent-draft-revision-apply"])


@router.post("/{plan_id}/apply", response_model=DraftRevisionApplyResponse)
def apply_draft_revision_plan(
    plan_id: int,
    data: DraftRevisionApplyRequest,
    db: Session = Depends(get_db),
) -> DraftRevisionApplyResponse:
    try:
        return DraftRevisionApplyService(db).apply(plan_id, data)
    except DraftRevisionApplyNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
