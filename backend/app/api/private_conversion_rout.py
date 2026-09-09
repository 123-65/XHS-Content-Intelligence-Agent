from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.response import fail, success
from app.schemas.post_publish import PrivateConversionSnapshotCreate
from app.services.post_publish_sev import PostPublishService

router = APIRouter(prefix="/api/conversions", tags=["private-conversions"])


def _service_error(exc: ValueError, status_code: int) -> JSONResponse:
    """返回统一格式的业务错误响应。"""
    return JSONResponse(status_code=status_code, content=fail(code=status_code, message=str(exc)).model_dump())


@router.post("/private-snapshots")
def create_private_snapshot(data: PrivateConversionSnapshotCreate, db: Session = Depends(get_db)):
    """创建人工录入的私域转化快照。"""
    service = PostPublishService(db)
    try:
        return success(service.create_private_conversion_snapshot(data).model_dump(mode="json"))
    except ValueError as exc:
        return _service_error(exc, 400)
