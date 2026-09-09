from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.response import fail, success
from app.schemas.competitor_analysis import CompetitorAnalysisCreate, CompetitorAnalysisResponse
from app.services.competitor_analysis_sev import CompetitorAnalysisService

router = APIRouter(prefix="/competitor-analysis", tags=["竞品分析"])


@router.post("")
def create_competitor_analysis(data: CompetitorAnalysisCreate, db: Session = Depends(get_db)):
    """创建竞品内容分析报告。"""
    service = CompetitorAnalysisService(db)
    try:
        report = service.create_analysis(data)
        result = CompetitorAnalysisResponse.model_validate(report).model_dump(mode="json")
        return success(result)
    except ValueError as exc:
        return JSONResponse(status_code=400, content=fail(str(exc), code=400).model_dump())


@router.get("")
def list_competitor_analysis(
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """查询竞品内容分析报告列表。"""
    service = CompetitorAnalysisService(db)
    reports = service.list_reports(limit)
    result = [CompetitorAnalysisResponse.model_validate(item).model_dump(mode="json") for item in reports]
    return success(result)


@router.get("/{report_id}")
def get_competitor_analysis(report_id: int, db: Session = Depends(get_db)):
    """查询竞品内容分析报告详情。"""
    service = CompetitorAnalysisService(db)
    try:
        report = service.get_report(report_id)
        result = CompetitorAnalysisResponse.model_validate(report).model_dump(mode="json")
        return success(result)
    except ValueError as exc:
        return JSONResponse(status_code=404, content=fail(str(exc), code=404).model_dump())