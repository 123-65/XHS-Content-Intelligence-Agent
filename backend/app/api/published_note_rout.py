from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.response import fail, success
from app.schemas.post_publish import CollectMetricsRequest, PublishedNoteCreate
from app.services.post_publish_sev import PostPublishService

router = APIRouter(prefix="/api/published-notes", tags=["post-publish"])


def _service_error(exc: ValueError, status_code: int) -> JSONResponse:
    """返回统一格式的业务错误响应。"""
    return JSONResponse(status_code=status_code, content=fail(code=status_code, message=str(exc)).model_dump())


@router.post("")
def create_published_note(data: PublishedNoteCreate, db: Session = Depends(get_db)):
    """根据人工提交的发布链接创建已发布笔记。"""
    service = PostPublishService(db)
    try:
        return success(service.create_published_note(data).model_dump(mode="json"))
    except ValueError as exc:
        return _service_error(exc, 400)


@router.get("/{published_note_id}/public-metrics")
def list_public_metrics(published_note_id: int, db: Session = Depends(get_db)):
    """查询已发布笔记的公开指标快照。"""
    service = PostPublishService(db)
    try:
        return success([item.model_dump(mode="json") for item in service.list_public_metrics(published_note_id)])
    except ValueError as exc:
        return _service_error(exc, 404)


@router.post("/{published_note_id}/collect-metrics")
def collect_public_metrics(published_note_id: int, data: CollectMetricsRequest, db: Session = Depends(get_db)):
    """通过人工核对数据回填公开指标。"""
    service = PostPublishService(db)
    try:
        return success(service.collect_public_metrics(published_note_id, data).model_dump(mode="json"))
    except ValueError as exc:
        return _service_error(exc, 400)
