from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.draft_context_preview import DraftContextPreviewRequest, DraftContextPreviewResponse
from app.services.draft_context_preview_sev import DraftContextPreviewNotFound, DraftContextPreviewService

router = APIRouter(prefix="/agent/content-experiments", tags=["agent-draft-context-preview"])


def _service(db: Session) -> DraftContextPreviewService:
    return DraftContextPreviewService(db)


@router.post("/{experiment_id}/draft-context/preview", response_model=DraftContextPreviewResponse)
def preview_draft_context(
    experiment_id: int,
    data: DraftContextPreviewRequest,
    db: Session = Depends(get_db),
) -> DraftContextPreviewResponse:
    try:
        return _service(db).preview(experiment_id, data)
    except DraftContextPreviewNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
