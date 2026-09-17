from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.orm import Session

from app.collectors.ocr.base import OcrProvider
from app.collectors.ocr.provider import RapidOcrProvider
from app.collectors.xhs.base import XhsCollectedAccount, XhsCollectedNote, XhsCollectorProvider
from app.collectors.xhs.provider_types import SUCCESS_STATUSES
from app.collectors.xhs.xiaohongshu_mcp_provider import XiaohongshuMcpProvider
from app.services.xhs_collect_import_sev import XhsCollectImportService


@dataclass
class XhsCollectItemOutcome:
    input_value: str
    status: str
    error_code: str | None = None
    error_message: str | None = None
    warnings: list[str] = field(default_factory=list)
    ids: dict[str, Any] = field(default_factory=dict)
    data_count: dict[str, int] = field(default_factory=dict)
    title: str | None = None
    nickname: str | None = None


class XhsCollectorService:
    """Collect real XHS data through a configured external provider and persist it."""

    def __init__(
        self,
        db: Session,
        provider: XhsCollectorProvider | None = None,
        ocr_provider: OcrProvider | None = None,
    ):
        self.db = db
        self.provider = provider or XiaohongshuMcpProvider()
        self.ocr_provider = ocr_provider or RapidOcrProvider()
        self.import_service = XhsCollectImportService(db)

    @property
    def source_type(self) -> str:
        return getattr(self.provider, "source_type", "XHS_MCP")

    @property
    def provider_name(self) -> str:
        return getattr(self.provider, "provider_name", "unknown_xhs_provider")

    def collect_notes(
        self,
        account_id: int,
        note_urls: list[str],
        *,
        collect_comments: bool = True,
        max_comments: int = 20,
        enable_ocr: bool = True,
    ) -> dict[str, Any]:
        normalized_urls = self._unique(note_urls)
        if not normalized_urls:
            raise ValueError("note_urls is required")
        outcomes = []
        for url in normalized_urls:
            provider_result = self.provider.collect_note(url, collect_comments=collect_comments, max_comments=max_comments)
            if provider_result.status not in SUCCESS_STATUSES or not provider_result.parsed_note:
                outcomes.append(
                    XhsCollectItemOutcome(
                        input_value=provider_result.source_url,
                        status=provider_result.status,
                        error_code=provider_result.error_code or provider_result.status,
                        error_message=provider_result.error_message,
                        warnings=provider_result.warnings,
                    )
                )
                continue
            note = provider_result.parsed_note
            warnings = [*provider_result.warnings, *self._apply_ocr(note, enable_ocr=enable_ocr)]
            imported = self.import_service.import_note(
                account_id,
                note,
                source_type=self.source_type,
                provider_name=self.provider_name,
                collect_comments=collect_comments,
                max_comments=max_comments,
            )
            self.db.commit()
            outcomes.append(
                XhsCollectItemOutcome(
                    input_value=provider_result.source_url,
                    status=provider_result.status,
                    warnings=warnings,
                    ids={
                        "competitor_account_id": imported["competitor_account"].id,
                        "competitor_note_id": imported["competitor_note"].id,
                        "xhs_note_snapshot_id": imported["xhs_note_snapshot"].id,
                    },
                    data_count={
                        "notes_saved": 1,
                        "comments_received": len(note.comments),
                        "comments_saved": len(imported["comments"]),
                        "images": len(note.image_urls),
                    },
                    title=note.title,
                )
            )
        return self._summary("COLLECT_XHS_NOTES", outcomes)

    def collect_accounts(
        self,
        account_id: int,
        account_ids_or_urls: list[str],
        *,
        recent_note_limit: int = 10,
    ) -> dict[str, Any]:
        normalized_accounts = self._unique(account_ids_or_urls)
        if not normalized_accounts:
            raise ValueError("competitor_account_ids_or_urls is required")
        outcomes = []
        for account_input in normalized_accounts:
            provider_result = self.provider.collect_account(account_input, recent_note_limit=recent_note_limit)
            if provider_result.status not in SUCCESS_STATUSES or not provider_result.parsed_account:
                outcomes.append(
                    XhsCollectItemOutcome(
                        input_value=provider_result.source_url,
                        status=provider_result.status,
                        error_code=provider_result.error_code or provider_result.status,
                        error_message=provider_result.error_message,
                        warnings=provider_result.warnings,
                    )
                )
                continue
            collected = provider_result.parsed_account
            imported = self.import_service.import_accounts(
                account_id,
                [collected],
                source_type=self.source_type,
                provider_name=self.provider_name,
            )[0]
            account = imported["competitor_account"]
            note_results = imported["recent_note_results"]
            outcomes.append(
                    XhsCollectItemOutcome(
                        input_value=provider_result.source_url,
                        status=provider_result.status,
                        warnings=list(dict.fromkeys([*provider_result.warnings, *collected.warnings])),
                    ids={"competitor_account_id": account.id},
                    data_count={"accounts_saved": 1, "recent_notes_saved": len(note_results)},
                    nickname=account.nickname,
                )
            )
        return self._summary("COLLECT_XHS_ACCOUNTS", outcomes)

    def _apply_ocr(self, note: XhsCollectedNote, *, enable_ocr: bool) -> list[str]:
        if not enable_ocr:
            return []
        warnings = []
        ocr_texts: list[str] = []
        card_structure: list[dict[str, Any]] = []
        for index, image_url in enumerate(note.image_urls):
            result = self.ocr_provider.extract_image_text(image_url)
            if result.status != "SUCCESS":
                warnings.append(f"OCR_{result.status}")
            text = result.text or ""
            lines = result.lines or ([line.strip() for line in text.splitlines() if line.strip()] if text else [])
            ocr_texts.append(text)
            card_structure.append(
                {
                    "image_index": index + 1,
                    "image_url": image_url,
                    "ocr_status": result.status,
                    "ocr_text": text,
                    "lines": lines,
                    "possible_title": lines[0] if lines else "",
                }
            )
        note.image_ocr_texts = ocr_texts
        note.card_structure = card_structure
        return list(dict.fromkeys(warnings))

    def _summary(self, action: str, outcomes: list[XhsCollectItemOutcome]) -> dict[str, Any]:
        success_count = sum(1 for item in outcomes if item.status in SUCCESS_STATUSES)
        failed_count = len(outcomes) - success_count
        partial_count = sum(1 for item in outcomes if item.status == "PARTIAL_SUCCESS")
        warnings = list(dict.fromkeys(warning for item in outcomes for warning in item.warnings))
        errors = [
            {"input": item.input_value, "error_code": item.error_code, "error_message": item.error_message}
            for item in outcomes
            if item.error_code or item.error_message
        ]
        return {
            "action": action,
            "status": "SUCCESS" if failed_count == 0 and partial_count == 0 else "PARTIAL_SUCCESS" if success_count else "FAILED",
            "provider_name": self.provider_name,
            "provider": self.source_type,
            "source_type": self.source_type,
            "data_source": "REAL",
            "total": len(outcomes),
            "success_count": success_count,
            "failed_count": failed_count,
            "items": [item.__dict__ for item in outcomes],
            "data_count": self._data_count(outcomes),
            "evidence_ids": self._evidence_ids(outcomes),
            "warnings": warnings,
            "errors": errors,
            "error_code": errors[0]["error_code"] if errors else None,
            "error_message": errors[0]["error_message"] if errors else None,
        }

    def _data_count(self, outcomes: list[XhsCollectItemOutcome]) -> dict[str, int]:
        totals: dict[str, int] = {}
        for item in outcomes:
            for key, value in item.data_count.items():
                totals[key] = totals.get(key, 0) + value
        return totals

    def _evidence_ids(self, outcomes: list[XhsCollectItemOutcome]) -> dict[str, list[int]]:
        ids: dict[str, list[int]] = {}
        for item in outcomes:
            for key, value in item.ids.items():
                if isinstance(value, int):
                    ids.setdefault(key, []).append(value)
        return ids

    def _unique(self, values: list[str]) -> list[str]:
        return list(dict.fromkeys(value.strip() for value in values if value and value.strip()))
