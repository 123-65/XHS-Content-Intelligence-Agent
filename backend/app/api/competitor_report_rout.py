from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.response import fail, success
from app.schemas.competitor_report import (
    CompetitorReportCreate,
    CompetitorReportResponse,
    ContentOpportunityResponse,
    ViralNoteBreakdownResponse,
)
from app.services.competitor_report_sev import CompetitorReportService

router = APIRouter(prefix="/api/competitor/reports", tags=["竞品分析 V2"])


def _service_error(exc: ValueError, status_code: int) -> JSONResponse:
    """返回业务错误响应。"""
    return JSONResponse(status_code=status_code, content=fail(code=status_code, message=str(exc)).model_dump())


@router.post("")
def create_competitor_report(data: CompetitorReportCreate, db: Session = Depends(get_db)):
    """创建竞品与爆款分析报告。"""
    service = CompetitorReportService(db)
    try:
        report = service.create_report(data)
        return success(CompetitorReportResponse.model_validate(report).model_dump(mode="json"))
    except ValueError as exc:
        return _service_error(exc, 400)


@router.get("/{report_id}")
def get_competitor_report(report_id: int, db: Session = Depends(get_db)):
    """查询竞品与爆款分析报告详情。"""
    service = CompetitorReportService(db)
    try:
        report = service.get_report(report_id)
        return success(CompetitorReportResponse.model_validate(report).model_dump(mode="json"))
    except ValueError as exc:
        return _service_error(exc, 404)


@router.get("/{report_id}/viral-notes")
def list_viral_notes(report_id: int, db: Session = Depends(get_db)):
    """查询报告下的爆款笔记拆解。"""
    service = CompetitorReportService(db)
    try:
        result = [
            ViralNoteBreakdownResponse.model_validate(item).model_dump(mode="json")
            for item in service.list_viral_breakdowns(report_id)
        ]
        return success(result)
    except ValueError as exc:
        return _service_error(exc, 404)


@router.get("/{report_id}/opportunities")
def list_opportunities(report_id: int, db: Session = Depends(get_db)):
    """查询报告下的内容机会。"""
    service = CompetitorReportService(db)
    try:
        result = [
            ContentOpportunityResponse.model_validate(item).model_dump(mode="json")
            for item in service.list_opportunities(report_id)
        ]
        return success(result)
    except ValueError as exc:
        return _service_error(exc, 404)
