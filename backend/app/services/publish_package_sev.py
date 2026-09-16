from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.account import AccountProfile
from app.models.content_draft import ContentDraft
from app.models.content_experiment import ContentExperiment
from app.models.review_report import ReviewReport
from app.repositories.publish_package_repo import PublishPackageRepository
from app.schemas.publish_package import (
    PublishCard,
    PublishChecklistItem,
    PublishPackageCreate,
    PublishPackageRequest,
    PublishPackageResponse,
)


class PublishPackageNotFound(ValueError):
    """Resource needed for B12 publish package was not found."""


class PublishPackageService:
    """Build manual publish packages without LLM calls or publishing side effects."""

    def __init__(self, db: Session):
        self.db = db
        self.repo = PublishPackageRepository(db)

    def create_package(self, draft_id: int, request: PublishPackageRequest) -> PublishPackageResponse:
        if not request.confirmed:
            return PublishPackageResponse(
                status="WAITING_CONFIRMATION",
                account_id=request.account_id,
                draft_id=draft_id,
                confirmation={
                    "requires_confirmation": True,
                    "confirmed": False,
                    "message": "Confirm to generate a local manual package. This will not publish to XHS.",
                },
            )

        draft = self._get_draft_or_raise(draft_id)
        experiment = self._get_experiment_or_raise(draft.experiment_id)
        account = self._get_account_or_raise(request.account_id)
        if experiment.account_id != request.account_id or account.id != experiment.account_id:
            raise ValueError("draft account_id does not match")

        title, body, tags, cta = self._draft_content(draft)
        if not title or not body:
            return PublishPackageResponse(
                status="DATA_INSUFFICIENT",
                account_id=request.account_id,
                draft_id=draft_id,
                error_code="DRAFT_CONTENT_EMPTY",
                error_message="Draft title and body are required to generate a publish package.",
            )

        review_report = self._select_review_report(draft_id, request.review_report_id)
        if review_report and review_report.account_id is not None and review_report.account_id != request.account_id:
            raise ValueError("review_report account_id does not match")

        warnings = self._warnings(review_report)
        status = "NEEDS_REVIEW" if warnings else "READY"
        cover_card = self._cover_card(title, body, request.style)
        image_cards = self._image_cards(cover_card, body, cta, request.card_count)
        checklist = self._checklist(title, body, tags, cta, review_report)
        steps = self._manual_steps()
        revision_plan_id = self._revision_plan_id(draft)
        source_type = "REVISED_DRAFT" if revision_plan_id or (draft.generation_context or {}).get("source_draft_id") else "ORIGINAL_DRAFT"
        stats = {
            "card_count": len(image_cards),
            "body_length": len(body),
            "tag_count": len(tags),
            "has_review_report": bool(review_report),
            "template_generation": "frontend_canvas",
            "llm_called": False,
            "auto_publish": False,
        }

        package = self.repo.create(
            PublishPackageCreate(
                account_id=request.account_id,
                draft_id=draft_id,
                review_report_id=review_report.id if review_report else None,
                revision_plan_id=revision_plan_id,
                source_type=source_type,
                status=status,
                title=title,
                body=body,
                tags=tags,
                cta=cta,
                cover_card=cover_card.model_dump(),
                image_cards=[item.model_dump() for item in image_cards],
                publish_checklist=[item.model_dump() for item in checklist],
                warnings=warnings,
                manual_publish_steps=steps,
                stats=stats,
            )
        )
        return self._response_from_record(package)

    def list_by_draft(self, draft_id: int) -> list[PublishPackageResponse]:
        if not self.db.get(ContentDraft, draft_id):
            raise PublishPackageNotFound("draft not found")
        return [self._response_from_record(item) for item in self.repo.list_by_draft(draft_id)]

    def get_package(self, package_id: int) -> PublishPackageResponse:
        package = self.repo.get_by_id(package_id)
        if not package:
            raise PublishPackageNotFound("publish package not found")
        return self._response_from_record(package)

    def _response_from_record(self, package: Any) -> PublishPackageResponse:
        return PublishPackageResponse(
            status=package.status,
            package_id=package.id,
            account_id=package.account_id,
            draft_id=package.draft_id,
            review_report_id=package.review_report_id,
            revision_plan_id=package.revision_plan_id,
            source_type=package.source_type,
            title=package.title,
            body=package.body,
            tags=package.tags or [],
            cta=package.cta,
            cover_card=PublishCard.model_validate(package.cover_card),
            image_cards=[PublishCard.model_validate(item) for item in package.image_cards or []],
            publish_checklist=[PublishChecklistItem.model_validate(item) for item in package.publish_checklist or []],
            warnings=package.warnings or [],
            manual_publish_steps=package.manual_publish_steps or [],
            stats=package.stats or {},
            created_at=package.created_at,
            updated_at=package.updated_at,
        )

    def _draft_content(self, draft: ContentDraft) -> tuple[str, str, list[str], str | None]:
        title = (draft.recommended_title or draft.title or "").strip()
        body = (draft.body_text or draft.body or "").strip()
        tags = [str(item).strip().lstrip("#") for item in (draft.tag_list or draft.tags or []) if str(item).strip()]
        cta = (draft.cta_text or draft.cta or "").strip() or None
        return title, body, tags, cta

    def _cover_card(self, title: str, body: str, style: str) -> PublishCard:
        return PublishCard(
            order=1,
            card_type="cover",
            title=self._truncate(title, 34),
            subtitle=self._truncate(self._first_sentence(body), 42),
            items=[],
            style=style,
        )

    def _image_cards(self, cover_card: PublishCard, body: str, cta: str | None, card_count: int) -> list[PublishCard]:
        cards = [cover_card]
        paragraphs = self._paragraphs(body)
        available_body_cards = max(1, card_count - 1 - (1 if cta else 0))
        for index, paragraph in enumerate(paragraphs[:available_body_cards], start=2):
            cards.append(
                PublishCard(
                    order=index,
                    card_type="list",
                    title=self._card_title(paragraph, index - 1),
                    items=self._bullet_items(paragraph),
                    style=cover_card.style,
                )
            )
        if cta and len(cards) < card_count:
            cards.append(
                PublishCard(
                    order=len(cards) + 1,
                    card_type="cta",
                    title="Final step",
                    subtitle=cta,
                    items=[],
                    style=cover_card.style,
                )
            )
        return cards[:card_count]

    def _checklist(self, title: str, body: str, tags: list[str], cta: str | None, report: ReviewReport | None) -> list[PublishChecklistItem]:
        risk_ok = not report or report.risk_level != "HIGH"
        return [
            PublishChecklistItem(item="Title has no absolute promise", passed=not self._has_risky_phrase(title), level="REQUIRED"),
            PublishChecklistItem(item="Body avoids guaranteed outcomes or forced engagement", passed=not self._has_risky_phrase(body), level="REQUIRED"),
            PublishChecklistItem(item="Manual publish gate is preserved; no auto publish is executed", passed=True, level="REQUIRED"),
            PublishChecklistItem(item="ReviewReport is not marked high risk", passed=risk_ok, level="REQUIRED"),
            PublishChecklistItem(item="Tag count is suitable for manual publishing", passed=0 < len(tags) <= 12, level="RECOMMENDED"),
            PublishChecklistItem(item="CTA is a natural interaction prompt", passed=bool(cta), level="RECOMMENDED"),
        ]

    def _warnings(self, report: ReviewReport | None) -> list[str]:
        if not report:
            return ["No ReviewReport was provided; manually review the package before publishing."]
        warnings: list[str] = []
        if report.risk_level == "HIGH" or not report.passed:
            warnings.append("ReviewReport indicates high risk or did not pass; review before manual publishing.")
        return warnings

    def _manual_steps(self) -> list[str]:
        return [
            "Download all generated card images.",
            "Copy the title and body into the XHS editor.",
            "Copy tags and perform a final manual compliance check.",
            "Open XHS yourself and upload the images and copy.",
            "After publishing, return to the system and record the note link and metrics.",
        ]

    def _revision_plan_id(self, draft: ContentDraft) -> int | None:
        context = draft.generation_context or {}
        value = context.get("revision_plan_id")
        try:
            return int(value) if value is not None else None
        except (TypeError, ValueError):
            return None

    def _select_review_report(self, draft_id: int, review_report_id: int | None) -> ReviewReport | None:
        if review_report_id is not None:
            report = self.db.get(ReviewReport, review_report_id)
            if not report:
                raise PublishPackageNotFound("review_report not found")
            if report.draft_id != draft_id:
                raise ValueError("review_report draft_id does not match")
            return report
        stmt = select(ReviewReport).where(ReviewReport.draft_id == draft_id).order_by(ReviewReport.id.desc()).limit(1)
        return self.db.execute(stmt).scalar_one_or_none()

    def _paragraphs(self, body: str) -> list[str]:
        normalized = body.replace("\r\n", "\n").replace("。", "。\n").replace(".", ".\n")
        rough = [part.strip(" \n\r\t-•") for part in normalized.splitlines()]
        return [part for part in rough if part]

    def _first_sentence(self, text: str) -> str:
        paragraphs = self._paragraphs(text)
        return paragraphs[0] if paragraphs else ""

    def _card_title(self, paragraph: str, index: int) -> str:
        compact = paragraph.split("。")[0].split(".")[0].strip()
        return self._truncate(compact or f"Step {index}", 28)

    def _bullet_items(self, paragraph: str) -> list[str]:
        normalized = paragraph.replace("；", "\n").replace(";", "\n").replace("。", "\n").replace(".", "\n")
        pieces = [item.strip(" ,，") for item in normalized.splitlines()]
        items = [self._truncate(item, 36) for item in pieces if item]
        if not items:
            items = [self._truncate(paragraph, 36)]
        return items[:5]

    def _truncate(self, text: str | None, limit: int) -> str:
        value = (text or "").strip()
        return value if len(value) <= limit else f"{value[: limit - 1]}..."

    def _has_risky_phrase(self, text: str) -> bool:
        lowered = text.lower()
        risky_phrases = [
            "guaranteed",
            "must comment",
            "guarantee sales",
            "guarantee followers",
            "稳赚",
            "保证涨粉",
            "保证成交",
            "必须评论",
            "评论区扣",
        ]
        return any(phrase in lowered for phrase in risky_phrases)

    def _get_draft_or_raise(self, draft_id: int) -> ContentDraft:
        draft = self.db.get(ContentDraft, draft_id)
        if not draft:
            raise PublishPackageNotFound("draft not found")
        return draft

    def _get_experiment_or_raise(self, experiment_id: int) -> ContentExperiment:
        experiment = self.db.get(ContentExperiment, experiment_id)
        if not experiment:
            raise PublishPackageNotFound("experiment not found")
        return experiment

    def _get_account_or_raise(self, account_id: int) -> AccountProfile:
        account = self.db.get(AccountProfile, account_id)
        if not account:
            raise PublishPackageNotFound("account not found")
        return account
