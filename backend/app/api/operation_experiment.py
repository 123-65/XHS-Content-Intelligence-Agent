from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.operation_experiment import OperationExperimentRequest, OperationExperimentResponse
from app.services.operation_experiment_sev import OperationExperimentNotFound, OperationExperimentService

router = APIRouter(prefix="/agent/operation-runs", tags=["agent-operation-experiments"])


def _service(db: Session) -> OperationExperimentService:
    return OperationExperimentService(db)


@router.post("/{run_id}/recommendations/{rank}/experiment-preview", response_model=OperationExperimentResponse)
def preview_operation_experiment(
    run_id: int,
    rank: int,
    data: OperationExperimentRequest,
    db: Session = Depends(get_db),
) -> OperationExperimentResponse:
    try:
        return _service(db).preview_from_recommendation(run_id, rank, data.account_id, data)
    except OperationExperimentNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/{run_id}/recommendations/{rank}/experiments", response_model=OperationExperimentResponse)
def create_operation_experiment(
    run_id: int,
    rank: int,
    data: OperationExperimentRequest,
    db: Session = Depends(get_db),
) -> OperationExperimentResponse:
    try:
        return _service(db).create_from_recommendation(run_id, rank, data)
    except OperationExperimentNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
