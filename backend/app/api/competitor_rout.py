from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.response import fail, success
from app.schemas.crawler_collection import CompetitorAccountResponse, CompetitorNoteResponse
from app.services.crawler_collection_sev import CrawlerCollectionService

router = APIRouter(prefix="/api/competitor", tags=["竞品数据"])


def _service_error(exc: ValueError, status_code: int) -> JSONResponse:
    """返回业务错误响应。"""
    return JSONResponse(status_code=status_code, content=fail(code=status_code, message=str(exc)).model_dump())


@router.get("/accounts")
def list_competitor_accounts(account_id: int = Query(...), db: Session = Depends(get_db)):
    """查询同行账号快照列表。"""
    service = CrawlerCollectionService(db)
    try:
        result = [CompetitorAccountResponse.model_validate(item).model_dump(mode="json") for item in service.list_competitor_accounts(account_id)]
        return success(result)
    except ValueError as exc:
        return _service_error(exc, 404)


@router.get("/notes")
def list_competitor_notes(account_id: int = Query(...), db: Session = Depends(get_db)):
    """查询竞品笔记快照列表。"""
    service = CrawlerCollectionService(db)
    try:
        result = [CompetitorNoteResponse.model_validate(item).model_dump(mode="json") for item in service.list_competitor_notes(account_id)]
        return success(result)
    except ValueError as exc:
        return _service_error(exc, 404)
