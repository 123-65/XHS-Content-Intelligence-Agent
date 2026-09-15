from sqlalchemy.orm import Session

from app.llm.errors import LLMError
from app.models.account import AccountProfile
from app.models.content_experiment import ContentExperiment
from app.models.prompt_run_log import PromptRunLog
from app.schemas.content_draft_v2 import GenerateDraftV2Request
from app.schemas.draft_context_preview import DraftContextPreviewRequest, DraftContextPreviewResponse
from app.schemas.draft_generation import (
    DraftGenerationDraft,
    DraftGenerationRequest,
    DraftGenerationResponse,
)
from app.services.content_draft_v2_sev import ContentDraftV2Service
from app.services.draft_context_preview_sev import DraftContextPreviewService


class DraftGenerationNotFound(ValueError):
    """Resource needed for draft generation was not found."""


class DraftGenerationService:
    """B8 controlled bridge from confirmed B7 context into ContentDraftV2."""

    def __init__(self, db: Session):
        self.db = db
        self.preview_service = DraftContextPreviewService(db)
        self.draft_service = ContentDraftV2Service(db)

    def generate(self, experiment_id: int, request: DraftGenerationRequest) -> DraftGenerationResponse:
        account = self.db.get(AccountProfile, request.account_id)
        if not account:
            raise DraftGenerationNotFound("account not found")
        experiment = self.db.get(ContentExperiment, experiment_id)
        if not experiment:
            raise DraftGenerationNotFound("experiment not found")
        if experiment.account_id != request.account_id:
            raise ValueError("experiment account_id does not match")

        preview = self._preview(experiment_id, request)
        if not request.confirmed:
            return self._waiting_confirmation(experiment_id, request, preview)
        if experiment.status != "READY":
            return self._blocked_for_experiment_status(experiment_id, request, preview, experiment.status)
        if not preview.ready_for_draft_generation:
            return self._blocked_for_preview(experiment_id, request, preview)

        try:
            draft = self.draft_service.generate_draft(
                GenerateDraftV2Request(
                    experiment_id=experiment_id,
                    user_requirement=self._generation_requirement(request),
                )
            )
        except LLMError as exc:
            return self._llm_error(experiment_id, request, preview, exc)
        except ValueError as exc:
            return self._failed(experiment_id, request, preview, "DRAFT_GENERATION_FAILED", str(exc))

        return DraftGenerationResponse(
            status="CREATED",
            account_id=request.account_id,
            experiment_id=experiment_id,
            draft_id=draft.id,
            ready_for_generation=True,
            context_preview_status=preview.status,
            provider=self._provider_from_draft(draft),
            draft=DraftGenerationDraft(
                title=draft.recommended_title or draft.title_candidates[0],
                content=draft.body_text or "",
                tags=draft.tag_list,
                cta=draft.cta_text,
            ),
            warnings=preview.warnings,
            missing_context=preview.missing_context,
            confirmation={
                **preview.confirmation,
                "confirmed": True,
                "draft_type": request.draft_type,
                "tone": request.tone,
                "model_profile": request.model_profile,
            },
        )

    def _preview(self, experiment_id: int, request: DraftGenerationRequest) -> DraftContextPreviewResponse:
        return self.preview_service.preview(
            experiment_id,
            DraftContextPreviewRequest(
                account_id=request.account_id,
                user_requirements=request.user_requirements,
                include_strategy_memory=True,
                include_comments=True,
            ),
        )

    def _waiting_confirmation(
        self,
        experiment_id: int,
        request: DraftGenerationRequest,
        preview: DraftContextPreviewResponse,
    ) -> DraftGenerationResponse:
        return DraftGenerationResponse(
            status="WAITING_CONFIRMATION",
            account_id=request.account_id,
            experiment_id=experiment_id,
            ready_for_generation=preview.ready_for_draft_generation,
            context_preview_status=preview.status,
            warnings=preview.warnings,
            missing_context=preview.missing_context,
            confirmation={
                **preview.confirmation,
                "requires_confirmation": True,
                "confirmed": False,
                "message": "Please confirm the draft context before generation.",
            },
        )

    def _blocked_for_experiment_status(
        self,
        experiment_id: int,
        request: DraftGenerationRequest,
        preview: DraftContextPreviewResponse,
        status: str,
    ) -> DraftGenerationResponse:
        return DraftGenerationResponse(
            status="BLOCKED",
            account_id=request.account_id,
            experiment_id=experiment_id,
            ready_for_generation=False,
            context_preview_status=preview.status,
            warnings=preview.warnings,
            missing_context=preview.missing_context,
            confirmation=preview.confirmation,
            error_code="EXPERIMENT_NOT_READY",
            error_message=f"Only READY content experiments can generate drafts, current status: {status}",
        )

    def _blocked_for_preview(
        self,
        experiment_id: int,
        request: DraftGenerationRequest,
        preview: DraftContextPreviewResponse,
    ) -> DraftGenerationResponse:
        status = "DATA_INSUFFICIENT" if preview.status == "DATA_INSUFFICIENT" else "BLOCKED"
        return DraftGenerationResponse(
            status=status,
            account_id=request.account_id,
            experiment_id=experiment_id,
            ready_for_generation=False,
            context_preview_status=preview.status,
            warnings=preview.warnings,
            missing_context=preview.missing_context,
            confirmation=preview.confirmation,
            error_code=preview.error_code or "DRAFT_CONTEXT_NOT_READY",
            error_message=preview.error_message or "Draft context preview is not ready for generation.",
        )

    def _llm_error(
        self,
        experiment_id: int,
        request: DraftGenerationRequest,
        preview: DraftContextPreviewResponse,
        exc: LLMError,
    ) -> DraftGenerationResponse:
        text = str(exc)
        if "LLM_CONFIG_MISSING" in text or "LLM_PROVIDER_UNAVAILABLE" in text:
            return DraftGenerationResponse(
                status="PROVIDER_NOT_CONFIGURED",
                account_id=request.account_id,
                experiment_id=experiment_id,
                ready_for_generation=True,
                context_preview_status=preview.status,
                warnings=preview.warnings,
                missing_context=preview.missing_context,
                confirmation=preview.confirmation,
                error_code="PROVIDER_NOT_CONFIGURED",
                error_message=text,
            )
        return self._failed(experiment_id, request, preview, "LLM_RESPONSE_INVALID", text)

    def _failed(
        self,
        experiment_id: int,
        request: DraftGenerationRequest,
        preview: DraftContextPreviewResponse,
        error_code: str,
        error_message: str,
    ) -> DraftGenerationResponse:
        return DraftGenerationResponse(
            status="FAILED",
            account_id=request.account_id,
            experiment_id=experiment_id,
            ready_for_generation=preview.ready_for_draft_generation,
            context_preview_status=preview.status,
            warnings=preview.warnings,
            missing_context=preview.missing_context,
            confirmation=preview.confirmation,
            error_code=error_code,
            error_message=error_message,
        )

    def _provider_from_draft(self, draft) -> str:
        if not draft.versions:
            return "unknown"
        prompt_run_log_id = draft.versions[0].prompt_run_log_id
        if not prompt_run_log_id:
            return "unknown"
        log = self.db.get(PromptRunLog, prompt_run_log_id)
        return log.provider if log else "unknown"

    def _generation_requirement(self, request: DraftGenerationRequest) -> str | None:
        parts = [
            request.user_requirements or "",
            f"draft_type={request.draft_type}",
            f"tone={request.tone}",
            f"model_profile={request.model_profile}",
        ]
        return "\n".join(part for part in parts if part).strip() or None
