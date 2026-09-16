from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.llm.client import LLMClient
from app.llm.errors import LLMError
from app.models.account import AccountProfile
from app.models.agent_conversation import AgentConversation
from app.models.content_draft import ContentDraft
from app.models.content_experiment import ContentExperiment
from app.models.draft_revision_plan import DraftRevisionPlan
from app.models.review_report import ReviewReport
from app.repositories.agent_conversation_repo import AgentConversationRepository
from app.repositories.content_draft_v2_repo import ContentDraftV2Repository
from app.schemas.content_draft_v2 import ContentDraftV2Create, ContentDraftVersionCreate
from app.schemas.draft_revision_apply import (
    DraftRevisionApplyDraft,
    DraftRevisionApplyLLMResult,
    DraftRevisionApplyRequest,
    DraftRevisionApplyResponse,
)
from app.schemas.provider_status import ProviderErrorCode


REVISION_APPLY_SYSTEM_PROMPT = """You are a controlled XHS draft revision editor.
Return only JSON matching the schema. Apply the given revision plan to create a revised draft.
Do not publish. Do not comment. Do not write memory. Do not invent unsupported facts. Do not copy competitor comments or notes.
Keep preserve items, obey must_not_change items, and make CTA natural."""

RISK_PHRASES = {
    "保 offer": "unsupported_outcome_guarantee",
    "保证涨粉": "unsupported_growth_guarantee",
    "保证成交": "unsupported_conversion_guarantee",
    "稳赚": "exaggerated_income_claim",
    "月入": "exaggerated_income_claim",
    "必须评论": "hard_comment_inducement",
    "评论区扣": "hard_comment_inducement",
}


class DraftRevisionApplyNotFound(ValueError):
    """Resource needed for B11 revision apply was not found."""


