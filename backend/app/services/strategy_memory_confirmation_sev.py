from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.agent_conversation import AgentConversation
from app.models.memory_evidence import MemoryEvidence
from app.models.published_note import PublishedNote
from app.models.review_report import ReviewReport
from app.models.strategy_memory import StrategyMemory
from app.repositories.agent_conversation_repo import AgentConversationRepository
from app.schemas.strategy_memory_confirmation import (
    SelectedStrategyMemoryCandidate,
    StrategyMemoryAction,
    StrategyMemoryCandidateResponse,
    StrategyMemoryConfirmationRequest,
    StrategyMemoryConfirmationResponse,
    StrategyMemoryItemResponse,
)


ALLOWED_MEMORY_TYPES = {
    "CONTENT_DIRECTION",
    "TITLE_STYLE",
    "CTA_STYLE",
    "AUDIENCE_PAIN_POINT",
    "FORMAT_PREFERENCE",
    "RISK_AVOIDANCE",
    "CONVERSION_SIGNAL",
    "DATA_GAP",
}
CONFIDENCE_SCORE = {
    "LOW": Decimal("0.3000"),
    "MEDIUM": Decimal("0.6000"),
    "HIGH": Decimal("0.8500"),
}


class StrategyMemoryConfirmationNotFound(ValueError):
    """Resource needed for B15 strategy memory confirmation was not found."""


