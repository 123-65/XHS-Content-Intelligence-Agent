from app.core.config import settings
from fastapi import FastAPI

from app.api.health import router as health_router
from app.api.account_rout import router as account_router
from app.api.xhs_note_rout import router as xhs_note_router

def create_app():
    """创建 FastAPI 应用实例。"""
    app=FastAPI(title=settings.app_name, debug=settings.debug)
    app.include_router(router=health_router)
    app.include_router(account_router)
    app.include_router(xhs_note_router)
    return app

app=create_app()