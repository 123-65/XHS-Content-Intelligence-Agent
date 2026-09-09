from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.response import fail, success
from app.schemas.crawler_collection import CrawlTaskCreate, CrawlTaskResponse
from app.services.crawler_collection_sev import CrawlerCollectionService

router = APIRouter(prefix="/api/crawler/tasks", tags=["采集任务"])


def _serialize_task(task) -> dict:
    """序列化采集任务响应。"""
    return CrawlTaskResponse.model_validate(task).model_dump(mode="json")


def _service_error(exc: ValueError, status_code: int) -> JSONResponse:
    """返回业务错误响应。"""
    return JSONResponse(status_code=status_code, content=fail(code=status_code, message=str(exc)).model_dump())


@router.post("")
def create_crawl_task(data: CrawlTaskCreate, db: Session = Depends(get_db)):
    """创建采集任务。"""
    service = CrawlerCollectionService(db)
    try:
        return success(_serialize_task(service.create_task(data)))
    except ValueError as exc:
        return _service_error(exc, 400)


@router.post("/{task_id}/run")
def run_crawl_task(task_id: int, db: Session = Depends(get_db)):
    """运行采集任务。"""
    service = CrawlerCollectionService(db)
    try:
        return success(_serialize_task(service.run_task(task_id)))
    except ValueError as exc:
        return _service_error(exc, 404)


@router.get("/{task_id}")
def get_crawl_task(task_id: int, db: Session = Depends(get_db)):
    """查询采集任务详情。"""
    service = CrawlerCollectionService(db)
    try:
        return success(_serialize_task(service.get_task(task_id)))
    except ValueError as exc:
        return _service_error(exc, 404)
