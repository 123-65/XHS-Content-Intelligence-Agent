from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.response import fail, success
from app.schemas.post_publish import OptimizationGenerateRequest
from app.services.post_publish_sev import PostPublishService

router = APIRouter(prefix="/api/optimizations", tags=["optimizations"])


def _service_error(exc: ValueError, status_code: int) -> JSONResponse:
    """返回统一格式的业务错误响应。"""
    return JSONResponse(status_code=status_code, content=fail(code=status_code, message=str(exc)).model_dump())


@router.post("/generate")
def generate_optimization(data: OptimizationGenerateRequest, db: Session = Depends(get_db)):
    """生成下一轮内容优化计划。"""
    service = PostPublishService(db)
    try:
        return success(service.generate_optimization(data).model_dump(mode="json"))
    except ValueError as exc:
        return _service_error(exc, 400)


@router.post("/{optimization_plan_id}/apply")
def apply_optimization(optimization_plan_id: int, db: Session = Depends(get_db)):
    """应用内容优化计划并按需创建候选实验。"""
    service = PostPublishService(db)
    try:
        return success(service.apply_optimization(optimization_plan_id).model_dump(mode="json"))
    except ValueError as exc:
        return _service_error(exc, 400)
