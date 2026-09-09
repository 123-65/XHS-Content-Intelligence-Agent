from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.response import fail, success
from app.llm.errors import LLMError
from app.schemas.content_draft_v2 import CreateDraftVersionRequest, GenerateDraftV2Request, RegenerateDraftRequest
from app.services.content_draft_v2_sev import ContentDraftV2Service

router = APIRouter(prefix="/api/drafts", tags=["content-draft-v2"])


def _error_response(exc: Exception, status_code: int) -> JSONResponse:
    """Return a normalized error response."""
    return JSONResponse(status_code=status_code, content=fail(code=status_code, message=str(exc)).model_dump())


@router.post("/generate")
def generate_draft(data: GenerateDraftV2Request, db: Session = Depends(get_db)):
    """Generate a draft from an approved experiment."""
    service = ContentDraftV2Service(db)
    try:
        return success(service.generate_draft(data).model_dump(mode="json"))
    except ValueError as exc:
        return _error_response(exc, 400)
    except LLMError as exc:
        return _error_response(exc, 500)


@router.get("/{draft_id}")
def get_draft(draft_id: int, db: Session = Depends(get_db)):
    """Get a draft by ID."""
    service = ContentDraftV2Service(db)
    try:
        return success(service.get_draft(draft_id).model_dump(mode="json"))
    except ValueError as exc:
        return _error_response(exc, 404)


@router.post("/{draft_id}/regenerate")
def regenerate_draft(draft_id: int, data: RegenerateDraftRequest, db: Session = Depends(get_db)):
    """Regenerate selected draft fields."""
    service = ContentDraftV2Service(db)
    try:
        return success(service.regenerate_draft(draft_id, data).model_dump(mode="json"))
    except ValueError as exc:
        return _error_response(exc, 400)
    except LLMError as exc:
        return _error_response(exc, 500)


@router.post("/{draft_id}/versions")
def create_draft_version(
    draft_id: int,
    data: CreateDraftVersionRequest | None = None,
    db: Session = Depends(get_db),
):
    """Create a manual draft version snapshot."""
    service = ContentDraftV2Service(db)
    try:
        return success(service.create_version(draft_id).model_dump(mode="json"))
    except ValueError as exc:
        return _error_response(exc, 404)
