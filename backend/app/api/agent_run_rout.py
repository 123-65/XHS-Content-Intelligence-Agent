from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.response import fail, success
from app.context.context_usage_logger import ContextUsageLogger
from app.models.agent_run import AgentRun
from app.schemas.context import AgentRunContextResponse, ContextSnapshotResponse
from app.services.agent_run_sev import AgentRunService

router = APIRouter(prefix="/api/agent-runs", tags=["agent-runs"])


def _service_error(exc: ValueError, status_code: int) -> JSONResponse:
    """返回统一格式的业务错误响应。"""
    return JSONResponse(status_code=status_code, content=fail(code=status_code, message=str(exc)).model_dump())


@router.get("")
def list_agent_runs(account_id: int | None = Query(default=None), db: Session = Depends(get_db)):
    """查询 AgentRun 列表。"""
    service = AgentRunService(db)
    return success([item.model_dump(mode="json") for item in service.list_runs(account_id)])


@router.get("/{agent_run_id}")
def get_agent_run(agent_run_id: int, db: Session = Depends(get_db)):
    """查询 AgentRun 详情。"""
    service = AgentRunService(db)
    try:
        return success(service.get_run(agent_run_id).model_dump(mode="json"))
    except ValueError as exc:
        return _service_error(exc, 404)


@router.get("/{agent_run_id}/steps")
def list_agent_steps(agent_run_id: int, db: Session = Depends(get_db)):
    """查询 AgentRun 步骤列表。"""
    service = AgentRunService(db)
    try:
        return success([item.model_dump(mode="json") for item in service.list_steps(agent_run_id)])
    except ValueError as exc:
        return _service_error(exc, 404)


@router.get("/{agent_run_id}/context")
def list_agent_run_context(agent_run_id: int, db: Session = Depends(get_db)):
    """Return context snapshots linked to an AgentRun."""
    if not db.get(AgentRun, agent_run_id):
        return _service_error(ValueError("AgentRun does not exist"), 404)
    snapshots = ContextUsageLogger(db).list_snapshots_for_run(agent_run_id)
    response = AgentRunContextResponse(
        agent_run_id=agent_run_id,
        snapshots=[ContextSnapshotResponse.model_validate(item).model_dump(mode="json") for item in snapshots],
    )
    return success(response.model_dump(mode="json"))
