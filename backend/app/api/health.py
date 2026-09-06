from fastapi import APIRouter
from fastapi.responses import JSONResponse
from app.core.config import settings
from app.core.response import fail, success
from app.core.database import check_db_connection


router=APIRouter(prefix="/health", tags=["健康检查"])

@router.get("")
def health_check():
    """检查服务是否正常运行。"""
    return success(data={"app_name": settings.app_name, "app_env": settings.app_env,"status": "ok"})

@router.get("/db")
def database_health_check():
    """检查数据库连接是否正常。"""

    try:
        check_db_connection()
        return success({"database": "ok"})
    except Exception as exc:
        return JSONResponse(
            status_code=500,
            content=fail(message=f"数据库连接失败：{exc}", code=500).model_dump(),
        )


