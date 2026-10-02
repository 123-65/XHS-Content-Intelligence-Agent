from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.product_read import (
    DraftDetail, DraftListPage, PublicationDetail, PublicationListPage,
    ResearchDetail, ResearchListPage, ReviewListPage, StrategyDetail, StrategyListPage,
)
from app.services.product_read_sev import ProductReadError, ProductReadService


router = APIRouter(prefix="/api", tags=["product-read"])


def _service(db: Session = Depends(get_db)) -> ProductReadService:
    return ProductReadService(db)


def _read(call):
    try:
        return call()
    except ProductReadError as exc:
        status = 403 if exc.code.endswith("ACCOUNT_MISMATCH") else 404 if exc.code.endswith("NOT_FOUND") else 409
        raise HTTPException(status_code=status, detail={"code": exc.code, "message": str(exc)}) from exc


@router.get("/artifacts/research", response_model=ResearchListPage)
def list_research(account_ref: int = Query(gt=0), page_no: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100), service: ProductReadService = Depends(_service)):
    return _read(lambda: service.list_research(account_ref, page_no, page_size))


@router.get("/artifacts/strategy", response_model=StrategyListPage)
def list_strategies(account_ref: int = Query(gt=0), page_no: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100), service: ProductReadService = Depends(_service)):
    return _read(lambda: service.list_strategies(account_ref, page_no, page_size))


@router.get("/artifacts/draft", response_model=DraftListPage)
def list_drafts(account_ref: int = Query(gt=0), page_no: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100), service: ProductReadService = Depends(_service)):
    return _read(lambda: service.list_drafts(account_ref, page_no, page_size))


@router.get("/publications", response_model=PublicationListPage)
def list_publications(account_ref: int = Query(gt=0), page_no: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100), service: ProductReadService = Depends(_service)):
    return _read(lambda: service.list_publications(account_ref, page_no, page_size))


@router.get("/reviews", response_model=ReviewListPage)
def list_reviews(account_ref: int = Query(gt=0), page_no: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100), service: ProductReadService = Depends(_service)):
    return _read(lambda: service.list_reviews(account_ref, page_no, page_size))


@router.get("/artifacts/research/{ref}", response_model=ResearchDetail)
def get_research(ref: int, account_ref: int = Query(gt=0), service: ProductReadService = Depends(_service)):
    return _read(lambda: service.research_detail(ref, account_ref))


@router.get("/artifacts/strategy/{ref}", response_model=StrategyDetail)
def get_strategy(ref: int, account_ref: int = Query(gt=0), service: ProductReadService = Depends(_service)):
    return _read(lambda: service.strategy_detail(ref, account_ref))


@router.get("/artifacts/draft/{ref}", response_model=DraftDetail)
def get_draft(ref: int, account_ref: int = Query(gt=0), service: ProductReadService = Depends(_service)):
    return _read(lambda: service.draft_detail(ref, account_ref))


@router.get("/publications/{ref}", response_model=PublicationDetail)
def get_publication(ref: int, account_ref: int = Query(gt=0), service: ProductReadService = Depends(_service)):
    return _read(lambda: service.publication_detail(ref, account_ref))
