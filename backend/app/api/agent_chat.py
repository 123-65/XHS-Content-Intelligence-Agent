from uuid import uuid4

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.agent.product_entry.chat_service import (
    AgentChatPreviewService,
    AgentChatReadonlyExecuteService,
    AgentChatWorkflowExecuteService,
    build_agent_chat_preview_service,
    build_agent_chat_readonly_execute_service,
    build_agent_chat_workflow_execute_service,
)
from app.agent.product_entry.schemas import AgentChatRequest, AgentChatResponse, AgentResponseStatus
from app.agent.product_entry.trace import mask_sensitive_text
from app.core.database import get_db

router = APIRouter(prefix="/agent/chat", tags=["agent-chat-preview"])


class _UnavailablePreviewPipeline:
    """不可用的预览 Pipeline，用于把依赖构建失败延迟到路由内处理。"""

    def __init__(self, error: Exception):
        """保存依赖构建错误。"""
        self.error = error

    def preview(self, request: AgentChatRequest) -> AgentChatResponse:
        """抛出依赖构建错误，交给 API 统一兜底。"""
        raise self.error


class _UnavailableReadonlyExecuteService:
    """不可用的只读执行服务，用于延迟处理依赖构建错误。"""

    def __init__(self, error: Exception):
        """保存依赖构建错误。"""
        self.error = error

    def execute_readonly(self, request: AgentChatRequest) -> AgentChatResponse:
        """抛出依赖构建错误，交给 API 统一兜底。"""
        raise self.error


class _UnavailableWorkflowExecuteService:
    """不可用的 workflow 执行服务，用于延迟处理依赖构建错误。"""

    def __init__(self, error: Exception):
        self.error = error

    def execute_workflow(self, request: AgentChatRequest) -> AgentChatResponse:
        raise self.error


def get_agent_chat_preview_service(db: Session = Depends(get_db)) -> AgentChatPreviewService:
    """获取 Agent Chat 预览服务，方便测试替换依赖。"""
    try:
        return build_agent_chat_preview_service(db)
    except Exception as exc:
        return AgentChatPreviewService(_UnavailablePreviewPipeline(exc))


def get_agent_chat_readonly_execute_service(db: Session = Depends(get_db)) -> AgentChatReadonlyExecuteService:
    """获取 Agent Chat 只读执行服务，方便测试替换依赖。"""
    try:
        return build_agent_chat_readonly_execute_service(db)
    except Exception as exc:
        return _UnavailableReadonlyExecuteService(exc)  # type: ignore[return-value]


def get_agent_chat_workflow_execute_service(db: Session = Depends(get_db)) -> AgentChatWorkflowExecuteService:
    """获取 Agent Chat workflow 执行服务，方便测试替换依赖。"""
    try:
        return build_agent_chat_workflow_execute_service(db)
    except Exception as exc:
        return _UnavailableWorkflowExecuteService(exc)  # type: ignore[return-value]


@router.post("/preview", response_model=AgentChatResponse)
def preview_agent_chat(
    request: AgentChatRequest,
    service: AgentChatPreviewService = Depends(get_agent_chat_preview_service),
) -> AgentChatResponse:
    """预览 Agent Chat 入口链路，只 dry-run，不执行业务。"""
    try:
        return service.preview(request)
    except Exception as exc:
        return AgentChatResponse(
            session_id=request.session_id,
            conversation_id=request.conversation_id,
            status=AgentResponseStatus.FAILED,
            can_execute=False,
            requires_confirmation=False,
            message="Agent Chat preview failed",
            trace_id=f"entry_api_failed_{uuid4().hex}",
            metadata={"error": {"type": type(exc).__name__, "message": mask_sensitive_text(str(exc))}},
        )


@router.post("/execute-readonly", response_model=AgentChatResponse)
def execute_readonly_agent_chat(
    request: AgentChatRequest,
    service: AgentChatReadonlyExecuteService = Depends(get_agent_chat_readonly_execute_service),
) -> AgentChatResponse:
    """执行 Agent Chat 只读链路，仅允许白名单查询类 Action 进入 REAL。"""
    try:
        return service.execute_readonly(request)
    except Exception as exc:
        return AgentChatResponse(
            session_id=request.session_id,
            conversation_id=request.conversation_id,
            status=AgentResponseStatus.FAILED,
            can_execute=False,
            requires_confirmation=False,
            message="Agent Chat readonly execution failed",
            trace_id=f"entry_readonly_failed_{uuid4().hex}",
            metadata={"error": {"type": type(exc).__name__, "message": mask_sensitive_text(str(exc))}},
        )


@router.post("/execute-workflow", response_model=AgentChatResponse)
def execute_workflow_agent_chat(
    request: AgentChatRequest,
    service: AgentChatWorkflowExecuteService = Depends(get_agent_chat_workflow_execute_service),
) -> AgentChatResponse:
    """执行 Agent Chat workflow 链路：真实采集、入库、竞品分析。"""
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
