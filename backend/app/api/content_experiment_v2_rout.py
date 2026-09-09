from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.response import fail, success
from app.schemas.content_experiment_v2 import GenerateExperimentsRequest, GenerateExperimentsResponse
from app.services.content_experiment_v2_sev import ContentExperimentV2Service

router = APIRouter(prefix="/api/experiments", tags=["内容实验 V2"])


def _service_error(exc: ValueError, status_code: int) -> JSONResponse:
    """返回业务错误响应。"""
    return JSONResponse(status_code=status_code, content=fail(code=status_code, message=str(exc)).model_dump())


@router.post("/generate")
def generate_experiments(data: GenerateExperimentsRequest, db: Session = Depends(get_db)):
    """从内容机会生成候选实验卡。"""
    service = ContentExperimentV2Service(db)
    try:
        experiments = [service.get_experiment_card(item.id) for item in service.generate_experiments(data)]
        result = GenerateExperimentsResponse(account_id=data.account_id, count=len(experiments), experiments=experiments)
        return success(result.model_dump(mode="json"))
    except ValueError as exc:
        return _service_error(exc, 400)


@router.get("")
def list_experiments(account_id: int | None = Query(default=None), db: Session = Depends(get_db)):
    """查询实验卡列表。"""
    service = ContentExperimentV2Service(db)
    result = [item.model_dump(mode="json") for item in service.list_experiment_cards(account_id=account_id)]
    return success(result)


@router.get("/{experiment_id}")
def get_experiment(experiment_id: int, db: Session = Depends(get_db)):
    """查询实验卡详情。"""
    service = ContentExperimentV2Service(db)
    try:
        return success(service.get_experiment_card(experiment_id).model_dump(mode="json"))
    except ValueError as exc:
        return _service_error(exc, 404)


@router.post("/{experiment_id}/approve")
def approve_experiment(experiment_id: int, db: Session = Depends(get_db)):
    """审批候选实验卡。"""
    service = ContentExperimentV2Service(db)
    try:
        return success(service.approve_experiment(experiment_id).model_dump(mode="json"))
    except ValueError as exc:
        return _service_error(exc, 400)
