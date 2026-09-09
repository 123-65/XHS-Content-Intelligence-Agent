from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.response import fail, success
from app.schemas.post_publish import ReviewCreate
from app.services.post_publish_sev import PostPublishService

router = APIRouter(prefix="/api/reviews", tags=["post-publish-reviews"])


def _service_error(exc: ValueError, status_code: int) -> JSONResponse:
    """返回统一格式的业务错误响应。"""
    return JSONResponse(status_code=status_code, content=fail(code=status_code, message=str(exc)).model_dump())


@router.post("")
def create_review(data: ReviewCreate, db: Session = Depends(get_db)):
    """创建发布后复盘报告。"""
    service = PostPublishService(db)
    try:
        return success(service.create_review(data).model_dump(mode="json"))
    except ValueError as exc:
        return _service_error(exc, 400)


@router.get("/memories")
def list_memories(account_id: int = Query(...), db: Session = Depends(get_db)):
    """查询账号的策略记忆列表。"""
    service = PostPublishService(db)
    try:
        return success([item.model_dump(mode="json") for item in service.list_memories(account_id)])
    except ValueError as exc:
        return _service_error(exc, 400)


@router.get("/{review_report_id}")
def get_review(review_report_id: int, db: Session = Depends(get_db)):
    """查询发布后复盘报告详情。"""
    service = PostPublishService(db)
    try:
        return success(service.get_review(review_report_id).model_dump(mode="json"))
    except ValueError as exc:
        return _service_error(exc, 404)


@router.post("/{review_report_id}/memories/extract")
def extract_memories(review_report_id: int, db: Session = Depends(get_db)):
    """从发布后复盘报告中提取候选策略记忆。"""
    service = PostPublishService(db)
    try:
        return success(service.extract_memories(review_report_id).model_dump(mode="json"))
    except ValueError as exc:
        return _service_error(exc, 400)