class DraftRevisionApplyService:
    """Controlled B11 apply service that creates a new draft and never overwrites the source."""

    def __init__(self, db: Session):
        self.db = db
        self.draft_repo = ContentDraftV2Repository(db)

    def apply(self, plan_id: int, request: DraftRevisionApplyRequest) -> DraftRevisionApplyResponse:
        if not request.confirmed:
            return DraftRevisionApplyResponse(
                status="WAITING_CONFIRMATION",
                account_id=request.account_id,
                revision_plan_id=plan_id,
                confirmation={
                    "requires_confirmation": True,
                    "confirmed": False,
                    "message": "Please confirm before applying the revision plan. This will call the configured LLM provider and create a new draft.",
                },
            )

        plan = self._get_plan_or_raise(plan_id)
        if plan.account_id != request.account_id:
            raise ValueError("revision_plan account_id does not match")
        if plan.status != "READY":
            return self._blocked(plan, "REVISION_PLAN_NOT_READY", f"Only READY revision plans can be applied, current status: {plan.status}")
        if request.source_draft_id is not None and request.source_draft_id != plan.draft_id:
            return self._blocked(plan, "SOURCE_DRAFT_MISMATCH", "source_draft_id does not match revision_plan.draft_id")

        source_draft = self._get_source_draft_or_raise(plan.draft_id)
        experiment = self._get_experiment_or_raise(source_draft.experiment_id)
        account = self._get_account_or_raise(request.account_id)
        if experiment.account_id != request.account_id or account.id != experiment.account_id:
            raise ValueError("source draft account_id does not match")

        stale_response = self._stale_response_if_needed(plan, source_draft)
        if stale_response:
            return stale_response

        review_report = self._get_review_report(plan.review_report_id)
        context = self._build_context(account, experiment, source_draft, plan, review_report, request)
        try:
            llm_result = LLMClient().generate_structured(
                prompt=self._build_prompt(context),
                schema_model=DraftRevisionApplyLLMResult,
                system_prompt=REVISION_APPLY_SYSTEM_PROMPT,
                prompt_key="draft_revision_apply_b11",
                prompt_version="v1",
            )
            result = self._validate_llm_result(llm_result.data)
            self._ensure_risk_safe(result)
        except LLMError as exc:
            return self._llm_error(plan, exc)
        except (ValidationError, ValueError) as exc:
            error_code = ProviderErrorCode.LLM_SCHEMA_INVALID.value
            if isinstance(exc, ValueError) and str(exc).startswith("RISK_BLOCKED"):
                error_code = ProviderErrorCode.RISK_BLOCKED.value
            return self._failed(plan, error_code, str(exc))

        revised_draft = self._create_revised_draft(source_draft, plan, review_report, request, result, llm_result)
        self._create_initial_version(revised_draft, result)
        if plan.conversation_id:
            self._update_current_state(plan.conversation_id, request.account_id, revised_draft.id)

        return DraftRevisionApplyResponse(
            status="CREATED",
            account_id=request.account_id,
            revision_plan_id=plan.id,
            source_draft_id=source_draft.id,
            revised_draft_id=revised_draft.id,
            review_report_id=plan.review_report_id,
            summary=result.change_summary,
            applied_operations=result.applied_operations,
            draft=DraftRevisionApplyDraft(
                title=result.title,
                content=result.content,
                tags=result.tags,
                cta=result.cta,
            ),
            warnings=[
                "Created a new draft record; the source draft was not overwritten.",
                "No publish/comment/memory workflow was triggered.",
            ],
        )

    def _validate_llm_result(self, data: Any) -> DraftRevisionApplyLLMResult:
        if isinstance(data, DraftRevisionApplyLLMResult):
            return DraftRevisionApplyLLMResult.model_validate(data.model_dump())
        return DraftRevisionApplyLLMResult.model_validate(data)

    def _create_revised_draft(
        self,
        source_draft: ContentDraft,
        plan: DraftRevisionPlan,
        review_report: ReviewReport | None,
        request: DraftRevisionApplyRequest,
        result: DraftRevisionApplyLLMResult,
        llm_result,
    ) -> ContentDraft:
        generation_context = {
            "source": "draft_revision_apply_b11",
            "source_draft_id": source_draft.id,
            "revised_from_draft_id": source_draft.id,
            "revision_plan_id": plan.id,
            "review_report_id": plan.review_report_id,
            "account_id": plan.account_id,
            "save_as": request.save_as,
            "user_extra_requirements": request.user_extra_requirements,
            "plan_snapshot": plan.plan,
            "review_report_summary": review_report.summary if review_report else None,
            "source_draft_updated_at": source_draft.updated_at.isoformat() if source_draft.updated_at else None,
        }
        return self.draft_repo.create_draft(
            ContentDraftV2Create(
                experiment_id=source_draft.experiment_id,
                title=result.title,
                body=result.content,
                tags=result.tags,
                cover_text=source_draft.cover_text,
                image_scripts=source_draft.image_scripts,
                cta=result.cta,
                title_candidates=[result.title, *(source_draft.title_candidates or [])][:5],
                recommended_title=result.title,
                cover_subtitle=source_draft.cover_subtitle,
                body_text=result.content,
                image_script=source_draft.image_script,
                tag_list=result.tags,
                keyword_list=source_draft.keyword_list,
                cta_text=result.cta,
                version=source_draft.version + 1,
                status="REVISED",
                generation_context=generation_context,
                prompt_tokens=llm_result.usage.prompt_tokens,
                completion_tokens=llm_result.usage.completion_tokens,
                total_tokens=llm_result.usage.total_tokens,
                estimated_cost=Decimal(str(llm_result.estimated_cost)),
                raw_response_id=llm_result.raw_response_id,
            )
        )

    def _create_initial_version(self, draft: ContentDraft, result: DraftRevisionApplyLLMResult) -> None:
        self.draft_repo.create_version(
            ContentDraftVersionCreate(
                draft_id=draft.id,
                version=draft.version,
                regenerate_scope="revision_apply",
                draft_snapshot={
                    "title_candidates": draft.title_candidates,
                    "recommended_title": draft.recommended_title,
                    "cover_text": draft.cover_text,
                    "cover_subtitle": draft.cover_subtitle,
                    "body_text": draft.body_text,
                    "image_script": draft.image_script,
                    "tag_list": draft.tag_list,
                    "keyword_list": draft.keyword_list,
                    "cta_text": draft.cta_text,
                    "version": draft.version,
                    "status": draft.status,
                    "change_summary": result.change_summary,
                    "applied_operations": [item.model_dump() for item in result.applied_operations],
                    "source": draft.generation_context,
                },
            )
        )

    def _build_context(
        self,
        account: AccountProfile,
        experiment: ContentExperiment,
        source_draft: ContentDraft,
        plan: DraftRevisionPlan,
        review_report: ReviewReport | None,
        request: DraftRevisionApplyRequest,
    ) -> dict[str, Any]:
        return {
            "controls": {
                "create_new_draft": True,
                "do_not_overwrite_source_draft": True,
                "do_not_publish": True,
                "do_not_comment": True,
                "do_not_write_strategy_memory": True,
            },
            "account": {
                "account_id": account.id,
                "account_name": account.account_name,
                "positioning": account.positioning,
                "target_audience": account.target_audience,
                "tone_preference": account.tone_preference,
                "forbidden_topics": account.forbidden_topics,
            },
            "experiment": {
                "experiment_id": experiment.id,
                "experiment_name": experiment.experiment_name,
                "hypothesis": experiment.hypothesis,
                "target_metric": experiment.target_metric,
                "selected_topic": experiment.selected_topic,
                "topic_angle": experiment.topic_angle,
            },
            "source_draft": self._draft_snapshot(source_draft),
            "revision_plan": {
                "revision_plan_id": plan.id,
                "summary": plan.summary,
                "plan": plan.plan,
                "feedback_text": plan.feedback_text,
                "feedback_scope": plan.feedback_scope,
                "risk_flags": plan.risk_flags,
            },
            "review_report": self._review_snapshot(review_report),
            "user_extra_requirements": request.user_extra_requirements or "",
        }

    def _build_prompt(self, context: dict[str, Any]) -> str:
        return (
            "Apply the structured revision plan to the source draft and return a revised XHS draft JSON. "
            "Follow operations, preserve items, must_not_change items, and risk_fixes. "
            "Do not add unsupported claims or execution actions.\n\n"
            f"CONTEXT:\n{context}"
        )

    def _draft_snapshot(self, draft: ContentDraft) -> dict[str, Any]:
        return {
            "draft_id": draft.id,
            "title": draft.recommended_title or draft.title,
            "content": draft.body_text or draft.body,
            "tags": draft.tag_list or draft.tags,
            "cta": draft.cta_text or draft.cta,
            "version": draft.version,
            "updated_at": draft.updated_at.isoformat() if draft.updated_at else None,
        }

    def _review_snapshot(self, report: ReviewReport | None) -> dict[str, Any] | None:
        if not report:
            return None
        return {
            "review_report_id": report.id,
            "risk_level": report.risk_level,
            "score": report.score,
            "issues": report.issues,
            "suggestions": report.suggestions,
            "summary": report.summary,
            "action_suggestions": report.action_suggestions,
        }

    def _stale_response_if_needed(self, plan: DraftRevisionPlan, draft: ContentDraft) -> DraftRevisionApplyResponse | None:
        if plan.base_draft_updated_at and draft.updated_at and draft.updated_at > plan.base_draft_updated_at:
            return DraftRevisionApplyResponse(
                status="STALE_PLAN",
                account_id=plan.account_id,
                revision_plan_id=plan.id,
                source_draft_id=draft.id,
                review_report_id=plan.review_report_id,
                summary="The source draft changed after this revision plan was created.",
                error_code="STALE_PLAN",
                error_message="Source draft has changed; regenerate the revision plan before applying.",
            )
        return None

    def _llm_error(self, plan: DraftRevisionPlan, exc: LLMError) -> DraftRevisionApplyResponse:
        text = str(exc)
        if ProviderErrorCode.LLM_CONFIG_MISSING.value in text or ProviderErrorCode.LLM_PROVIDER_UNAVAILABLE.value in text:
            return DraftRevisionApplyResponse(
                status="PROVIDER_NOT_CONFIGURED",
                account_id=plan.account_id,
                revision_plan_id=plan.id,
                source_draft_id=plan.draft_id,
                review_report_id=plan.review_report_id,
                error_code=ProviderErrorCode.LLM_CONFIG_MISSING.value,
                error_message=text,
            )
        error_code = ProviderErrorCode.LLM_OUTPUT_FAILED.value
        if "parse" in text.lower() or "json" in text.lower():
            error_code = ProviderErrorCode.LLM_OUTPUT_PARSE_FAILED.value
        elif "schema" in text.lower() or "validation" in text.lower():
            error_code = ProviderErrorCode.LLM_SCHEMA_INVALID.value
        return self._failed(plan, error_code, text)

    def _failed(self, plan: DraftRevisionPlan, error_code: str, error_message: str) -> DraftRevisionApplyResponse:
        return DraftRevisionApplyResponse(
            status="FAILED",
            account_id=plan.account_id,
            revision_plan_id=plan.id,
            source_draft_id=plan.draft_id,
            review_report_id=plan.review_report_id,
            error_code=error_code,
            error_message=error_message,
        )

    def _blocked(self, plan: DraftRevisionPlan, error_code: str, error_message: str) -> DraftRevisionApplyResponse:
        return DraftRevisionApplyResponse(
            status="BLOCKED",
            account_id=plan.account_id,
            revision_plan_id=plan.id,
            source_draft_id=plan.draft_id,
            review_report_id=plan.review_report_id,
            error_code=error_code,
            error_message=error_message,
        )

    def _ensure_risk_safe(self, result: DraftRevisionApplyLLMResult) -> None:
        text = " ".join([result.title, result.content, " ".join(result.tags), result.cta or ""]).lower()
        violations = {rule for phrase, rule in RISK_PHRASES.items() if phrase.lower() in text}
        if violations:
            raise ValueError(f"RISK_BLOCKED: {', '.join(sorted(violations))}")

    def _update_current_state(self, conversation_id: int, account_id: int, draft_id: int) -> None:
        repo = AgentConversationRepository(self.db)
        conversation = self._get_conversation_or_raise(conversation_id)
        current_state = dict(conversation.current_state or {})
        current_state.update(
            {
                "active_account_id": account_id,
                "active_draft_id": draft_id,
                "current_target_type": "DRAFT",
                "current_target_id": draft_id,
                "last_action": "APPLY_REVISION_PLAN",
            }
        )
        repo.update_state(conversation, current_state, account_id=account_id)

    def _get_plan_or_raise(self, plan_id: int) -> DraftRevisionPlan:
        plan = self.db.get(DraftRevisionPlan, plan_id)
        if not plan:
            raise DraftRevisionApplyNotFound("revision plan not found")
        return plan

    def _get_source_draft_or_raise(self, draft_id: int) -> ContentDraft:
        draft = self.db.get(ContentDraft, draft_id)
        if not draft:
            raise DraftRevisionApplyNotFound("source draft not found")
        return draft

    def _get_experiment_or_raise(self, experiment_id: int) -> ContentExperiment:
        experiment = self.db.get(ContentExperiment, experiment_id)
        if not experiment:
            raise DraftRevisionApplyNotFound("experiment not found")
        return experiment

    def _get_account_or_raise(self, account_id: int) -> AccountProfile:
        account = self.db.get(AccountProfile, account_id)
        if not account:
            raise DraftRevisionApplyNotFound("account not found")
        return account

    def _get_review_report(self, review_report_id: int | None) -> ReviewReport | None:
        return self.db.get(ReviewReport, review_report_id) if review_report_id else None

    def _get_conversation_or_raise(self, conversation_id: int) -> AgentConversation:
        conversation = self.db.get(AgentConversation, conversation_id)
        if not conversation:
            raise DraftRevisionApplyNotFound("conversation not found")
        return conversation
