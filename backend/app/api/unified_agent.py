from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.unified_agent import AgentRunResponse, AgentTurnRequest, AgentTurnResponse
from app.services.unified_agent_sev import UnifiedAgentError, UnifiedAgentService


router = APIRouter(prefix="/api/agent", tags=["unified-agent"])


def get_unified_agent_service(db: Session = Depends(get_db)) -> UnifiedAgentService:
    return UnifiedAgentService(db)


@router.post("/turns", response_model=AgentTurnResponse)
def create_agent_turn(data: AgentTurnRequest, service: UnifiedAgentService = Depends(get_unified_agent_service)):
    """Unified Agent 唯一 Turn 入口；业务状态均以 HTTP 200 返回。"""
    try:
        return service.handle_turn(data)
    except UnifiedAgentError as exc:
        status = 403 if exc.code.endswith("ACCOUNT_MISMATCH") else 404 if exc.code.endswith("NOT_FOUND") else 409 if exc.code.startswith("REQUEST_") else 400
        raise HTTPException(status_code=status, detail={"code": exc.code, "message": str(exc)}) from exc


@router.get("/runs/{run_ref}", response_model=AgentRunResponse)
def get_agent_run(run_ref: str, account_ref: int = Query(gt=0), service: UnifiedAgentService = Depends(get_unified_agent_service)):
    """按 Account boundary 返回 public-safe Runtime 结果。"""
    try:
        return service.get_run(run_ref, account_ref)
    except UnifiedAgentError as exc:
        status = 403 if exc.code.endswith("ACCOUNT_MISMATCH") else 404 if exc.code.endswith("NOT_FOUND") else 400
        raise HTTPException(status_code=status, detail={"code": exc.code, "message": str(exc)}) from exc
