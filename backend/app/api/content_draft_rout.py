from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.response import fail, success
from app.llm.errors import LLMError
from app.schemas.content_draft import ContentDraftResponse, GenerateDraftRequest
from app.services.content_draft_sev import ContentDraftService

router = APIRouter(prefix="/drafts", tags=["内容草稿"])


def _serialize_draft(draft) -> dict:
    """序列化内容草稿响应。"""
    return ContentDraftResponse.model_validate(draft).model_dump(mode="json")


def _service_error(exc: ValueError, status_code: int) -> JSONResponse:
    """返回业务错误响应。"""
    return JSONResponse(status_code=status_code, content=fail(code=status_code, message=str(exc)).model_dump())


def _llm_error(exc: LLMError) -> JSONResponse:
    """返回模型调用错误响应。"""
    return JSONResponse(status_code=500, content=fail(code=500, message=str(exc)).model_dump())


@router.post("/generate")
def generate_draft(data: GenerateDraftRequest, db: Session = Depends(get_db)):
    """生成内容草稿。"""
    service = ContentDraftService(db)
    try:
        return success(_serialize_draft(service.generate_draft(data)))
    except ValueError as exc:
        return _service_error(exc, 400)
    except LLMError as exc:
        return _llm_error(exc)


@router.get("/experiment/{experiment_id}")
def list_drafts_by_experiment(experiment_id: int, db: Session = Depends(get_db)):
    """查询某个实验下的草稿列表。"""
    service = ContentDraftService(db)
    result = [_serialize_draft(item) for item in service.list_drafts(experiment_id)]
    return success(result)


@router.get("/{draft_id}")
def get_draft(draft_id: int, db: Session = Depends(get_db)):
    """查询内容草稿详情。"""
    service = ContentDraftService(db)
    try:
        return success(_serialize_draft(service.get_draft(draft_id)))
    except ValueError as exc:
        return _service_error(exc, 404)
