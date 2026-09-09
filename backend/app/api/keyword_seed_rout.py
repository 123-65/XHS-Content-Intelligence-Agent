from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.response import fail, success
from app.enums.keyword import KeywordCategory
from app.schemas.keyword_seed import KeywordGenerateRequest, KeywordGenerateResponse, KeywordSeedResponse
from app.services.keyword_seed_sev import KeywordSeedService

router = APIRouter(prefix="/api/crawler/keywords", tags=["关键词池"])


def _serialize_seed(seed) -> dict:
    """序列化关键词种子。"""
    return KeywordSeedResponse.model_validate(seed).model_dump(mode="json")


def _service_error(exc: ValueError, status_code: int) -> JSONResponse:
    """返回业务错误响应。"""
    return JSONResponse(status_code=status_code, content=fail(code=status_code, message=str(exc)).model_dump())


@router.post("/generate")
def generate_keywords(data: KeywordGenerateRequest, db: Session = Depends(get_db)):
    """生成账号关键词池。"""
    service = KeywordSeedService(db)
    try:
        seeds = service.generate_keywords(data)
        result = KeywordGenerateResponse(
            account_id=data.account_id,
            count=len(seeds),
            keywords=[KeywordSeedResponse.model_validate(seed) for seed in seeds],
        )
        return success(result.model_dump(mode="json"))
    except ValueError as exc:
        return _service_error(exc, 400)


@router.get("")
def list_keywords(
    account_id: int = Query(...),
    category: KeywordCategory | None = Query(default=None),
    db: Session = Depends(get_db),
):
    """查询账号关键词池。"""
    service = KeywordSeedService(db)
    try:
        seeds = service.list_keywords(account_id=account_id, category=category.value if category else None)
        return success([_serialize_seed(seed) for seed in seeds])
    except ValueError as exc:
        return _service_error(exc, 404)
