from sqlalchemy import DateTime, Integer, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class AccountProfile(Base):
    """小红书账号配置表。"""

    __tablename__ = "account_profile"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    account_name: Mapped[str] = mapped_column(String(128), nullable=False, comment="账号名称")
    platform: Mapped[str] = mapped_column(String(32), default="xhs", nullable=False, comment="平台")
    homepage_url: Mapped[str | None] = mapped_column(String(512), nullable=True, comment="账号主页地址")
    positioning: Mapped[str] = mapped_column(Text, nullable=False, comment="账号定位")
    target_audience: Mapped[str] = mapped_column(Text, nullable=False, comment="目标用户")
    business_model: Mapped[str | None] = mapped_column(String(128), nullable=True, comment="商业模式")
    main_product: Mapped[str | None] = mapped_column(String(128), nullable=True, comment="核心产品")
    lead_value: Mapped[float] = mapped_column(Numeric(10, 2), default=0, nullable=False, comment="单个线索估值")
    avg_order_value: Mapped[float] = mapped_column(Numeric(10, 2), default=0, nullable=False, comment="平均客单价")
    gross_profit: Mapped[float] = mapped_column(Numeric(10, 2), default=0, nullable=False, comment="单笔毛利")
    primary_goal: Mapped[str] = mapped_column(String(64), default="lead", nullable=False, comment="主要目标")
    tone_preference: Mapped[str | None] = mapped_column(Text, nullable=True, comment="内容风格偏好")
    forbidden_topics: Mapped[str | None] = mapped_column(Text, nullable=True, comment="禁用内容方向")
    created_at: Mapped[DateTime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    updated_at: Mapped[DateTime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)