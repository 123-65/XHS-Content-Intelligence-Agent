from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.draft_generation import DraftGenerationRequest, DraftGenerationResponse
from app.services.draft_generation_sev import DraftGenerationNotFound, DraftGenerationService

router = APIRouter(prefix="/agent/content-experiments", tags=["agent-draft-generation"])


@router.post("/{experiment_id}/drafts/generate", response_model=DraftGenerationResponse)
def generate_draft(
    experiment_id: int,
    data: DraftGenerationRequest,
    db: Session = Depends(get_db),
) -> DraftGenerationResponse:
    try:
        return DraftGenerationService(db).generate(experiment_id, data)
    except DraftGenerationNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
