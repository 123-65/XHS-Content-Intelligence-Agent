from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.data_refresh_run import DataRefreshRunCreate, DataRefreshRunResponse
from app.services.data_refresh_run_sev import DataRefreshRunService

router = APIRouter(prefix="/agent/data-refresh/runs", tags=["agent-data-refresh-runs"])


def _service(db: Session) -> DataRefreshRunService:
    """构造数据刷新运行服务。"""
    return DataRefreshRunService(db)


@router.post("", response_model=DataRefreshRunResponse)
def create_data_refresh_run(data: DataRefreshRunCreate, db: Session = Depends(get_db)) -> DataRefreshRunResponse:
    """创建一次用户触发的数据刷新运行。"""
    try:
        return _service(db).create_run(data)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("", response_model=list[DataRefreshRunResponse])
def list_data_refresh_runs(
    account_id: int | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
) -> list[DataRefreshRunResponse]:
    """查询最近的数据刷新运行记录。"""
    try:
        return _service(db).list_runs(account_id=account_id, limit=limit)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/{run_id}", response_model=DataRefreshRunResponse)
def get_data_refresh_run(run_id: int, db: Session = Depends(get_db)) -> DataRefreshRunResponse:
    """查询数据刷新运行详情。"""
    try:
        return _service(db).get_run(run_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
