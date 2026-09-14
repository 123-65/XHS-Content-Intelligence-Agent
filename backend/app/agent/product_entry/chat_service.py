from app.agent.product_entry.llm_router import LLMUserInputRouter
from app.agent.product_entry.pipeline import AgentEntryPreviewPipeline
from app.agent.product_entry.schemas import AgentChatRequest, AgentChatResponse
from app.agent.product_entry.task_planner import LLMTaskPlanner
from app.llm.client import LLMClient


class AgentChatPreviewService:
    """Agent Chat 预览服务，封装入口 dry-run pipeline。"""

    def __init__(self, pipeline: AgentEntryPreviewPipeline):
        """初始化预览服务。"""
        self.pipeline = pipeline

    def preview(self, request: AgentChatRequest) -> AgentChatResponse:
        """处理 Agent Chat dry-run 请求，返回统一响应。"""
        return self.pipeline.preview(request)


def build_agent_chat_preview_service() -> AgentChatPreviewService:
    """构建 Agent Chat 预览服务。"""
    llm_client = LLMClient()
    pipeline = AgentEntryPreviewPipeline(
        router=LLMUserInputRouter(llm_client),
        planner=LLMTaskPlanner(llm_client),
    )
    return AgentChatPreviewService(pipeline)
