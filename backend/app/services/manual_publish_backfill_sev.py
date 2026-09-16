from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.content_draft import ContentDraft
from app.models.private_conversion_snapshot import PrivateConversionSnapshot
from app.models.public_metric_snapshot import PublicMetricSnapshot
from app.models.publish_package import PublishPackage
from app.models.published_note import PublishedNote
from app.schemas.manual_publish_backfill import (
    ManualPublishBackfillRequest,
    ManualPublishBackfillResponse,
    ManualPublishMetrics,
    ManualPublishNextAction,
    PublishedNoteBackfillResponse,
)


class ManualPublishBackfillNotFound(ValueError):
    """Resource needed for manual publish backfill was not found."""


class ManualPublishBackfillService:
    """Record user-supplied publish URL and metrics without external access."""

    def __init__(self, db: Session):
        self.db = db

    def record(self, package_id: int, request: ManualPublishBackfillRequest) -> ManualPublishBackfillResponse:
        if not request.confirmed:
            return ManualPublishBackfillResponse(
                status="WAITING_CONFIRMATION",
                account_id=request.account_id,
                package_id=package_id,
                confirmation={
                    "requires_confirmation": True,
                    "confirmed": False,
                    "message": "Confirm after you have manually published on XHS. This will not access XHS.",
                },
            )

        package = self._get_package_or_raise(package_id)
        if package.account_id != request.account_id:
            raise ValueError("publish_package account_id does not match")

        note_url = request.note_url.strip()
        if not note_url:
            raise ValueError("note_url is required")
        if not self._is_xhs_url(note_url):
            raise ValueError("note_url must be a XHS link")

        draft = self._get_draft_or_raise(package.draft_id)
        published_note = self._find_existing_note(package_id)
        if not published_note:
            published_note = self._create_published_note(package, draft, request, note_url)

        metric_snapshot = self._create_public_metric_snapshot(published_note.id, package_id, request)
        private_snapshot = self._create_private_conversion_snapshot(published_note.id, package.account_id, package_id, request)
        self._mark_package_manually_published(package, published_note.id, metric_snapshot.id, private_snapshot.id)

        return ManualPublishBackfillResponse(
            status="RECORDED",
            account_id=request.account_id,
            package_id=package_id,
            published_note_id=published_note.id,
            metric_snapshot_id=metric_snapshot.id,
            private_conversion_snapshot_id=private_snapshot.id,
            note_url=published_note.publish_url,
            published_at=published_note.published_at,
            metrics=self._metrics(request),
            warnings=[],
            next_actions=[
                ManualPublishNextAction(
                    action="POST_PUBLISH_REVIEW",
                    label="Enter post-publish review",
                    enabled=True,
                )
            ],
        )

    def list_published_notes(self, account_id: int | None, limit: int = 20) -> list[PublishedNoteBackfillResponse]:
        stmt = select(PublishedNote).order_by(PublishedNote.created_at.desc(), PublishedNote.id.desc()).limit(limit)
        if account_id is not None:
            stmt = stmt.where(PublishedNote.account_id == account_id)
        notes = self.db.execute(stmt).scalars().all()
        return [self._note_response(note) for note in notes]

    def get_published_note(self, published_note_id: int) -> PublishedNoteBackfillResponse:
        note = self.db.get(PublishedNote, published_note_id)
        if not note:
            raise ManualPublishBackfillNotFound("published note not found")
        return self._note_response(note)

    def _create_published_note(
        self,
        package: PublishPackage,
        draft: ContentDraft,
        request: ManualPublishBackfillRequest,
        note_url: str,
    ) -> PublishedNote:
        title = (request.title or package.title or draft.recommended_title or draft.title or "").strip()
        note = PublishedNote(
            account_id=package.account_id,
            experiment_id=draft.experiment_id,
            draft_id=package.draft_id,
            publish_url=note_url,
            platform=request.platform,
            status="PUBLISHED",
            source_type="MANUAL_BACKFILL",
            published_at=request.published_at or datetime.now(UTC).replace(tzinfo=None),
            raw_snapshot={
                "publish_package_id": package.id,
                "title": title,
                "remark": request.remark,
                "source": "manual_publish_backfill",
                "metric_source": "MANUAL",
            },
        )
        self.db.add(note)
        self.db.commit()
        self.db.refresh(note)
        return note

    def _create_public_metric_snapshot(
        self,
        published_note_id: int,
        package_id: int,
        request: ManualPublishBackfillRequest,
    ) -> PublicMetricSnapshot:
        snapshot = PublicMetricSnapshot(
            published_note_id=published_note_id,
            snapshot_window=request.snapshot_window,
            view_count=0,
            like_count=request.like_count,
            collect_count=request.collect_count,
            comment_count=request.comment_count,
            share_count=request.share_count,
            follow_count=request.follower_gain,
            profile_visit_count=0,
            source_type="MANUAL",
            confidence=Decimal("1"),
            raw_snapshot={
                "publish_package_id": package_id,
                "note_url": request.note_url.strip(),
                "remark": request.remark,
                "metric_source": "MANUAL",
            },
        )
        self.db.add(snapshot)
        self.db.commit()
        self.db.refresh(snapshot)
        return snapshot

    def _create_private_conversion_snapshot(
        self,
        published_note_id: int,
        account_id: int,
        package_id: int,
        request: ManualPublishBackfillRequest,
    ) -> PrivateConversionSnapshot:
        snapshot = PrivateConversionSnapshot(
            account_id=account_id,
            published_note_id=published_note_id,
            snapshot_window=request.snapshot_window,
            dm_count=0,
            lead_count=request.lead_count,
            source_type="MANUAL",
            confidence=Decimal("1"),
            raw_snapshot={
                "publish_package_id": package_id,
                "remark": request.remark,
                "metric_source": "MANUAL",
            },
        )
        self.db.add(snapshot)
        self.db.commit()
        self.db.refresh(snapshot)
        return snapshot

    def _mark_package_manually_published(
        self,
        package: PublishPackage,
        published_note_id: int,
        metric_snapshot_id: int,
        private_snapshot_id: int,
    ) -> None:
        stats = dict(package.stats or {})
        stats["manual_publish"] = {
            "status": "RECORDED",
            "published_note_id": published_note_id,
            "latest_metric_snapshot_id": metric_snapshot_id,
            "latest_private_conversion_snapshot_id": private_snapshot_id,
            "recorded_at": datetime.now(UTC).replace(tzinfo=None).isoformat(),
        }
        package.stats = stats
        package.status = "MANUALLY_PUBLISHED"
        self.db.commit()

    def _find_existing_note(self, package_id: int) -> PublishedNote | None:
        stmt = (
            select(PublishedNote)
            .where(PublishedNote.source_type == "MANUAL_BACKFILL")
            .order_by(PublishedNote.id.desc())
        )
        for note in self.db.execute(stmt).scalars().all():
            if (note.raw_snapshot or {}).get("publish_package_id") == package_id:
                return note
        return None

    def _note_response(self, note: PublishedNote) -> PublishedNoteBackfillResponse:
        raw_snapshot = note.raw_snapshot or {}
        return PublishedNoteBackfillResponse(
            id=note.id,
            account_id=note.account_id,
            experiment_id=note.experiment_id,
            draft_id=note.draft_id,
            package_id=self._int_or_none(raw_snapshot.get("publish_package_id")),
            publish_url=note.publish_url,
            platform=note.platform,
            status=note.status,
            source_type=note.source_type,
            published_at=note.published_at,
            raw_snapshot=raw_snapshot,
            created_at=note.created_at,
            updated_at=note.updated_at,
        )

    def _metrics(self, request: ManualPublishBackfillRequest) -> ManualPublishMetrics:
        return ManualPublishMetrics(
            like_count=request.like_count,
            collect_count=request.collect_count,
            comment_count=request.comment_count,
            share_count=request.share_count,
            follower_gain=request.follower_gain,
            lead_count=request.lead_count,
            source_type="MANUAL",
        )

    def _is_xhs_url(self, note_url: str) -> bool:
        lowered = note_url.lower()
        return lowered.startswith(("http://", "https://")) and (
            "xiaohongshu.com" in lowered or "xhslink.com" in lowered
        )

    def _int_or_none(self, value: Any) -> int | None:
        try:
            return int(value) if value is not None else None
        except (TypeError, ValueError):
            return None

    def _get_package_or_raise(self, package_id: int) -> PublishPackage:
        package = self.db.get(PublishPackage, package_id)
        if not package:
            raise ManualPublishBackfillNotFound("publish package not found")
        return package

    def _get_draft_or_raise(self, draft_id: int) -> ContentDraft:
        draft = self.db.get(ContentDraft, draft_id)
        if not draft:
            raise ManualPublishBackfillNotFound("draft not found")
        return draft
