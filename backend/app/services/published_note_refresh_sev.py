from datetime import UTC, datetime, timedelta

from app.schemas.publication import MetricWindow
from app.services.published_metrics_sev import PublishedMetricsService
from app.services.xhs_collector_sev import XhsCollectorService


class PublishedNoteRefreshService:
    """协调绑定 Note 的既有采集与 canonical 公开指标快照写入。"""

    def __init__(self, db=None, collector=None, metrics_service=None):
        self.collector = collector or XhsCollectorService(db)
        self.metrics_service = metrics_service or PublishedMetricsService(db, collector=self.collector)

    def refresh(self, account_ref: int, published_note_ref: int, note_url: str, *, include_comments: bool, max_comments: int):
        """仅在 Note 采集成功后追加真实公开指标快照。"""
        collected = self.collector.collect_notes(
            account_ref,
            [note_url],
            collect_comments=include_comments,
            max_comments=max_comments,
            enable_ocr=True,
        )
        if not collected.get("success_count"):
            return collected
        observed = datetime.now(UTC)
        self.metrics_service.snapshot(
            published_note_ref,
            MetricWindow(label="REFRESH", window_start=observed, window_end=observed + timedelta(microseconds=1)),
        )
        return collected
