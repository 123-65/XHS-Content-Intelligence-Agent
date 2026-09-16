from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.xhs_url_collect import XhsUrlCollectRequest, XhsUrlCollectResponse
from app.services.xhs_url_collect_sev import XhsUrlCollectService

router = APIRouter(prefix="/agent/xhs/url-collect", tags=["agent-xhs-url-collect-v0"])


@router.post("", response_model=XhsUrlCollectResponse)
def collect_xhs_urls(data: XhsUrlCollectRequest, db: Session = Depends(get_db)) -> XhsUrlCollectResponse:
    try:
        return XhsUrlCollectService(db).collect(data)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/runs", response_model=list[XhsUrlCollectResponse])
def list_xhs_url_collect_runs(
    account_id: int | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
) -> list[XhsUrlCollectResponse]:
    return XhsUrlCollectService(db).list_runs(account_id=account_id, limit=limit)


@router.get("/runs/{run_id}", response_model=XhsUrlCollectResponse)
def get_xhs_url_collect_run(run_id: int, db: Session = Depends(get_db)) -> XhsUrlCollectResponse:
    try:
        return XhsUrlCollectService(db).get_run(run_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
