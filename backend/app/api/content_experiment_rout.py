from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.response import fail, success
from app.schemas.content_experiment import (
    ContentExperimentCreate,
    ContentExperimentResponse,
    ContentExperimentUpdate,
    CreateExperimentFromAnalysisRequest,
)
from app.services.content_experiment_sev import ContentExperimentService

router = APIRouter(prefix="/experiments", tags=["内容实验"])


def _serialize_experiment(experiment) -> dict:
    """序列化内容实验响应。"""
    return ContentExperimentResponse.model_validate(experiment).model_dump(mode="json")


def _service_error(exc: ValueError, status_code: int) -> JSONResponse:
    """返回业务错误响应。"""
    return JSONResponse(status_code=status_code, content=fail(code=status_code, message=str(exc)).model_dump())


@router.post("")
def create_experiment(data: ContentExperimentCreate, db: Session = Depends(get_db)):
    """创建内容实验。"""
    service = ContentExperimentService(db)
    try:
        return success(_serialize_experiment(service.create_experiment(data)))
    except ValueError as exc:
        return _service_error(exc, 400)


@router.post("/from-analysis/{analysis_report_id}")
def create_experiment_from_analysis(
    analysis_report_id: int,
    data: CreateExperimentFromAnalysisRequest,
    db: Session = Depends(get_db),
):
    """基于竞品分析报告创建内容实验。"""
    service = ContentExperimentService(db)
    try:
        return success(_serialize_experiment(service.create_from_analysis(analysis_report_id, data)))
    except ValueError as exc:
        return _service_error(exc, 400)


@router.get("")
def list_experiments(
    account_id: int | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """查询内容实验列表。"""
    service = ContentExperimentService(db)
    result = [_serialize_experiment(item) for item in service.list_experiments(account_id=account_id, limit=limit)]
    return success(result)


@router.get("/{experiment_id}")
def get_experiment(experiment_id: int, db: Session = Depends(get_db)):
    """查询内容实验详情。"""
    service = ContentExperimentService(db)
    try:
        return success(_serialize_experiment(service.get_experiment(experiment_id)))
    except ValueError as exc:
        return _service_error(exc, 404)


@router.put("/{experiment_id}")
def update_experiment(experiment_id: int, data: ContentExperimentUpdate, db: Session = Depends(get_db)):
    """更新内容实验。"""
    service = ContentExperimentService(db)
    try:
        return success(_serialize_experiment(service.update_experiment(experiment_id, data)))
    except ValueError as exc:
        return _service_error(exc, 400)
