from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.agent_conversation import (
    ConversationCreate,
    ConversationCurrentState,
    ConversationMessageResponse,
    ConversationMessagePage,
    ConversationPatchState,
    ConversationResponse,
)
from app.services.agent_conversation_sev import AgentConversationService, ConversationAccountMismatchError

router = APIRouter(prefix="/agent/conversations", tags=["agent-conversations"])


def _service(db: Session) -> AgentConversationService:
    """构造 AgentConversationService。"""
    return AgentConversationService(db)


def _raise_read_error(exc: ValueError) -> None:
    if isinstance(exc, ConversationAccountMismatchError):
        raise HTTPException(
            status_code=403,
            detail={"code": "CONVERSATION_ACCOUNT_MISMATCH", "message": str(exc)},
        ) from exc
    raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("", response_model=ConversationResponse)
def create_conversation(data: ConversationCreate, db: Session = Depends(get_db)) -> ConversationResponse:
    """创建 Agent 会话。"""
    return _service(db).create_conversation(data)


@router.get("", response_model=list[ConversationResponse])
def list_conversations(
    account_ref: int = Query(gt=0),
    limit: int = Query(default=30, ge=1, le=100),
    db: Session = Depends(get_db),
) -> list[ConversationResponse]:
    """查询 Agent 会话列表。"""
    return _service(db).list_conversations(account_id=account_ref, limit=limit)


@router.get("/{conversation_id}", response_model=ConversationResponse)
def get_conversation(conversation_id: int, account_ref: int = Query(gt=0), db: Session = Depends(get_db)) -> ConversationResponse:
    """查询 Agent 会话详情。"""
    try:
        return _service(db).get_conversation(conversation_id, account_ref=account_ref)
    except ValueError as exc:
        _raise_read_error(exc)


@router.get("/{conversation_id}/messages", response_model=ConversationMessagePage)
def list_messages(
    conversation_id: int,
    account_ref: int = Query(gt=0),
    limit: int = Query(default=30, ge=1, le=100),
    before_id: int | None = Query(default=None, gt=0),
    db: Session = Depends(get_db),
) -> ConversationMessagePage:
    """查询 Agent 会话消息列表。"""
    try:
        return _service(db).list_message_page(conversation_id, limit=limit, before_id=before_id, account_ref=account_ref)
    except ValueError as exc:
        _raise_read_error(exc)


@router.get("/{conversation_id}/state", response_model=ConversationCurrentState)
def get_state(conversation_id: int, account_ref: int = Query(gt=0), db: Session = Depends(get_db)) -> ConversationCurrentState:
    """查询 Agent 会话 Current State。"""
    try:
        return _service(db).get_state(conversation_id, account_ref=account_ref)
    except ValueError as exc:
        _raise_read_error(exc)


@router.patch("/{conversation_id}/state", response_model=ConversationCurrentState)
def patch_state(
    conversation_id: int,
    data: ConversationPatchState,
    account_ref: int = Query(gt=0),
    db: Session = Depends(get_db),
) -> ConversationCurrentState:
    """受控更新 Agent 会话 Current State。"""
    try:
        return _service(db).patch_state(conversation_id, data, account_ref=account_ref)
    except ValueError as exc:
        _raise_read_error(exc)
