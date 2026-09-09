from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.response import fail, success
from app.schemas.confirmation import ConfirmationDecisionCreate, ConfirmationTaskCreate
from app.services.confirmation_sev import ConfirmationService

router = APIRouter(prefix="/api/confirmations", tags=["confirmations"])


def _service_error(exc: ValueError, status_code: int) -> JSONResponse:
    """Return a normalized business error response."""
    return JSONResponse(status_code=status_code, content=fail(code=status_code, message=str(exc)).model_dump())


@router.post("")
def create_confirmation(data: ConfirmationTaskCreate, db: Session = Depends(get_db)):
    """Create a human confirmation task."""
    service = ConfirmationService(db)
    try:
        return success(service.create_task(data).model_dump(mode="json"))
    except ValueError as exc:
        return _service_error(exc, 400)


@router.get("/pending")
def list_pending_confirmations(account_id: int | None = Query(default=None), db: Session = Depends(get_db)):
    """List pending human confirmation tasks."""
    service = ConfirmationService(db)
    return success(service.list_pending_tasks(account_id).model_dump(mode="json"))


@router.get("/{task_id}")
def get_confirmation(task_id: int, db: Session = Depends(get_db)):
    """Get a human confirmation task detail."""
    service = ConfirmationService(db)
    try:
        return success(service.get_task(task_id).model_dump(mode="json"))
    except ValueError as exc:
        return _service_error(exc, 404)


@router.post("/{task_id}/decision")
def submit_confirmation_decision(task_id: int, data: ConfirmationDecisionCreate, db: Session = Depends(get_db)):
    """Submit a human confirmation decision."""
    service = ConfirmationService(db)
    try:
        return success(service.submit_decision(task_id, data).model_dump(mode="json"))
    except ValueError as exc:
        return _service_error(exc, 400)
