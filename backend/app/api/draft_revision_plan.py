from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.draft_revision_plan import (
    DraftRevisionPlanRecord,
    DraftRevisionPlanRequest,
    DraftRevisionPlanResponse,
)
from app.services.draft_revision_plan_sev import DraftRevisionPlanNotFound, DraftRevisionPlanningService

router = APIRouter(prefix="/agent", tags=["agent-draft-revision-plan"])


@router.post("/drafts/{draft_id}/revision-plans", response_model=DraftRevisionPlanResponse)
def create_draft_revision_plan(
    draft_id: int,
    data: DraftRevisionPlanRequest,
    db: Session = Depends(get_db),
) -> DraftRevisionPlanResponse:
    try:
        return DraftRevisionPlanningService(db).create_plan(draft_id, data)
    except DraftRevisionPlanNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/drafts/{draft_id}/revision-plans", response_model=list[DraftRevisionPlanRecord])
def list_draft_revision_plans(
    draft_id: int,
    db: Session = Depends(get_db),
) -> list[DraftRevisionPlanRecord]:
    try:
        return DraftRevisionPlanningService(db).list_by_draft(draft_id)
    except DraftRevisionPlanNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/revision-plans/{plan_id}", response_model=DraftRevisionPlanRecord)
def get_draft_revision_plan(
    plan_id: int,
    db: Session = Depends(get_db),
) -> DraftRevisionPlanRecord:
    try:
        return DraftRevisionPlanningService(db).get_plan(plan_id)
    except DraftRevisionPlanNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
