from decimal import Decimal

from sqlalchemy.orm import Session

from app.repositories.publication_repo import PublicationRepository
from app.schemas.publication import PrivateMetricSnapshotResult, PrivateMetricsInput


class PrivateMetricsService:
    """校验、归一化并保存用户明确归因的私域指标。"""

    def __init__(self, db: Session, repository: PublicationRepository | None = None):
        """初始化私域指标服务，该服务不使用 LLM。"""
        self.repo = repository or PublicationRepository(db)

    def record(self, data: PrivateMetricsInput) -> PrivateMetricSnapshotResult:
        """仅保存用户提供的字段，未提供字段在返回合同中保持 UNKNOWN。"""
        note = self.repo.get_note(data.published_note_ref)
        if not note or note.account_id != data.account_id:
            raise ValueError("Published Note 不存在或不属于当前账号")
        record = self.repo.create_private_metrics(data)
        metrics: dict[str, int | Decimal | None] = {
            "dm_count": data.dm_count,
            "wechat_add_count": data.wechat_add_count,
            "consultation_count": data.consultation_count,
            "deal_count": data.deal_count,
            "revenue": data.revenue,
        }
        return PrivateMetricSnapshotResult(
            snapshot_ref=record.id,
            published_note_ref=note.id,
            observed_at=getattr(record, "collected_at", None),
            window=data.window,
            metrics=metrics,
        )
