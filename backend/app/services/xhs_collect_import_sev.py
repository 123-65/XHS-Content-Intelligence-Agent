import hashlib
from datetime import datetime
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.collectors.xhs.base import XhsCollectedAccount, XhsCollectedNote
from app.collectors.xhs.provider_types import ALLOWED_SOURCE_TYPES
from app.models.account import AccountProfile
from app.models.competitor_account import CompetitorAccount
from app.models.competitor_comment import CompetitorComment
from app.models.competitor_note import CompetitorNote
from app.models.xhs_note import XhsNoteSnapshot


class XhsImportError(ValueError):
    """Structured import error for invalid real-data collector payloads."""


class XhsCollectImportService:
    """Persist normalized real XHS collection results without crawling or LLM backfill."""

    def __init__(self, db: Session):
        self.db = db

    def import_notes(
        self,
        account_id: int,
        notes: list[XhsCollectedNote],
        *,
        source_type: str,
        provider_name: str,
        collect_comments: bool = True,
        max_comments: int = 20,
    ) -> list[dict[str, Any]]:
        self._ensure_account(account_id)
        self._ensure_real_source(source_type)
        results = []
        for note in notes:
            results.append(
                self.import_note(
                    account_id,
                    note,
                    source_type=source_type,
                    provider_name=provider_name,
                    collect_comments=collect_comments,
                    max_comments=max_comments,
                )
            )
        self.db.commit()
        return results

    def import_accounts(
        self,
        account_id: int,
        accounts: list[XhsCollectedAccount],
        *,
        source_type: str,
        provider_name: str,
    ) -> list[dict[str, Any]]:
        self._ensure_account(account_id)
        self._ensure_real_source(source_type)
        results = []
        for collected in accounts:
            account = self.upsert_competitor_account(account_id, collected, source_type=source_type, provider_name=provider_name)
            note_results = [
                self.import_note(
                    account_id,
                    note,
                    source_type=source_type,
                    provider_name=provider_name,
                    competitor_account=account,
                    collect_comments=False,
                    max_comments=0,
                )
                for note in collected.recent_notes
                if note.note_url or note.source_url
            ]
            results.append({"competitor_account": account, "recent_note_results": note_results})
        self.db.commit()
        return results

    def import_note(
        self,
        account_id: int,
        note: XhsCollectedNote,
        *,
        source_type: str,
        provider_name: str,
        competitor_account: CompetitorAccount | None = None,
        collect_comments: bool = True,
        max_comments: int = 20,
    ) -> dict[str, Any]:
        self._ensure_real_source(source_type)
        note_url = note.note_url or note.source_url
        if not note_url:
            raise XhsImportError("note_url is required")

        account = competitor_account or self._account_from_note(account_id, note, source_type=source_type, provider_name=provider_name)
        competitor_note = self._upsert_competitor_note(account_id, account.id, note, source_type=source_type, provider_name=provider_name)
        snapshot = self._upsert_xhs_note_snapshot(account_id, note, source_type=source_type)
        comments = self._replace_comments(
            account_id,
            competitor_note.id,
            note,
            source_type=source_type,
            provider_name=provider_name,
            collect_comments=collect_comments,
            max_comments=max_comments,
        )
        self.db.flush()
        return {
            "competitor_account": account,
            "competitor_note": competitor_note,
            "xhs_note_snapshot": snapshot,
            "comments": comments,
        }

    def upsert_competitor_account(
        self,
        account_id: int,
        collected: XhsCollectedAccount,
        *,
        source_type: str,
        provider_name: str,
    ) -> CompetitorAccount:
        self._ensure_real_source(source_type)
        stmt = select(CompetitorAccount).where(CompetitorAccount.account_id == account_id)
        if collected.profile_url:
            stmt = stmt.where(CompetitorAccount.homepage_url == collected.profile_url)
        elif collected.account_id:
            stmt = stmt.where(CompetitorAccount.platform_account_id == collected.account_id)
        else:
            stmt = stmt.where(CompetitorAccount.nickname == (collected.nickname or "Unknown XHS Account"))
        account = self.db.execute(stmt.limit(1)).scalar_one_or_none()
        if not account:
            account = CompetitorAccount(account_id=account_id, nickname=collected.nickname or "Unknown XHS Account")
            self.db.add(account)
            self.db.flush()

        account.platform = "xhs"
        account.platform_account_id = collected.account_id or account.platform_account_id
        account.nickname = collected.nickname or account.nickname
        account.homepage_url = collected.profile_url or account.homepage_url
        account.bio = collected.bio
        account.follower_count = collected.follower_count
        account.note_count = len(collected.recent_notes) if collected.recent_notes else account.note_count
        account.source_type = source_type
        account.provider_name = provider_name
        account.is_mock = False
        account.confidence = 0.8 if collected.status == "SUCCESS" else 0.5
        account.raw_snapshot = {
            **(account.raw_snapshot or {}),
            "source_type": source_type,
            "provider_name": provider_name,
            "is_mock": False,
            "profile_url": collected.profile_url,
            "avatar_url": collected.avatar_url,
            "following_count": collected.following_count,
            "liked_count": collected.liked_count,
            "recent_note_count": len(collected.recent_notes),
            "raw_payload": collected.raw_payload,
        }
        return account

    def _account_from_note(
        self,
        account_id: int,
        note: XhsCollectedNote,
        *,
        source_type: str,
        provider_name: str,
    ) -> CompetitorAccount:
        return self.upsert_competitor_account(
            account_id,
            XhsCollectedAccount(
                profile_url=note.author_profile_url,
                nickname=note.author_name or "Unknown XHS Author",
                raw_payload={"from_note_url": note.note_url or note.source_url, "note_raw_payload": note.raw_payload},
                source_type=source_type,
                source_provider=provider_name,
            ),
            source_type=source_type,
            provider_name=provider_name,
        )

    def _upsert_competitor_note(
        self,
        account_id: int,
        competitor_account_id: int,
        note: XhsCollectedNote,
        *,
        source_type: str,
        provider_name: str,
    ) -> CompetitorNote:
        note_url = note.note_url or note.source_url
        item = self.db.execute(
            select(CompetitorNote).where(CompetitorNote.account_id == account_id, CompetitorNote.note_url == note_url).limit(1)
        ).scalar_one_or_none()
        if not item:
            item = CompetitorNote(account_id=account_id, note_url=note_url)
            self.db.add(item)
            self.db.flush()
        item.competitor_account_id = competitor_account_id
        item.note_id = note.note_id
        item.author_name = note.author_name
        item.title = note.title
        item.content = note.content
        item.tags = note.tags
        item.like_count = note.like_count
        item.collect_count = note.collect_count
        item.comment_count = note.comment_count
        item.source_type = source_type
        item.provider_name = provider_name
        item.is_mock = False
        item.confidence = 0.8 if note.status == "SUCCESS" else 0.5
        item.raw_snapshot = self._note_raw_snapshot(note, source_type=source_type, provider_name=provider_name)
        return item

    def _upsert_xhs_note_snapshot(self, account_id: int, note: XhsCollectedNote, *, source_type: str) -> XhsNoteSnapshot:
        note_url = note.note_url or note.source_url
        snapshot = self.db.execute(
            select(XhsNoteSnapshot).where(XhsNoteSnapshot.account_id == account_id, XhsNoteSnapshot.note_url == note_url).limit(1)
        ).scalar_one_or_none()
        if not snapshot:
            snapshot = XhsNoteSnapshot(account_id=account_id, note_url=note_url, source_type=source_type)
            self.db.add(snapshot)
            self.db.flush()
        ocr_items = self._ocr_items(note)
        snapshot.source_type = source_type
        snapshot.note_id = note.note_id
        snapshot.author_name = note.author_name
        snapshot.author_homepage = note.author_profile_url
        snapshot.title = note.title
        snapshot.content = note.content
        snapshot.tags = note.tags
        snapshot.cover_url = note.cover_url
        snapshot.image_urls = note.image_urls
        snapshot.image_count = len(note.image_urls)
        snapshot.image_ocr_items = ocr_items
        snapshot.image_ocr_text = "\n".join(item.get("ocr_text", "") for item in ocr_items if item.get("ocr_text")) or None
        snapshot.merged_text = " ".join(
            part for part in [note.title, note.content, " ".join(note.tags or []), snapshot.image_ocr_text] if part
        )
        snapshot.like_count = note.like_count
        snapshot.collect_count = note.collect_count
        snapshot.comment_count = note.comment_count
        snapshot.publish_time = note.publish_time
        snapshot.status = note.status
        snapshot.error_message = None
        snapshot.raw_hash = self._hash_note(note)
        return snapshot

    def _replace_comments(
        self,
        account_id: int,
        competitor_note_id: int,
        note: XhsCollectedNote,
        *,
        source_type: str,
        provider_name: str,
        collect_comments: bool,
        max_comments: int,
    ) -> list[CompetitorComment]:
        self.db.execute(
            delete(CompetitorComment).where(
                CompetitorComment.account_id == account_id,
                CompetitorComment.competitor_note_id == competitor_note_id,
                CompetitorComment.source_type == source_type,
            )
        )
        if not collect_comments:
            return []
        rows = []
        for index, comment in enumerate((note.comments or note.top_comments)[:max_comments]):
            if not comment.content:
                continue
            row = CompetitorComment(
                account_id=account_id,
                competitor_note_id=competitor_note_id,
                comment_id=comment.comment_id or f"{source_type.lower()}-{competitor_note_id}-{index}",
                user_name=comment.author_name,
                content=comment.content,
                like_count=comment.like_count,
                source_type=source_type,
                provider_name=provider_name,
                is_mock=False,
                confidence=0.8,
                raw_snapshot={
                    "source_type": source_type,
                    "provider_name": provider_name,
                    "is_mock": False,
                    "note_url": note.note_url or note.source_url,
                    "created_at": comment.created_at.isoformat() if comment.created_at else None,
                    "raw_payload": comment.raw_snapshot,
                },
            )
            self.db.add(row)
            rows.append(row)
        return rows

    def _note_raw_snapshot(self, note: XhsCollectedNote, *, source_type: str, provider_name: str) -> dict[str, Any]:
        return {
            "source_type": source_type,
            "provider_name": provider_name,
            "is_mock": False,
            "note_url": note.note_url or note.source_url,
            "cover_url": note.cover_url,
            "image_urls": note.image_urls,
            "image_ocr_texts": note.image_ocr_texts,
            "card_structure": note.card_structure,
            "share_count": note.share_count,
            "raw_payload": note.raw_payload,
        }

    def _ocr_items(self, note: XhsCollectedNote) -> list[dict]:
        items = []
        for index, image_url in enumerate(note.image_urls):
            ocr_text = note.image_ocr_texts[index] if index < len(note.image_ocr_texts) else ""
            card = note.card_structure[index] if index < len(note.card_structure) else {}
            items.append(
                {
                    "image_index": index + 1,
                    "image_url": image_url,
                    "ocr_status": card.get("ocr_status") if isinstance(card, dict) else None,
                    "ocr_text": ocr_text,
                    "lines": card.get("lines") if isinstance(card, dict) else [],
                    "possible_title": card.get("possible_title") if isinstance(card, dict) else "",
                    "card_structure": card if isinstance(card, dict) else {},
                }
            )
        return items

    def _hash_note(self, note: XhsCollectedNote) -> str:
        payload = note.model_dump(mode="json")
        return hashlib.sha256(repr(payload).encode("utf-8")).hexdigest()

    def _ensure_account(self, account_id: int) -> None:
        if not self.db.get(AccountProfile, account_id):
            raise ValueError("account not found")

    def _ensure_real_source(self, source_type: str) -> None:
        if source_type == "MOCK" or source_type not in ALLOWED_SOURCE_TYPES:
            raise XhsImportError(f"unsupported real source_type: {source_type}")
