from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.operation_run import OperationRunCreate, OperationRunResponse
from app.services.operation_run_sev import OperationRunService

router = APIRouter(prefix="/agent/operation-runs", tags=["agent-operation-runs"])


def _service(db: Session) -> OperationRunService:
    return OperationRunService(db)


@router.post("", response_model=OperationRunResponse)
def create_operation_run(data: OperationRunCreate, db: Session = Depends(get_db)) -> OperationRunResponse:
    try:
        service = _service(db)
        return service.to_response(service.create_run(data))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("", response_model=list[OperationRunResponse])
def list_operation_runs(
    account_id: int = Query(...),
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
) -> list[OperationRunResponse]:
    try:
        return _service(db).list_runs(account_id=account_id, limit=limit)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/{run_id}", response_model=OperationRunResponse)
def get_operation_run(run_id: int, db: Session = Depends(get_db)) -> OperationRunResponse:
    try:
        return _service(db).get_run(run_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
