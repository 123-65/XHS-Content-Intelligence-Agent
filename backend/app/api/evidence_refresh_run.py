from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.evidence_refresh_run import EvidenceRefreshRunCreate, EvidenceRefreshRunResponse
from app.services.evidence_refresh_run_sev import EvidenceRefreshRunService

router = APIRouter(prefix="/agent/evidence-refresh/runs", tags=["agent-evidence-refresh-runs"])


def _service(db: Session) -> EvidenceRefreshRunService:
    """构造证据刷新运行服务。"""
    return EvidenceRefreshRunService(db)


@router.post("", response_model=EvidenceRefreshRunResponse)
def create_evidence_refresh_run(data: EvidenceRefreshRunCreate, db: Session = Depends(get_db)) -> EvidenceRefreshRunResponse:
    """创建一次用户触发的证据刷新运行。"""
    try:
        service = _service(db)
        return service.to_response(service.create_run(data))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("", response_model=list[EvidenceRefreshRunResponse])
def list_evidence_refresh_runs(
    account_id: int = Query(...),
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
) -> list[EvidenceRefreshRunResponse]:
    """查询账号最近证据刷新运行记录。"""
    try:
        return _service(db).list_runs(account_id=account_id, limit=limit)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/{run_id}", response_model=EvidenceRefreshRunResponse)
def get_evidence_refresh_run(run_id: int, db: Session = Depends(get_db)) -> EvidenceRefreshRunResponse:
    """查询单条证据刷新运行记录。"""
    try:
        return _service(db).get_run(run_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
