from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.strategy_memory_confirmation import (
    StrategyMemoryConfirmationRequest,
    StrategyMemoryConfirmationResponse,
    StrategyMemoryItemResponse,
)
from app.services.strategy_memory_confirmation_sev import (
    StrategyMemoryConfirmationNotFound,
    StrategyMemoryConfirmationService,
)

router = APIRouter(prefix="/agent", tags=["agent-strategy-memory-confirmation-v0"])


@router.get("/post-publish-reviews/{review_id}/strategy-memory-candidates", response_model=StrategyMemoryConfirmationResponse)
def get_strategy_memory_candidates(review_id: int, db: Session = Depends(get_db)) -> StrategyMemoryConfirmationResponse:
    try:
        return StrategyMemoryConfirmationService(db).list_candidates(review_id)
    except StrategyMemoryConfirmationNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/post-publish-reviews/{review_id}/strategy-memories/confirm", response_model=StrategyMemoryConfirmationResponse)
def confirm_strategy_memories(
    review_id: int,
    data: StrategyMemoryConfirmationRequest,
    db: Session = Depends(get_db),
) -> StrategyMemoryConfirmationResponse:
    try:
        return StrategyMemoryConfirmationService(db).confirm(review_id, data)
    except StrategyMemoryConfirmationNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/accounts/{account_id}/strategy-memories", response_model=list[StrategyMemoryItemResponse])
def list_account_strategy_memories(account_id: int, db: Session = Depends(get_db)) -> list[StrategyMemoryItemResponse]:
    return StrategyMemoryConfirmationService(db).list_memories(account_id)
