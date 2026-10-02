"""DEPRECATED/LEGACY_COMPAT crawler providers.

The canonical production XHS provider lives under ``app.collectors.xhs``.
These providers remain only for registered legacy API compatibility.
"""

from app.crawler.providers.base import BaseCrawlerProvider
from app.crawler.providers.manual_snapshot_provider import ManualSnapshotProvider

__all__ = ["BaseCrawlerProvider", "ManualSnapshotProvider"]