class StrategyMemoryConfirmationService:
    """Confirm B14 strategy-memory candidates into StrategyMemory with provenance."""

    def __init__(self, db: Session):
        self.db = db

    def list_candidates(self, review_id: int) -> StrategyMemoryConfirmationResponse:
        report = self._get_review_or_raise(review_id)
        account_id = report.account_id or 0
        if report.review_type != "POST_PUBLISH_REVIEW_V0":
            return self._blocked(account_id, review_id, "INVALID_REVIEW_TYPE", "Review is not POST_PUBLISH_REVIEW_V0.")
        candidates = self._candidate_responses(report)
        if not candidates:
            return StrategyMemoryConfirmationResponse(
                status="DATA_INSUFFICIENT",
                account_id=account_id,
                review_id=review_id,
                error_code="NO_STRATEGY_MEMORY_CANDIDATES",
                error_message="No strategy memory candidates are available on this post-publish review.",
            )
        return StrategyMemoryConfirmationResponse(
            status="WAITING_CONFIRMATION",
            account_id=account_id,
            review_id=review_id,
            candidates=candidates,
            next_actions=[StrategyMemoryAction(action="CONFIRM_SELECTED_CANDIDATES", label="Confirm selected strategy memory candidates")],
        )

    def confirm(self, review_id: int, request: StrategyMemoryConfirmationRequest) -> StrategyMemoryConfirmationResponse:
        report = self._get_review_or_raise(review_id)
        if report.account_id != request.account_id:
            raise ValueError("review account_id does not match")
        if report.review_type != "POST_PUBLISH_REVIEW_V0":
            return self._blocked(request.account_id, review_id, "INVALID_REVIEW_TYPE", "Review is not POST_PUBLISH_REVIEW_V0.")

        candidates = self._candidate_responses(report)
        if not request.confirmed:
            return StrategyMemoryConfirmationResponse(
                status="WAITING_CONFIRMATION",
                account_id=request.account_id,
                review_id=review_id,
                candidates=candidates,
                warnings=["No StrategyMemory will be written until confirmed=true."],
            )
        if not candidates:
            return StrategyMemoryConfirmationResponse(
                status="DATA_INSUFFICIENT",
                account_id=request.account_id,
                review_id=review_id,
                error_code="NO_STRATEGY_MEMORY_CANDIDATES",
                error_message="No strategy memory candidates are available on this post-publish review.",
            )
        if not request.selected_candidates:
            return StrategyMemoryConfirmationResponse(
                status="DATA_INSUFFICIENT",
                account_id=request.account_id,
                review_id=review_id,
                candidates=candidates,
                error_code="NO_SELECTED_CANDIDATES",
                error_message="Select at least one candidate to save.",
            )

        candidate_by_index = {item.candidate_index: item for item in candidates}
        invalid = self._validate_selection(request.selected_candidates, candidate_by_index)
        if invalid:
            return StrategyMemoryConfirmationResponse(
                status="VALIDATION_ERROR",
                account_id=request.account_id,
                review_id=review_id,
                candidates=candidates,
                error_code=invalid["code"],
                error_message=invalid["message"],
            )

        self._ensure_conversation(request.conversation_id)
        created_ids: list[int] = []
        skipped: list[dict] = []
        for selected in request.selected_candidates:
            duplicate = self._find_duplicate(request.account_id, review_id, selected.candidate_index)
            if duplicate:
                skipped.append(
                    {
                        "candidate_index": selected.candidate_index,
                        "memory_id": duplicate.id,
                        "reason": "DUPLICATE_SOURCE_CANDIDATE",
                    }
                )
                continue
            memory = self._create_memory(report, selected)
            created_ids.append(memory.id)

        self._update_current_state(request.conversation_id, request.account_id, created_ids)
        return StrategyMemoryConfirmationResponse(
            status="SAVED",
            account_id=request.account_id,
            review_id=review_id,
            candidates=candidates,
            created_memory_ids=created_ids,
            skipped_duplicates=skipped,
            warnings=[] if created_ids else ["No new StrategyMemory was created."],
            next_actions=[
                StrategyMemoryAction(
                    action="NEXT_OPERATION_RUN_WITH_MEMORY",
                    label="Use confirmed strategy memory in the next content analysis",
                    enabled=bool(created_ids),
                )
            ],
        )

    def list_memories(self, account_id: int) -> list[StrategyMemoryItemResponse]:
        stmt = (
            select(StrategyMemory)
            .where(StrategyMemory.account_id == account_id)
            .order_by(StrategyMemory.updated_at.desc(), StrategyMemory.id.desc())
        )
        return [StrategyMemoryItemResponse.model_validate(item) for item in self.db.execute(stmt).scalars().all()]

    def _candidate_responses(self, report: ReviewReport) -> list[StrategyMemoryCandidateResponse]:
        target = (report.public_metrics_summary or {}).get("target_comparison") or {}
        if report.result_status != "HIT_TARGET":
            return []
        metric_summary = report.public_metrics_summary or {}
        conversion_summary = report.private_conversion_summary or {}
        target_metric = target.get("target_metric") or "target"
        candidates = [
            StrategyMemoryCandidateResponse(
                candidate_index=0,
                memory_type="CONTENT_DIRECTION",
                content="This topic direction has a positive manual post-publish signal and can be considered in future content planning.",
                evidence=f"{target_metric} actual={target.get('actual_value')}, target={target.get('target_value')}",
                confidence="MEDIUM" if metric_summary.get("engagement_count", 0) > 0 else "LOW",
            )
        ]
        candidates.append(
            StrategyMemoryCandidateResponse(
                candidate_index=1,
                memory_type="CONVERSION_SIGNAL",
                content="Manual lead signal is available and can be considered as a conversion memory after user confirmation.",
                evidence=f"lead_count={conversion_summary.get('lead_count', 0)}, lead_rate={conversion_summary.get('lead_rate', 0)}",
                confidence="MEDIUM" if conversion_summary.get("lead_count", 0) > 0 else "LOW",
            )
        )
        return candidates

    def _validate_selection(
        self,
        selected: list[SelectedStrategyMemoryCandidate],
        candidate_by_index: dict[int, StrategyMemoryCandidateResponse],
    ) -> dict[str, str] | None:
        for item in selected:
            if item.candidate_index not in candidate_by_index:
                return {"code": "CANDIDATE_INDEX_OUT_OF_RANGE", "message": f"candidate_index {item.candidate_index} is not available."}
            if item.memory_type not in ALLOWED_MEMORY_TYPES:
                return {"code": "INVALID_MEMORY_TYPE", "message": f"memory_type {item.memory_type} is not allowed."}
            if not item.content.strip():
                return {"code": "EMPTY_CONTENT", "message": "content must not be empty."}
            if not item.evidence.strip():
                return {"code": "EMPTY_EVIDENCE", "message": "evidence must not be empty."}
            if item.confidence not in CONFIDENCE_SCORE:
                return {"code": "INVALID_CONFIDENCE", "message": "confidence must be LOW, MEDIUM, or HIGH."}
        return None

    def _create_memory(self, report: ReviewReport, selected: SelectedStrategyMemoryCandidate) -> StrategyMemory:
        note = self.db.get(PublishedNote, report.published_note_id) if report.published_note_id else None
        package_id = self._package_id(note)
        metric_summary = report.public_metrics_summary or {}
        metadata = {
            "source": "post_publish_review_v0",
            "source_type": "POST_PUBLISH_REVIEW_V0",
            "source_review_id": report.id,
            "source_published_note_id": report.published_note_id,
            "source_metric_snapshot_id": metric_summary.get("snapshot_id"),
            "source_package_id": package_id,
            "source_candidate_index": selected.candidate_index,
            "candidate_memory_type": selected.memory_type,
            "candidate_confidence": selected.confidence,
            "evidence": selected.evidence,
            "verified": True,
            "is_mock": False,
            "result_status": report.result_status,
        }
        memory = StrategyMemory(
            account_id=report.account_id,
            memory_type=selected.memory_type,
            status="VALIDATED",
            summary=selected.content,
            pattern=selected.content,
            confidence=CONFIDENCE_SCORE[selected.confidence],
            source_review_report_id=report.id,
            support_count=1,
            risk_level=report.risk_level or "LOW",
            metadata_payload=metadata,
        )
        self.db.add(memory)
        self.db.flush()
        self.db.add(
            MemoryEvidence(
                memory_id=memory.id,
                review_report_id=report.id,
                evidence_type="POST_PUBLISH_REVIEW_V0",
                evidence_text=selected.evidence,
                evidence_payload={
                    "candidate_index": selected.candidate_index,
                    "memory_type": selected.memory_type,
                    "content": selected.content,
                    "evidence": selected.evidence,
                    "confidence": selected.confidence,
                    "source_review_id": report.id,
                },
            )
        )
        memory.evidence_count = 1
        self.db.commit()
        self.db.refresh(memory)
        return memory

    def _find_duplicate(self, account_id: int, review_id: int, candidate_index: int) -> StrategyMemory | None:
        stmt = select(StrategyMemory).where(
            StrategyMemory.account_id == account_id,
            StrategyMemory.source_review_report_id == review_id,
        )
        for memory in self.db.execute(stmt).scalars().all():
            metadata = memory.metadata_payload or {}
            if metadata.get("source_candidate_index") == candidate_index:
                return memory
        return None

    def _update_current_state(self, conversation_id: int | None, account_id: int, created_ids: list[int]) -> None:
        if not conversation_id:
            return
        conversation = self._ensure_conversation(conversation_id)
        current_state = dict(conversation.current_state or {})
        current_state.update(
            {
                "active_account_id": account_id,
                "current_target_type": "STRATEGY_MEMORY" if created_ids else current_state.get("current_target_type"),
                "current_target_id": created_ids[-1] if created_ids else current_state.get("current_target_id"),
                "last_action": "CONFIRM_STRATEGY_MEMORY" if created_ids else "CONFIRM_STRATEGY_MEMORY_SKIPPED",
            }
        )
        AgentConversationRepository(self.db).update_state(conversation, current_state, account_id=account_id)

    def _ensure_conversation(self, conversation_id: int | None) -> AgentConversation | None:
        if not conversation_id:
            return None
        conversation = self.db.get(AgentConversation, conversation_id)
        if not conversation:
            raise StrategyMemoryConfirmationNotFound("conversation not found")
        return conversation

    def _get_review_or_raise(self, review_id: int) -> ReviewReport:
        report = self.db.get(ReviewReport, review_id)
        if not report:
            raise StrategyMemoryConfirmationNotFound("post publish review not found")
        return report

    def _blocked(self, account_id: int, review_id: int, code: str, message: str) -> StrategyMemoryConfirmationResponse:
        return StrategyMemoryConfirmationResponse(
            status="BLOCKED",
            account_id=account_id,
            review_id=review_id,
            error_code=code,
            error_message=message,
        )

    def _package_id(self, note: PublishedNote | None) -> int | None:
        if not note:
            return None
        raw_snapshot: dict[str, Any] = note.raw_snapshot or {}
        try:
            return int(raw_snapshot.get("publish_package_id")) if raw_snapshot.get("publish_package_id") is not None else None
        except (TypeError, ValueError):
            return None
