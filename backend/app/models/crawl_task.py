from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class CrawlTask(Base):
    """采集任务表。"""

    __tablename__ = "crawl_task"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("account_profile.id"), nullable=False, comment="账号 ID")
    task_type: Mapped[str] = mapped_column(String(64), nullable=False, comment="任务类型")
    provider_name: Mapped[str] = mapped_column(String(64), nullable=False, comment="采集 Provider 名称")
    keyword: Mapped[str | None] = mapped_column(String(128), nullable=True, comment="采集关键词")
    status: Mapped[str] = mapped_column(String(32), default="PENDING", nullable=False, comment="任务状态")
    result_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False, comment="结果总数")
    success_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False, comment="成功数量")
    failed_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False, comment="失败数量")
    confidence: Mapped[float] = mapped_column(Float, default=0, nullable=False, comment="整体置信度")
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True, comment="错误信息")
    input_payload: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False, comment="任务输入快照")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, comment="开始时间")
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, comment="结束时间")
