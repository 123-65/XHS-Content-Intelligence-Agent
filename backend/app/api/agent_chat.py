from uuid import uuid4

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.agent.product_entry.chat_service import (
    AgentChatWorkflowExecuteService,
    build_agent_chat_workflow_execute_service,
)
from app.agent.product_entry.schemas import AgentChatRequest, AgentChatResponse, AgentResponseStatus
from app.agent.product_entry.trace import mask_sensitive_text
from app.core.database import get_db

router = APIRouter(prefix="/agent/chat", tags=["agent-chat"])


class _UnavailableWorkflowExecuteService:
    """将 workflow 依赖构建失败延迟到路由内统一转换为失败响应。"""

    def __init__(self, error: Exception):
        self.error = error

    def execute_workflow(self, request: AgentChatRequest) -> AgentChatResponse:
        raise self.error


def get_agent_chat_workflow_execute_service(db: Session = Depends(get_db)) -> AgentChatWorkflowExecuteService:
    """获取当前正式 Agent Chat workflow 执行服务。"""
    try:
        return build_agent_chat_workflow_execute_service(db)
    except Exception as exc:
        return _UnavailableWorkflowExecuteService(exc)  # type: ignore[return-value]


@router.post("/execute-workflow", response_model=AgentChatResponse)
def execute_workflow_agent_chat(
    request: AgentChatRequest,
    service: AgentChatWorkflowExecuteService = Depends(get_agent_chat_workflow_execute_service),
) -> AgentChatResponse:
    """执行当前 Agent Chat workflow 入口。"""
    try:
        return service.execute_workflow(request)
    except Exception as exc:
        return AgentChatResponse(
            session_id=request.session_id,
            conversation_id=request.conversation_id,
            status=AgentResponseStatus.FAILED,
            can_execute=False,
            requires_confirmation=False,
            message="Agent Chat workflow execution failed",
            trace_id=f"entry_workflow_failed_{uuid4().hex}",
            metadata={"error": {"type": type(exc).__name__, "message": mask_sensitive_text(str(exc))}},
        )
