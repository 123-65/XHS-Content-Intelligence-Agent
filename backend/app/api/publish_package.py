from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.publish_package import PublishPackageRequest, PublishPackageResponse
from app.services.publish_package_sev import PublishPackageNotFound, PublishPackageService

router = APIRouter(prefix="/agent", tags=["agent-publish-package"])


@router.post("/drafts/{draft_id}/publish-packages", response_model=PublishPackageResponse)
def create_publish_package(
    draft_id: int,
    data: PublishPackageRequest,
    db: Session = Depends(get_db),
) -> PublishPackageResponse:
    try:
        return PublishPackageService(db).create_package(draft_id, data)
    except PublishPackageNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/drafts/{draft_id}/publish-packages", response_model=list[PublishPackageResponse])
def list_publish_packages(
    draft_id: int,
    db: Session = Depends(get_db),
) -> list[PublishPackageResponse]:
    try:
        return PublishPackageService(db).list_by_draft(draft_id)
    except PublishPackageNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/publish-packages/{package_id}", response_model=PublishPackageResponse)
def get_publish_package(
    package_id: int,
    db: Session = Depends(get_db),
) -> PublishPackageResponse:
    try:
        return PublishPackageService(db).get_package(package_id)
    except PublishPackageNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
