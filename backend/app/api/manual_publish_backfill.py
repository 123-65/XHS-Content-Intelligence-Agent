from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.manual_publish_backfill import (
    ManualPublishBackfillRequest,
    ManualPublishBackfillResponse,
    PublishedNoteBackfillResponse,
)
from app.services.manual_publish_backfill_sev import (
    ManualPublishBackfillNotFound,
    ManualPublishBackfillService,
)

router = APIRouter(prefix="/agent", tags=["agent-manual-publish-backfill"])


@router.post("/publish-packages/{package_id}/manual-publish", response_model=ManualPublishBackfillResponse)
def record_manual_publish(
    package_id: int,
    data: ManualPublishBackfillRequest,
    db: Session = Depends(get_db),
) -> ManualPublishBackfillResponse:
    try:
        return ManualPublishBackfillService(db).record(package_id, data)
    except ManualPublishBackfillNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/published-notes", response_model=list[PublishedNoteBackfillResponse])
def list_published_notes(
    account_id: int | None = Query(default=None, gt=0),
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
) -> list[PublishedNoteBackfillResponse]:
    return ManualPublishBackfillService(db).list_published_notes(account_id, limit)


@router.get("/published-notes/{published_note_id}", response_model=PublishedNoteBackfillResponse)
def get_published_note(
    published_note_id: int,
    db: Session = Depends(get_db),
) -> PublishedNoteBackfillResponse:
    try:
        return ManualPublishBackfillService(db).get_published_note(published_note_id)
    except ManualPublishBackfillNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
