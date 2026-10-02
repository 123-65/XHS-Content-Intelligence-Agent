from sqlalchemy.orm import Session

from app.repositories.publication_repo import PublicationRepository
from app.schemas.publication import MetricWindow, PublicMetricSnapshotResult
from app.services.xhs_collector_sev import XhsCollectorService


class PublishedMetricsService:
    """复用 Canonical XHS Collector 读取并保存公开指标快照。"""

    def __init__(self, db: Session, collector: XhsCollectorService | None = None, repository: PublicationRepository | None = None):
        """初始化公开指标服务。"""
        self.repo = repository or PublicationRepository(db)
        self.collector = collector or XhsCollectorService(db)

    def snapshot(self, published_note_ref: int, window: MetricWindow) -> PublicMetricSnapshotResult:
        """采集单篇已绑定笔记的公开指标，不扩展采集范围。"""
        note = self.repo.get_note(published_note_ref)
        if not note:
            raise ValueError("Published Note 不存在")
        measured = self.collector.collect_public_note_metrics(note.publish_url)
        metrics = measured["metrics"]
        record = self.repo.create_public_metrics(note.id, window, metrics, measured["source"], measured)
        return PublicMetricSnapshotResult(
            snapshot_ref=record.id,
            published_note_ref=note.id,
            observed_at=getattr(record, "collected_at", None),
            window=window,
            metrics=metrics,
            source=measured["source"],
        )

