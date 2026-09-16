from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session

from app.llm.client import LLMClient
from app.llm.errors import LLMError
from app.models.account import AccountProfile
from app.models.content_draft import ContentDraft
from app.models.content_experiment import ContentExperiment
from app.models.review_report import ReviewReport
from app.prompts.content_reviewer import CONTENT_REVIEWER_SYSTEM_PROMPT, build_content_reviewer_prompt
from app.schemas.draft_review import DraftReviewLLMResult, DraftReviewRequest, DraftReviewResponse
from app.schemas.provider_status import ProviderErrorCode


class DraftReviewNotFound(ValueError):
    """Resource needed for B9 draft review was not found."""


class DraftReviewService:
    """Controlled B9 draft review that persists ReviewReport without mutating drafts."""

    def __init__(self, db: Session):
        self.db = db

    def review(self, draft_id: int, request: DraftReviewRequest) -> DraftReviewResponse:
        if not request.confirmed:
            return DraftReviewResponse(
                status="WAITING_CONFIRMATION",
                account_id=request.account_id,
                draft_id=draft_id,
                confirmation={
                    "requires_confirmation": True,
                    "confirmed": False,
                    "message": "Please confirm before running draft review. This may call the configured LLM provider.",
                },
            )

        draft = self._get_draft_or_raise(draft_id)
        experiment = self._get_experiment_or_raise(draft.experiment_id)
        account = self._get_account_or_raise(request.account_id)
        if experiment.account_id != request.account_id or account.id != experiment.account_id:
            raise ValueError("draft account_id does not match")

        context = self._build_review_context(account, experiment, draft, request)
        try:
            llm_result = LLMClient().generate_structured(
                prompt=build_content_reviewer_prompt(context),
                schema_model=DraftReviewLLMResult,
                system_prompt=CONTENT_REVIEWER_SYSTEM_PROMPT,
                prompt_key="draft_review_b9",
                prompt_version="v1",
            )
        except LLMError as exc:
            return self._llm_error(draft_id, request, exc)

        result: DraftReviewLLMResult = llm_result.data
        report = self._create_review_report(draft, experiment, account, result, llm_result)
        return DraftReviewResponse(
            status="REVIEWED",
            account_id=request.account_id,
            draft_id=draft_id,
            review_report_id=report.id,
            can_enter_publish_preparation=result.can_enter_publish_preparation,
            risk_level=result.risk_level,
            score=result.score,
            issues=result.issues,
            suggestions=result.suggestions,
            warnings=result.warnings,
            summary=result.summary,
            block_reasons=result.block_reasons,
            must_fix_before_publish=result.must_fix_before_publish,
            optional_improvements=result.optional_improvements,
            confirmation={"requires_confirmation": True, "confirmed": True, "review_mode": request.review_mode},
        )

    def _create_review_report(
        self,
        draft: ContentDraft,
        experiment: ContentExperiment,
        account: AccountProfile,
        result: DraftReviewLLMResult,
        llm_result,
    ) -> ReviewReport:
        report = ReviewReport(
            draft_id=draft.id,
            account_id=account.id,
            experiment_id=experiment.id,
            review_type="DRAFT_REVIEW_B9",
            passed=result.can_enter_publish_preparation and result.risk_level != "HIGH",
            score=result.score,
            quality_score=result.score,
            conversion_score=max(0, result.score - 5),
            evidence_usage_score=max(0, result.score - 10),
            risk_level=result.risk_level,
            issues=[issue.model_dump() for issue in result.issues],
            suggestions=result.suggestions,
            data_facts=self._data_facts(result),
            inferences=self._inferences(result),
            action_suggestions=self._action_suggestions(result),
            summary=result.summary,
            status="SUCCESS",
            prompt_tokens=llm_result.usage.prompt_tokens,
            completion_tokens=llm_result.usage.completion_tokens,
            total_tokens=llm_result.usage.total_tokens,
            estimated_cost=Decimal(str(llm_result.estimated_cost)),
            raw_response_id=llm_result.raw_response_id,
        )
        self.db.add(report)
        self.db.commit()
        self.db.refresh(report)
        return report

    def _build_review_context(
        self,
        account: AccountProfile,
        experiment: ContentExperiment,
        draft: ContentDraft,
        request: DraftReviewRequest,
    ) -> dict[str, Any]:
        return {
            "review_controls": {
                "review_mode": request.review_mode,
                "check_ai_tone": request.check_ai_tone,
                "check_risk": request.check_risk,
                "check_evidence_consistency": request.check_evidence_consistency,
                "do_not_rewrite_draft": True,
                "do_not_publish": True,
                "do_not_comment": True,
            },
            "account": {
                "account_id": account.id,
                "account_name": account.account_name,
                "positioning": account.positioning,
                "target_audience": account.target_audience,
                "primary_goal": account.primary_goal,
                "tone_preference": account.tone_preference,
                "forbidden_topics": account.forbidden_topics,
            },
            "experiment": {
                "experiment_id": experiment.id,
                "experiment_name": experiment.experiment_name,
                "hypothesis": experiment.hypothesis,
                "target_metric": experiment.target_metric,
                "expected_result": experiment.expected_result,
                "topic_angle": experiment.topic_angle,
                "selected_topic": experiment.selected_topic,
                "target_values": experiment.target_values,
            },
            "draft": {
                "draft_id": draft.id,
                "title": draft.recommended_title or draft.title,
                "body": draft.body_text or draft.body,
                "tags": draft.tag_list or draft.tags,
                "cover_text": draft.cover_text,
                "image_scripts": draft.image_script or draft.image_scripts,
                "cta": draft.cta_text or draft.cta,
                "status": draft.status,
                "generation_context": draft.generation_context,
            },
            "review_dimensions": [
                "safety_compliance",
                "ai_tone_readability",
                "evidence_consistency",
                "publish_preparation_readiness",
            ],
        }

    def _data_facts(self, result: DraftReviewLLMResult) -> list[dict[str, Any]]:
        return [
            {
                "type": "draft_review_b9",
                "risk_level": result.risk_level,
                "score": result.score,
                "can_enter_publish_preparation": result.can_enter_publish_preparation,
                "evidence_consistency": result.evidence_consistency,
                "ai_tone_feedback": result.ai_tone_feedback,
            }
        ]

    def _inferences(self, result: DraftReviewLLMResult) -> list[dict[str, Any]]:
        return [
            {"type": "block_reason", "content": item}
            for item in result.block_reasons
        ]

    def _action_suggestions(self, result: DraftReviewLLMResult) -> list[dict[str, Any]]:
        return [
            {"type": "must_fix_before_publish", "content": item}
            for item in result.must_fix_before_publish
        ] + [
            {"type": "optional_improvement", "content": item}
            for item in result.optional_improvements
        ]

    def _llm_error(self, draft_id: int, request: DraftReviewRequest, exc: LLMError) -> DraftReviewResponse:
        text = str(exc)
        if ProviderErrorCode.LLM_CONFIG_MISSING.value in text or ProviderErrorCode.LLM_PROVIDER_UNAVAILABLE.value in text:
            return DraftReviewResponse(
                status="PROVIDER_NOT_CONFIGURED",
                account_id=request.account_id,
                draft_id=draft_id,
                error_code=ProviderErrorCode.LLM_CONFIG_MISSING.value,
                error_message=text,
            )
        return DraftReviewResponse(
            status="FAILED",
            account_id=request.account_id,
            draft_id=draft_id,
            error_code=ProviderErrorCode.LLM_OUTPUT_FAILED.value,
            error_message=text,
        )

    def _get_draft_or_raise(self, draft_id: int) -> ContentDraft:
        draft = self.db.get(ContentDraft, draft_id)
        if not draft:
            raise DraftReviewNotFound("draft not found")
        return draft

    def _get_experiment_or_raise(self, experiment_id: int) -> ContentExperiment:
        experiment = self.db.get(ContentExperiment, experiment_id)
        if not experiment:
            raise DraftReviewNotFound("experiment not found")
        return experiment

    def _get_account_or_raise(self, account_id: int) -> AccountProfile:
        account = self.db.get(AccountProfile, account_id)
        if not account:
            raise DraftReviewNotFound("account not found")
        return account
