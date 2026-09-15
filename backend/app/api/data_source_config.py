from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.data_source_config import DataSourceConfigResponse, DataSourceConfigUpdate, DataSourceConfigUpsert
from app.services.data_source_config_sev import DataSourceConfigService

router = APIRouter(prefix="/agent/data-source-configs", tags=["agent-data-source-configs"])


def _service(db: Session) -> DataSourceConfigService:
    return DataSourceConfigService(db)


@router.post("", response_model=DataSourceConfigResponse)
def upsert_data_source_config(data: DataSourceConfigUpsert, db: Session = Depends(get_db)) -> DataSourceConfigResponse:
    try:
        return _service(db).upsert_config(data)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("", response_model=list[DataSourceConfigResponse])
def list_data_source_configs(
    account_id: int | None = Query(default=None),
    db: Session = Depends(get_db),
) -> list[DataSourceConfigResponse]:
    try:
        return _service(db).list_configs(account_id=account_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/by-account/{account_id}", response_model=DataSourceConfigResponse)
def get_data_source_config_by_account(
    account_id: int,
    platform: str = Query(default="xhs", min_length=1, max_length=32),
    db: Session = Depends(get_db),
) -> DataSourceConfigResponse:
    try:
        return _service(db).get_by_account(account_id=account_id, platform=platform)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/{config_id}", response_model=DataSourceConfigResponse)
def get_data_source_config(config_id: int, db: Session = Depends(get_db)) -> DataSourceConfigResponse:
    try:
        return _service(db).get_config(config_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.put("/{config_id}", response_model=DataSourceConfigResponse)
def update_data_source_config(
    config_id: int,
    data: DataSourceConfigUpdate,
    db: Session = Depends(get_db),
) -> DataSourceConfigResponse:
    try:
        return _service(db).update_config(config_id, data)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
