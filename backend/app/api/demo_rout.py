from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.response import success
from app.services.demo_sev import DemoService

router = APIRouter(prefix="/api/demo", tags=["demo"])


@router.get("/latest-run")
def latest_run(db: Session = Depends(get_db)):
    """查询最近一次流程的可视化验收摘要。"""
    return success(DemoService(db).latest_run())


@router.get("/latest-run/steps")
def latest_run_steps(db: Session = Depends(get_db)):
    """查询最近一次流程的步骤级可视化验收数据。"""
    return success(DemoService(db).latest_steps())
