"""Deprecated compatibility service for the legacy SimpleHTTP XHS endpoint.

New Agents, Workflows, and Tools must use ``XhsCollectorService`` instead.
This module is retained only while external consumers of the old HTTP API are
being audited; it must not be used as an MCP failure fallback.
"""

import hashlib
import re
from datetime import datetime
from typing import Any
from urllib.parse import urlparse

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.collectors.xhs.base import XhsCollectedNote, XhsCollectProviderResult
from app.collectors.xhs.simple_http_provider import SimpleHttpXhsProvider
from app.models.account import AccountProfile
from app.models.competitor_account import CompetitorAccount
from app.models.competitor_comment import CompetitorComment
from app.models.competitor_note import CompetitorNote
from app.models.crawl_task import CrawlTask
from app.models.xhs_note import XhsNoteSnapshot
from app.schemas.xhs_url_collect import (
    XhsUrlCollectAction,
    XhsUrlCollectItemResult,
    XhsUrlCollectRequest,
    XhsUrlCollectResponse,
)


class XhsUrlCollectService:
    """DEPRECATED/LEGACY_COMPAT: old SimpleHTTP collection owner."""

    def __init__(self, db: Session, provider=None):
        self.db = db
        self.provider = provider or SimpleHttpXhsProvider()

    def collect(self, request: XhsUrlCollectRequest) -> XhsUrlCollectResponse:
        if not request.confirmed:
            return XhsUrlCollectResponse(
                status="WAITING_CONFIRMATION",
                account_id=request.account_id,
                total=len(request.urls),
                next_actions=[
                    XhsUrlCollectAction(
                        action="CONFIRM_URL_COLLECT",
                        label="Confirm public XHS URL collection without cookies or captcha bypass",
                    )
                ],
            )

        self._ensure_account(request.account_id)
        urls = self._normalized_urls(request.urls)
        if not urls:
            return XhsUrlCollectResponse(
                status="FAILED",
                account_id=request.account_id,
                error_code="EMPTY_URLS",
                error_message="At least one XHS note URL is required.",
            )

        run = self._create_run(request, urls)
        results: list[XhsUrlCollectItemResult] = []
        for url in urls:
            if not self._is_supported_url(url):
                results.append(
                    XhsUrlCollectItemResult(
                        url=url,
                        status="UNSUPPORTED_URL",
                        error_code="UNSUPPORTED_URL",
                        error_message="Only public xiaohongshu.com or xhslink.com note URLs are supported.",
                    )
                )
                continue
            provider_result = self.provider.collect(url, request.collect_comments, request.max_comments)
            results.append(self._handle_provider_result(request, provider_result))

        success_count = sum(1 for item in results if item.status in {"SUCCESS", "PARTIAL_SUCCESS"} and item.note_id)
        failed_count = len(results) - success_count
        status = "COMPLETED" if success_count == len(results) else "PARTIAL_SUCCESS" if success_count else "FAILED"
        self._finish_run(run, status, results, success_count, failed_count)
        return self._response_from_run(run)

    def list_runs(self, account_id: int | None = None, limit: int = 20) -> list[XhsUrlCollectResponse]:
        stmt = select(CrawlTask).where(CrawlTask.task_type == "XHS_URL_COLLECT")
        if account_id is not None:
            stmt = stmt.where(CrawlTask.account_id == account_id)
        stmt = stmt.order_by(CrawlTask.created_at.desc(), CrawlTask.id.desc()).limit(limit)
        return [self._response_from_run(run) for run in self.db.execute(stmt).scalars().all()]

    def get_run(self, run_id: int) -> XhsUrlCollectResponse:
        run = self.db.get(CrawlTask, run_id)
        if not run or run.task_type != "XHS_URL_COLLECT":
            raise ValueError("xhs url collect run not found")
        return self._response_from_run(run)

    def _handle_provider_result(self, request: XhsUrlCollectRequest, result: XhsCollectProviderResult) -> XhsUrlCollectItemResult:
        if result.status not in {"SUCCESS", "PARTIAL_SUCCESS"} or not result.parsed_result:
            return XhsUrlCollectItemResult(
                url=result.source_url,
                status=result.status,
                warnings=result.warnings,
                error_code=result.error_code or result.status,
                error_message=result.error_message,
            )

        note = result.parsed_result
        account = self._upsert_competitor_account(request.account_id, note, result)
        competitor_note = self._upsert_competitor_note(request.account_id, account.id, note, result)
        xhs_snapshot = self._upsert_xhs_note_snapshot(request.account_id, note, result)
        saved_comments = self._replace_comments(
            request.account_id,
            competitor_note.id,
            note,
            result,
            collect_comments=request.collect_comments,
            max_comments=request.max_comments,
        )
        self.db.commit()
        return XhsUrlCollectItemResult(
            url=note.source_url,
            status=result.status,
            note_id=xhs_snapshot.id,
            xhs_note_snapshot_id=xhs_snapshot.id,
            competitor_account_id=account.id,
            competitor_note_id=competitor_note.id,
            comment_count_saved=len(saved_comments),
            author_name=note.author_name,
            title=note.title,
            like_count=note.like_count,
            collect_count=note.collect_count,
            comment_count=note.comment_count,
            warnings=result.warnings,
        )

    def _upsert_competitor_account(self, account_id: int, note: XhsCollectedNote, result: XhsCollectProviderResult) -> CompetitorAccount:
        stmt = select(CompetitorAccount).where(CompetitorAccount.account_id == account_id)
        if note.author_profile_url:
            stmt = stmt.where(CompetitorAccount.homepage_url == note.author_profile_url)
        else:
            stmt = stmt.where(CompetitorAccount.nickname == (note.author_name or "Unknown XHS Author"))
        account = self.db.execute(stmt.limit(1)).scalar_one_or_none()
        if not account:
            account = CompetitorAccount(account_id=account_id, nickname=note.author_name or "Unknown XHS Author")
            self.db.add(account)
            self.db.flush()
        account.platform = "xhs"
        account.nickname = note.author_name or account.nickname
        account.homepage_url = note.author_profile_url or account.homepage_url
        account.source_type = "URL_COLLECT"
        account.provider_name = result.provider_name
        account.is_mock = False
        account.confidence = 0.8 if result.status == "SUCCESS" else 0.5
        account.raw_snapshot = self._raw_snapshot(note, result, row_type="competitor_account")
        return account

    def _upsert_competitor_note(
        self,
        account_id: int,
        competitor_account_id: int,
        note: XhsCollectedNote,
        result: XhsCollectProviderResult,
    ) -> CompetitorNote:
        stmt = select(CompetitorNote).where(CompetitorNote.account_id == account_id, CompetitorNote.note_url == note.source_url)
        item = self.db.execute(stmt.limit(1)).scalar_one_or_none()
        if not item:
            item = CompetitorNote(account_id=account_id, note_url=note.source_url)
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
        item.source_type = "URL_COLLECT"
        item.provider_name = result.provider_name
        item.is_mock = False
        item.confidence = 0.8 if result.status == "SUCCESS" else 0.5
        item.raw_snapshot = self._raw_snapshot(note, result, row_type="competitor_note")
        return item

    def _upsert_xhs_note_snapshot(self, account_id: int, note: XhsCollectedNote, result: XhsCollectProviderResult) -> XhsNoteSnapshot:
        stmt = select(XhsNoteSnapshot).where(XhsNoteSnapshot.account_id == account_id, XhsNoteSnapshot.note_url == note.source_url)
        snapshot = self.db.execute(stmt.limit(1)).scalar_one_or_none()
        if not snapshot:
            snapshot = XhsNoteSnapshot(account_id=account_id, note_url=note.source_url, source_type="URL_COLLECT")
            self.db.add(snapshot)
            self.db.flush()
        snapshot.source_type = "URL_COLLECT"
        snapshot.note_id = note.note_id
        snapshot.author_name = note.author_name
        snapshot.author_homepage = note.author_profile_url
        snapshot.title = note.title
        snapshot.content = note.content
        snapshot.tags = note.tags
        snapshot.cover_url = note.cover_url
        snapshot.image_urls = note.image_urls
        snapshot.image_count = len(note.image_urls)
        snapshot.merged_text = " ".join(part for part in [note.title, note.content, " ".join(note.tags)] if part)
        snapshot.like_count = note.like_count
        snapshot.collect_count = note.collect_count
        snapshot.comment_count = note.comment_count
        snapshot.publish_time = note.publish_time
        snapshot.status = result.status
        snapshot.error_message = result.error_message
        snapshot.raw_hash = self._hash_snapshot(note, result)
        return snapshot

    def _replace_comments(
        self,
        account_id: int,
        competitor_note_id: int,
        note: XhsCollectedNote,
        result: XhsCollectProviderResult,
        collect_comments: bool,
        max_comments: int,
    ) -> list[CompetitorComment]:
        self.db.execute(
            delete(CompetitorComment).where(
                CompetitorComment.account_id == account_id,
                CompetitorComment.competitor_note_id == competitor_note_id,
                CompetitorComment.source_type == "URL_COLLECT",
            )
        )
        if not collect_comments:
            return []
        comments = []
        for index, comment in enumerate(note.top_comments[:max_comments]):
            row = CompetitorComment(
                account_id=account_id,
                competitor_note_id=competitor_note_id,
                comment_id=comment.comment_id or f"url-collect-{competitor_note_id}-{index}",
                user_name=comment.author_name,
                content=comment.content,
                like_count=comment.like_count,
                source_type="URL_COLLECT",
                provider_name=result.provider_name,
                is_mock=False,
                confidence=0.8 if result.status == "SUCCESS" else 0.5,
                raw_snapshot={
                    "provider_name": result.provider_name,
                    "source_url": note.source_url,
                    "source_type": "URL_COLLECT",
                    "comment": comment.raw_snapshot,
                },
            )
            self.db.add(row)
            comments.append(row)
        return comments

    def _create_run(self, request: XhsUrlCollectRequest, urls: list[str]) -> CrawlTask:
        run = CrawlTask(
            account_id=request.account_id,
            task_type="XHS_URL_COLLECT",
            provider_name=getattr(self.provider, "provider_name", "unknown"),
            status="RUNNING",
            started_at=datetime.now(),
            input_payload={
                "request": {
                    "urls": urls,
                    "collect_comments": request.collect_comments,
                    "max_comments": request.max_comments,
                },
                "results": [],
            },
        )
        self.db.add(run)
        self.db.commit()
        self.db.refresh(run)
        return run

    def _finish_run(
        self,
        run: CrawlTask,
        status: str,
        results: list[XhsUrlCollectItemResult],
        success_count: int,
        failed_count: int,
    ) -> None:
        run.status = status
        run.result_count = len(results)
        run.success_count = success_count
        run.failed_count = failed_count
        run.finished_at = datetime.now()
        run.input_payload = {
            **(run.input_payload or {}),
            "results": [item.model_dump(mode="json") for item in results],
        }
        run.error_message = "; ".join(item.error_message or item.error_code or "" for item in results if item.status not in {"SUCCESS", "PARTIAL_SUCCESS"}) or None
        self.db.commit()
        self.db.refresh(run)

    def _response_from_run(self, run: CrawlTask) -> XhsUrlCollectResponse:
        payload = run.input_payload or {}
        results = [XhsUrlCollectItemResult.model_validate(item) for item in payload.get("results", [])]
        return XhsUrlCollectResponse(
            status=run.status if run.status in {"COMPLETED", "PARTIAL_SUCCESS", "FAILED"} else "FAILED",
            account_id=run.account_id,
            run_id=run.id,
            total=run.result_count or len((payload.get("request") or {}).get("urls") or []),
            success_count=run.success_count,
            failed_count=run.failed_count,
            results=results,
            next_actions=[
                XhsUrlCollectAction(
                    action="EVIDENCE_REFRESH",
                    label="Refresh evidence analysis from collected URL data",
                    enabled=run.success_count > 0,
                )
            ],
            error_code="XHS_URL_COLLECT_FAILED" if run.status == "FAILED" else None,
            error_message=run.error_message,
            created_at=run.created_at,
            finished_at=run.finished_at,
        )

    def _ensure_account(self, account_id: int) -> None:
        if not self.db.get(AccountProfile, account_id):
            raise ValueError("account not found")

    def _normalized_urls(self, urls: list[str]) -> list[str]:
        return list(dict.fromkeys(url.strip() for url in urls if url and url.strip()))

    def _is_supported_url(self, url: str) -> bool:
        parsed = urlparse(url)
        host = parsed.netloc.lower()
        if parsed.scheme not in {"http", "https"}:
            return False
        if host.endswith("xiaohongshu.com") and re.search(r"/(explore|discovery/item)/", parsed.path):
            return True
        return host.endswith("xhslink.com")

    def _raw_snapshot(self, note: XhsCollectedNote, result: XhsCollectProviderResult, row_type: str) -> dict[str, Any]:
        return {
            "row_type": row_type,
            "provider_name": result.provider_name,
            "source_type": "URL_COLLECT",
            "source_url": note.source_url,
            "status": result.status,
            "warnings": result.warnings,
            "image_urls": note.image_urls,
            "share_count": note.share_count,
            "raw_snapshot": note.raw_snapshot,
            "raw_text": result.raw_text,
            "raw_html_excerpt": (result.raw_html or "")[:5000],
        }

    def _hash_snapshot(self, note: XhsCollectedNote, result: XhsCollectProviderResult) -> str:
        content = repr({"note": note.model_dump(mode="json"), "status": result.status}).encode("utf-8")
        return hashlib.sha256(content).hexdigest()
