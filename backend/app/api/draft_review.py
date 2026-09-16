from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.draft_review import DraftReviewRequest, DraftReviewResponse
from app.services.draft_review_sev import DraftReviewNotFound, DraftReviewService

router = APIRouter(prefix="/agent/drafts", tags=["agent-draft-review"])


@router.post("/{draft_id}/review", response_model=DraftReviewResponse)
def review_draft(
    draft_id: int,
    data: DraftReviewRequest,
    db: Session = Depends(get_db),
) -> DraftReviewResponse:
    try:
        return DraftReviewService(db).review(draft_id, data)
    except DraftReviewNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
