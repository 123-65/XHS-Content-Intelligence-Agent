from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class AccountProfileCreate(BaseModel):
    """创建账号配置请求。"""

    account_name: str = Field(min_length=1, max_length=128)
    platform: str = Field(default="xhs", max_length=32)
    homepage_url: str | None = Field(default=None, max_length=512)
    positioning: str = Field(min_length=1)
    target_audience: str = Field(min_length=1)
    business_model: str | None = Field(default=None, max_length=128)
    main_product: str | None = Field(default=None, max_length=128)
    lead_value: Decimal = Field(default=0, ge=0)
    avg_order_value: Decimal = Field(default=0, ge=0)
    gross_profit: Decimal = Field(default=0, ge=0)
    primary_goal: str = Field(default="lead", max_length=64)
    tone_preference: str | None = None
    forbidden_topics: str | None = None


class AccountProfileUpdate(BaseModel):
    """更新账号配置请求。"""

    account_name: str | None = Field(default=None, min_length=1, max_length=128)
    homepage_url: str | None = Field(default=None, max_length=512)
    positioning: str | None = Field(default=None, min_length=1)
    target_audience: str | None = Field(default=None, min_length=1)
    business_model: str | None = Field(default=None, max_length=128)
    main_product: str | None = Field(default=None, max_length=128)
    lead_value: Decimal | None = Field(default=None, ge=0)
    avg_order_value: Decimal | None = Field(default=None, ge=0)
    gross_profit: Decimal | None = Field(default=None, ge=0)
    primary_goal: str | None = Field(default=None, max_length=64)
    tone_preference: str | None = None
    forbidden_topics: str | None = None


class AccountProfileResponse(BaseModel):
    """账号配置响应。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    account_name: str
    platform: str
    homepage_url: str | None
    positioning: str
    target_audience: str
    business_model: str | None
    main_product: str | None
    lead_value: Decimal
    avg_order_value: Decimal
    gross_profit: Decimal
    primary_goal: str
    tone_preference: str | None
    forbidden_topics: str | None
    created_at: datetime
    updated_at: datetime