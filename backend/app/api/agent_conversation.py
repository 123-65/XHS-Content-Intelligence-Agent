from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.agent_conversation import (
    ConversationCreate,
    ConversationCurrentState,
    ConversationMessageResponse,
    ConversationPatchState,
    ConversationResponse,
)
from app.services.agent_conversation_sev import AgentConversationService

router = APIRouter(prefix="/agent/conversations", tags=["agent-conversations"])


def _service(db: Session) -> AgentConversationService:
    """构造 AgentConversationService。"""
    return AgentConversationService(db)


@router.post("", response_model=ConversationResponse)
def create_conversation(data: ConversationCreate, db: Session = Depends(get_db)) -> ConversationResponse:
    """创建 Agent 会话。"""
    return _service(db).create_conversation(data)


@router.get("", response_model=list[ConversationResponse])
def list_conversations(
    account_id: int | None = Query(default=None),
    limit: int = Query(default=30, ge=1, le=100),
    db: Session = Depends(get_db),
) -> list[ConversationResponse]:
    """查询 Agent 会话列表。"""
    return _service(db).list_conversations(account_id=account_id, limit=limit)


@router.get("/{conversation_id}", response_model=ConversationResponse)
def get_conversation(conversation_id: int, db: Session = Depends(get_db)) -> ConversationResponse:
    """查询 Agent 会话详情。"""
    try:
        return _service(db).get_conversation(conversation_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/{conversation_id}/messages", response_model=list[ConversationMessageResponse])
def list_messages(
    conversation_id: int,
    limit: int = Query(default=30, ge=1, le=100),
    db: Session = Depends(get_db),
) -> list[ConversationMessageResponse]:
    """查询 Agent 会话消息列表。"""
    try:
        return _service(db).list_messages(conversation_id, limit=limit)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/{conversation_id}/state", response_model=ConversationCurrentState)
def get_state(conversation_id: int, db: Session = Depends(get_db)) -> ConversationCurrentState:
    """查询 Agent 会话 Current State。"""
    try:
        return _service(db).get_state(conversation_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.patch("/{conversation_id}/state", response_model=ConversationCurrentState)
def patch_state(
    conversation_id: int,
    data: ConversationPatchState,
    db: Session = Depends(get_db),
) -> ConversationCurrentState:
    """受控更新 Agent 会话 Current State。"""
    try:
        return _service(db).patch_state(conversation_id, data)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
