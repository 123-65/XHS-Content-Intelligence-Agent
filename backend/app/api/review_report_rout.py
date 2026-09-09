from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.response import fail, success
from app.llm.errors import LLMError
from app.schemas.review_report import ReviewDraftRequest, ReviewReportResponse
from app.services.review_report_sev import ReviewReportService

router = APIRouter(prefix="/reviews", tags=["内容审核"])


def _serialize_report(report) -> dict:
    """序列化审核报告响应。"""
    return ReviewReportResponse.model_validate(report).model_dump(mode="json")


def _service_error(exc: ValueError, status_code: int) -> JSONResponse:
    """返回业务错误响应。"""
    return JSONResponse(status_code=status_code, content=fail(code=status_code, message=str(exc)).model_dump())


def _llm_error(exc: LLMError) -> JSONResponse:
    """返回模型调用错误响应。"""
    return JSONResponse(status_code=500, content=fail(code=500, message=str(exc)).model_dump())


@router.post("/draft")
def review_draft(data: ReviewDraftRequest, db: Session = Depends(get_db)):
    """审核内容草稿。"""
    service = ReviewReportService(db)
    try:
        return success(_serialize_report(service.review_draft(data)))
    except ValueError as exc:
        return _service_error(exc, 400)
    except LLMError as exc:
        return _llm_error(exc)


@router.get("/draft/{draft_id}")
def list_reports_by_draft(draft_id: int, db: Session = Depends(get_db)):
    """查询某个草稿的审核报告列表。"""
    service = ReviewReportService(db)
    result = [_serialize_report(item) for item in service.list_reports_by_draft(draft_id)]
    return success(result)


@router.get("/{report_id}")
def get_review_report(report_id: int, db: Session = Depends(get_db)):
    """查询审核报告详情。"""
    service = ReviewReportService(db)
    try:
        return success(_serialize_report(service.get_report(report_id)))
    except ValueError as exc:
        return _service_error(exc, 404)
