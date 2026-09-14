from uuid import uuid4

from fastapi import APIRouter, Depends

from app.agent.product_entry.chat_service import AgentChatPreviewService, build_agent_chat_preview_service
from app.agent.product_entry.schemas import AgentChatRequest, AgentChatResponse, AgentResponseStatus
from app.agent.product_entry.trace import mask_sensitive_text

router = APIRouter(prefix="/agent/chat", tags=["agent-chat-preview"])


class _UnavailablePreviewPipeline:
    """不可用的预览 Pipeline，用于把依赖构建失败延迟到路由内处理。"""

    def __init__(self, error: Exception):
        """保存依赖构建错误。"""
        self.error = error

    def preview(self, request: AgentChatRequest) -> AgentChatResponse:
        """抛出依赖构建错误，交给 API 统一兜底。"""
        raise self.error


def get_agent_chat_preview_service() -> AgentChatPreviewService:
    """获取 Agent Chat 预览服务，方便测试替换依赖。"""
    try:
        return build_agent_chat_preview_service()
    except Exception as exc:
        return AgentChatPreviewService(_UnavailablePreviewPipeline(exc))


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
            status=AgentResponseStatus.FAILED,
            can_execute=False,
            requires_confirmation=False,
            message="Agent Chat preview failed",
            trace_id=f"entry_api_failed_{uuid4().hex}",
            metadata={"error": {"type": type(exc).__name__, "message": mask_sensitive_text(str(exc))}},
        )
