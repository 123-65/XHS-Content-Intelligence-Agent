from fastapi import FastAPI

from app.api.account_rout import router as account_router
from app.api.agent_chat import router as agent_chat_router
from app.api.agent_conversation import router as agent_conversation_router
from app.api.agent_run_rout import router as agent_run_router
from app.api.context_rout import router as context_router
from app.api.developer_rout import router as developer_router
from app.api.health import router as health_router
from app.api.provider_health_rout import router as provider_health_router
from app.api.product_read import router as product_read_router
from app.api.publication import router as publication_router
from app.api.unified_agent import router as unified_agent_router
from app.core.config import settings


def create_app():
    """创建仅注册当前产品入口与必要运维资源的 FastAPI 应用。"""
    app = FastAPI(title=settings.app_name, debug=settings.debug)
    app.include_router(health_router)
    app.include_router(account_router)
    app.include_router(account_router, prefix="/api")
    app.include_router(agent_run_router)
    app.include_router(provider_health_router)
    app.include_router(context_router)
    app.include_router(developer_router)
    app.include_router(agent_chat_router)
    app.include_router(agent_conversation_router)
    app.include_router(unified_agent_router)
    app.include_router(product_read_router)
    app.include_router(publication_router)
    return app


app = create_app()
