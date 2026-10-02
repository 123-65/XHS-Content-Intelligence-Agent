from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.schemas.publication import (
    PrivateMetricSnapshotResult, PrivateMetricsWriteRequest,
    PublishPackageInput, PublishPackageResult, PublishedNoteBindingInput, PublishedNoteResult,
)
from app.services.private_metrics_sev import PrivateMetricsService
from app.services.publish_package_sev import PublishPackageService
from app.services.published_note_binding_sev import PublishedNoteBindingService

router = APIRouter(prefix="/api", tags=["manual-publication"])

def _package_service(db: Session = Depends(get_db)) -> PublishPackageService:
    """构造发布包命令服务。"""
    return PublishPackageService(db)

def _binding_service(db: Session = Depends(get_db)) -> PublishedNoteBindingService:
    """构造人工发布登记服务。"""
    return PublishedNoteBindingService(db)

def _private_metrics_service(db: Session = Depends(get_db)) -> PrivateMetricsService:
    """构造用户归因私域指标服务。"""
    return PrivateMetricsService(db)

def _command(call):
    """将稳定业务拒绝映射为 HTTP 422。"""
    try:
        return call()
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

@router.post("/publish-packages", response_model=PublishPackageResult, status_code=status.HTTP_201_CREATED)
def create_publish_package(data: PublishPackageInput, service: PublishPackageService = Depends(_package_service)):
    """从用户显式选择的 Draft Version 创建不可变人工发布包。"""
    return _command(lambda: service.create_package(data))

@router.post("/published-notes", response_model=PublishedNoteResult, status_code=status.HTTP_201_CREATED)
def register_published_note(data: PublishedNoteBindingInput, service: PublishedNoteBindingService = Depends(_binding_service)):
    """基于发布包登记用户已经完成的人工发布。"""
    return _command(lambda: service.bind(data))

@router.post("/published-notes/{published_note_ref}/private-metrics", response_model=PrivateMetricSnapshotResult, status_code=status.HTTP_201_CREATED)
def record_private_metrics(published_note_ref: int, data: PrivateMetricsWriteRequest, service: PrivateMetricsService = Depends(_private_metrics_service)):
    """记录用户明确提供的 Note-level 匿名聚合私域指标。"""
    return _command(lambda: service.record(data.to_service_input(published_note_ref)))
