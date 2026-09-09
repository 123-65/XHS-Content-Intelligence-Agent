from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.response import fail, success
from app.services.developer_trace_sev import DeveloperTraceService

router = APIRouter(prefix="/api/developer", tags=["developer-trace"])


def _service_error(exc: ValueError, status_code: int) -> JSONResponse:
    return JSONResponse(status_code=status_code, content=fail(code=status_code, message=str(exc)).model_dump())


@router.get("/agent-runs")
def list_developer_agent_runs(limit: int = Query(default=20, ge=1, le=100), db: Session = Depends(get_db)):
    """Return recent AgentRun summaries for the developer trace console."""
    service = DeveloperTraceService(db)
    return success([item.model_dump(mode="json") for item in service.list_runs(limit)])


@router.get("/agent-runs/{run_id}")
def get_developer_agent_run(run_id: int, db: Session = Depends(get_db)):
    """Return one AgentRun with the full developer trace."""
    service = DeveloperTraceService(db)
    try:
        return success(service.get_run(run_id).model_dump(mode="json"))
    except ValueError as exc:
        return _service_error(exc, 404)


@router.get("/agent-runs/{run_id}/steps")
def list_developer_agent_steps(run_id: int, db: Session = Depends(get_db)):
    """Return one AgentRun timeline."""
    service = DeveloperTraceService(db)
    try:
        return success([item.model_dump(mode="json") for item in service.list_steps(run_id)])
    except ValueError as exc:
        return _service_error(exc, 404)


@router.get("/latest-run")
def get_latest_developer_run(db: Session = Depends(get_db)):
    """Return the latest AgentRun with full trace."""
    service = DeveloperTraceService(db)
    try:
        return success(service.latest_run().model_dump(mode="json"))
    except ValueError as exc:
        return _service_error(exc, 404)


@router.get("/latest-run/steps")
def list_latest_developer_steps(db: Session = Depends(get_db)):
    """Return the latest AgentRun timeline."""
    service = DeveloperTraceService(db)
    try:
        return success([item.model_dump(mode="json") for item in service.latest_steps()])
    except ValueError as exc:
        return _service_error(exc, 404)

