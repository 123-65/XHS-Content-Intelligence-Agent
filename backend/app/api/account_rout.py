from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.response import fail, success
from app.schemas.account import AccountProfileCreate, AccountProfileResponse, AccountProfileUpdate
from app.services.account_sev import AccountProfileService

router = APIRouter(prefix="/accounts", tags=["账号配置"])


@router.post("")
def create_account(data: AccountProfileCreate, db: Session = Depends(get_db)):
    """创建账号配置。"""
    service = AccountProfileService(db)
    account = service.create_account(data)
    result = AccountProfileResponse.model_validate(account).model_dump(mode="json")
    return success(result)


@router.get("")
def list_accounts(db: Session = Depends(get_db)):
    """查询账号配置列表。"""
    service = AccountProfileService(db)
    accounts = service.list_accounts()
    result = [AccountProfileResponse.model_validate(item).model_dump(mode="json") for item in accounts]
    return success(result)


@router.get("/{account_id}")
def get_account(account_id: int, db: Session = Depends(get_db)):
    """查询账号配置详情。"""
    service = AccountProfileService(db)
    try:
        account = service.get_account(account_id)
        result = AccountProfileResponse.model_validate(account).model_dump(mode="json")
        return success(result)
    except ValueError as exc:
        return JSONResponse(status_code=404, content=fail(str(exc), code=404).model_dump())


@router.put("/{account_id}")
def update_account(account_id: int, data: AccountProfileUpdate, db: Session = Depends(get_db)):
    """更新账号配置。"""
    service = AccountProfileService(db)
    try:
        account = service.update_account(account_id, data)
        result = AccountProfileResponse.model_validate(account).model_dump(mode="json")
        return success(result)
    except ValueError as exc:
        return JSONResponse(status_code=404, content=fail(str(exc), code=404).model_dump())