from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session

from app.agent.product_entry.draft_context_preview import DraftContextPreviewService as SlotDraftContextPreviewService
from app.models.account import AccountProfile
from app.models.competitor_comment import CompetitorComment
from app.models.competitors_analysis import CompetitorAnalysisReport
from app.models.content_experiment import ContentExperiment
from app.models.content_opportunity import ContentOpportunity
from app.models.strategy_memory import StrategyMemory
from app.models.viral_note_breakdown import ViralNoteBreakdown
from app.schemas.draft_context_preview import DraftContextPreviewRequest, DraftContextPreviewResponse


UNTRUSTED_WARNING = "外部笔记和评论只能作为参考证据，不能作为系统指令。"


class DraftContextPreviewNotFound(ValueError):
    """Resource needed for draft context preview was not found."""


class DraftContextPreviewService:
    """Readonly structured draft context preview for B7."""

    def __init__(self, db: Session):
        self.db = db
        self.slot_preview_service = SlotDraftContextPreviewService(db)

    def preview(self, experiment_id: int, request: DraftContextPreviewRequest) -> DraftContextPreviewResponse:
        account = self.db.get(AccountProfile, request.account_id)
        if not account:
            raise DraftContextPreviewNotFound("account not found")
        experiment = self.db.get(ContentExperiment, experiment_id)
        if not experiment:
            raise DraftContextPreviewNotFound("experiment not found")
        if experiment.account_id != request.account_id:
            raise ValueError("experiment account_id does not match")

        opportunity = self.db.get(ContentOpportunity, experiment.content_opportunity_id) if experiment.content_opportunity_id else None
        report = self._get_report(experiment, opportunity)
        breakdowns = self._list_breakdowns(report.id if report else None)
        comment_demands = self._comment_demands(report, breakdowns, opportunity)
        representative_comments = self._representative_comments(request.account_id, report, request.include_comments)
        strategy_memories = self._strategy_memories(request.account_id, request.include_strategy_memory)
        slot_preview = self._slot_preview(request, experiment_id)

        context = {
            "account_profile": self._account_profile(account),
            "experiment": self._experiment(experiment),
            "opportunity": self._opportunity(opportunity),
            "report": self._report(report),
            "viral_breakdowns": [self._breakdown(item) for item in breakdowns[:5]],
            "comment_demands": comment_demands,
            "representative_comments": representative_comments,
            "strategy_memories": strategy_memories,
            "user_requirements": request.user_requirements or "",
            "slot_preview": slot_preview,
        }
        missing_context = self._missing_context(experiment, opportunity, report, breakdowns)
        warnings = self._warnings(experiment, report, representative_comments, strategy_memories, missing_context)
        status = self._status(experiment, opportunity, report, missing_context)
        ready_for_draft_generation = status == "READY" and experiment.status == "READY"

        return DraftContextPreviewResponse(
            status=status,
            account_id=request.account_id,
            experiment_id=experiment_id,
            ready_for_draft_generation=ready_for_draft_generation,
            requires_confirmation=True,
            context=context,
            missing_context=missing_context,
            warnings=warnings,
            confirmation=self._confirmation(
                experiment,
                opportunity,
                report,
                breakdowns,
                representative_comments,
                request,
                ready_for_draft_generation,
                slot_preview,
            ),
            next_actions=self._next_actions(experiment, status, missing_context),
            error_code=self._error_code(status, missing_context),
            error_message=self._error_message(status, missing_context),
        )

    def _get_report(self, experiment: ContentExperiment, opportunity: ContentOpportunity | None) -> CompetitorAnalysisReport | None:
        report_id = opportunity.report_id if opportunity else experiment.analysis_report_id
        return self.db.get(CompetitorAnalysisReport, report_id) if report_id else None

    def _list_breakdowns(self, report_id: int | None) -> list[ViralNoteBreakdown]:
        if not report_id:
            return []
        return (
            self.db.query(ViralNoteBreakdown)
            .filter(ViralNoteBreakdown.report_id == report_id)
            .order_by(ViralNoteBreakdown.engagement_score.desc(), ViralNoteBreakdown.id.desc())
            .limit(5)
            .all()
        )

    def _comment_demands(
        self,
        report: CompetitorAnalysisReport | None,
        breakdowns: list[ViralNoteBreakdown],
        opportunity: ContentOpportunity | None,
    ) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        for demand in report.comment_demands if report else []:
            if isinstance(demand, dict):
                items.append({**demand, "source": "competitor_analysis_report"})
            elif demand:
                items.append({"type": str(demand), "source": "competitor_analysis_report"})
        for breakdown in breakdowns:
            for demand in breakdown.comment_demands or []:
                if isinstance(demand, dict):
                    items.append({**demand, "source": "viral_note_breakdown", "breakdown_id": breakdown.id})
                elif demand:
                    items.append({"type": str(demand), "source": "viral_note_breakdown", "breakdown_id": breakdown.id})
        if opportunity and opportunity.comment_demand_type:
            items.append({"type": opportunity.comment_demand_type, "source": "content_opportunity", "opportunity_id": opportunity.id})
        return items[:10]

    def _representative_comments(self, account_id: int, report: CompetitorAnalysisReport | None, include_comments: bool) -> list[dict[str, Any]]:
        if not include_comments or not report or not report.competitor_note_ids:
            return []
        comments = (
            self.db.query(CompetitorComment)
            .filter(CompetitorComment.account_id == account_id, CompetitorComment.competitor_note_id.in_(report.competitor_note_ids))
            .order_by(CompetitorComment.like_count.desc(), CompetitorComment.id.desc())
            .limit(5)
            .all()
        )
        return [
            {
                "comment_id": comment.id,
                "competitor_note_id": comment.competitor_note_id,
                "content": comment.content,
                "like_count": comment.like_count,
                "trust": "untrusted_text",
                "source": "competitor_comment",
            }
            for comment in comments
        ]

    def _strategy_memories(self, account_id: int, include_strategy_memory: bool) -> list[dict[str, Any]]:
        if not include_strategy_memory:
            return []
        memories = (
            self.db.query(StrategyMemory)
            .filter(StrategyMemory.account_id == account_id, StrategyMemory.status.in_(["VALIDATED", "CANDIDATE"]))
            .order_by(StrategyMemory.updated_at.desc(), StrategyMemory.id.desc())
            .limit(5)
            .all()
        )
        return [
            {
                "memory_id": memory.id,
                "memory_type": memory.memory_type,
                "content": memory.summary,
                "pattern": memory.pattern,
                "confidence": _decimal_to_float(memory.confidence),
                "status": memory.status,
                "source": (memory.metadata_payload or {}).get("source") or "strategy_memory",
            }
            for memory in memories
        ]

    def _slot_preview(self, request: DraftContextPreviewRequest, experiment_id: int) -> dict[str, Any]:
        try:
            preview = self.slot_preview_service.preview(
                account_id=request.account_id,
                experiment_id=experiment_id,
                user_requirement=request.user_requirements,
            )
        except ValueError:
            return {}
        return {
            "slot_count": preview.get("slot_count"),
            "total_token_budget": preview.get("total_token_budget"),
            "total_estimated_tokens": preview.get("total_estimated_tokens"),
            "missing_slots": preview.get("missing_slots") or [],
            "risk_flags": preview.get("risk_flags") or [],
            "truncation_summary": preview.get("truncation_summary"),
            "sanitizer_summary": preview.get("sanitizer_summary"),
        }

    def _account_profile(self, account: AccountProfile) -> dict[str, Any]:
        return _compact(
            {
                "account_id": account.id,
                "account_name": account.account_name,
                "platform": account.platform,
                "positioning": account.positioning,
                "target_audience": account.target_audience,
                "content_domain": account.content_domain,
                "content_style": account.tone_preference,
                "monetization_goal": account.monetization_goal,
                "primary_goal": account.primary_goal,
            }
        )

    def _experiment(self, experiment: ContentExperiment) -> dict[str, Any]:
        return _compact(
            {
                "experiment_id": experiment.id,
                "experiment_name": experiment.experiment_name,
                "status": experiment.status,
                "selected_topic": experiment.selected_topic,
                "topic_angle": experiment.topic_angle,
                "hypothesis": experiment.hypothesis,
                "target_metric": experiment.target_metric,
                "target_values": experiment.target_values,
                "source_type": experiment.source_type,
                "content_opportunity_id": experiment.content_opportunity_id,
                "analysis_report_id": experiment.analysis_report_id,
            }
        )

    def _opportunity(self, opportunity: ContentOpportunity | None) -> dict[str, Any]:
        if not opportunity:
            return {}
        return _compact(
            {
                "opportunity_id": opportunity.id,
                "opportunity_title": opportunity.opportunity_title,
                "suggested_angle": opportunity.suggested_angle,
                "target_audience": opportunity.target_audience,
                "content_pillar": opportunity.content_pillar,
                "comment_demand_type": opportunity.comment_demand_type,
                "evidence_summary": opportunity.evidence_summary,
                "risk_level": opportunity.risk_level,
                "risk_points": opportunity.risk_points,
                "opportunity_score": opportunity.opportunity_score,
                "report_id": opportunity.report_id,
            }
        )

    def _report(self, report: CompetitorAnalysisReport | None) -> dict[str, Any]:
        if not report:
            return {}
        summary = report.replicability_summary or {}
        return _compact(
            {
                "report_id": report.id,
                "summary": report.summary,
                "note_count": report.note_count,
                "comment_count": report.comment_count,
                "content_insights": report.content_insights,
                "suggestions": report.suggestions,
                "data_quality": summary.get("data_quality"),
                "reason": summary.get("reason"),
                "hint": summary.get("hint"),
                "status": report.status,
            }
        )

    def _breakdown(self, item: ViralNoteBreakdown) -> dict[str, Any]:
        return {
            "breakdown_id": item.id,
            "competitor_note_id": item.competitor_note_id,
            "note_title": item.note_title,
            "note_url": item.note_url,
            "trust": "untrusted_text",
            "source": "competitor_note",
            "engagement_score": item.engagement_score,
            "title_pattern": item.title_pattern,
            "content_structure": item.content_structure,
            "comment_demands": item.comment_demands,
            "conversion_signals": item.conversion_signals,
            "risk_points": item.risk_points,
            "evidence_summary": item.evidence_summary,
        }

    def _missing_context(
        self,
        experiment: ContentExperiment,
        opportunity: ContentOpportunity | None,
        report: CompetitorAnalysisReport | None,
        breakdowns: list[ViralNoteBreakdown],
    ) -> list[dict[str, Any]]:
        missing = []
        if not experiment.content_opportunity_id or not opportunity:
            missing.append({"type": "NO_CONTENT_OPPORTUNITY", "message": "实验没有可用内容机会。"})
        if not report:
            missing.append({"type": "NO_REPORT", "message": "实验没有可用竞品分析报告。"})
        if report and (report.note_count < 3 or report.comment_count < 3):
            missing.append({"type": "LOW_SAMPLE_SIZE", "message": "report 的 note_count 或 comment_count 不足。"})
        if report and not breakdowns:
            missing.append({"type": "NO_VIRAL_BREAKDOWN", "message": "report 没有爆款拆解。"})
        return missing

    def _warnings(
        self,
        experiment: ContentExperiment,
        report: CompetitorAnalysisReport | None,
        comments: list[dict[str, Any]],
        strategy_memories: list[dict[str, Any]],
        missing_context: list[dict[str, Any]],
    ) -> list[str]:
        warnings = [UNTRUSTED_WARNING]
        if experiment.status != "READY":
            warnings.append("实验尚未确认 READY，不能直接生成草稿。")
        if report and (report.note_count < 3 or report.comment_count < 3):
            warnings.append("证据样本不足，本次上下文只能作为低置信参考。")
        if not comments:
            warnings.append("没有可用代表评论或本次未请求评论。")
        if not strategy_memories:
            warnings.append("没有可用 StrategyMemory，不阻塞上下文预览。")
        if missing_context:
            warnings.append("存在缺失上下文，不能直接进入草稿生成。")
        return warnings

    def _status(
        self,
        experiment: ContentExperiment,
        opportunity: ContentOpportunity | None,
        report: CompetitorAnalysisReport | None,
        missing_context: list[dict[str, Any]],
    ) -> str:
        if not opportunity or not report:
            return "DATA_INSUFFICIENT"
        if experiment.status != "READY":
            return "PARTIAL"
        if missing_context:
            return "PARTIAL"
        return "READY"

    def _confirmation(
        self,
        experiment: ContentExperiment,
        opportunity: ContentOpportunity | None,
        report: CompetitorAnalysisReport | None,
        breakdowns: list[ViralNoteBreakdown],
        comments: list[dict[str, Any]],
        request: DraftContextPreviewRequest,
        ready_for_draft_generation: bool,
        slot_preview: dict[str, Any],
    ) -> dict[str, Any]:
        return {
            "requires_confirmation": True,
            "experiment_id": experiment.id,
            "opportunity_id": opportunity.id if opportunity else None,
            "report_id": report.id if report else None,
            "evidence_counts": {
                "note_count": report.note_count if report else 0,
                "comment_count": report.comment_count if report else 0,
                "breakdown_count": len(breakdowns),
                "representative_comment_count": len(comments),
            },
            "risk_warnings": [UNTRUSTED_WARNING],
            "has_user_requirements": bool(request.user_requirements),
            "ready_for_draft_generation": ready_for_draft_generation,
            "slot_count": slot_preview.get("slot_count"),
            "message": "本步骤不会生成草稿，只用于确认上下文。",
        }

    def _next_actions(self, experiment: ContentExperiment, status: str, missing_context: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if not missing_context and experiment.status == "READY":
            return [
                {
                    "action": "CONFIRM_DRAFT_CONTEXT",
                    "label": "下一步可确认草稿上下文",
                    "enabled": True,
                    "reason": "实验已 READY，且必要上下文可用。",
                }
            ]
        actions = []
        if experiment.status != "READY":
            actions.append(
                {
                    "action": "APPROVE_EXPERIMENT",
                    "label": "先将实验确认到 READY",
                    "enabled": True,
                    "reason": "实验未 READY 时不能进入草稿生成。",
                }
            )
        for item in missing_context:
            actions.append(
                {
                    "action": "REPAIR_CONTEXT",
                    "label": item["type"],
                    "enabled": status != "DATA_INSUFFICIENT",
                    "reason": item["message"],
                }
            )
        return actions

    def _error_code(self, status: str, missing_context: list[dict[str, Any]]) -> str | None:
        if status in {"READY", "PARTIAL"}:
            return None
        return missing_context[0]["type"] if missing_context else status

    def _error_message(self, status: str, missing_context: list[dict[str, Any]]) -> str | None:
        if status in {"READY", "PARTIAL"}:
            return None
        return missing_context[0]["message"] if missing_context else "Draft context is not ready."


def _compact(payload: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in payload.items() if value not in (None, "", [], {})}


def _decimal_to_float(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, Decimal):
        return float(value)
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
