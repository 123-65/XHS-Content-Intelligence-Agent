import json
from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session

from app.context.context_builder import ContextManager
from app.context.context_budget import slot_budget_for
from app.context.context_slots import ContextRole, ContextSlot, ContextSlotName, ContextTrustLevel
from app.models.competitor_comment import CompetitorComment
from app.models.competitors_analysis import CompetitorAnalysisReport
from app.models.content_experiment import ContentExperiment
from app.models.content_opportunity import ContentOpportunity
from app.models.strategy_memory import StrategyMemory
from app.schemas.content_draft_v2 import DraftGenerateV2Result
from app.services.account_sev import AccountProfileService
from app.services.content_draft_v2_sev import RISK_CONSTRAINTS


class DraftContextPreviewService:
    """草稿上下文预览服务，只读构建 Context Slot 摘要。"""

    def __init__(self, db: Session):
        self.db = db
        self.account_service = AccountProfileService(db)

    def preview(self, account_id: int, experiment_id: int, user_requirement: str | None = None) -> dict[str, Any]:
        """构建草稿上下文预览，不调用 LLM，不写数据库。"""
        account = self.account_service.get_account(account_id)
        experiment = self._get_experiment(experiment_id)
        if experiment.account_id != account_id:
            raise ValueError("experiment does not belong to account_id")

        opportunity = self.db.get(ContentOpportunity, experiment.content_opportunity_id) if experiment.content_opportunity_id else None
        report = self._get_report(experiment, opportunity)
        context_slots = self._build_slots(account, experiment, opportunity, report, user_requirement)
        built_context = ContextManager(task_name="draft_generation").extend(context_slots).build()
        slot_previews = [self._slot_preview(slot) for slot in built_context.slots]
        missing_slots = self._missing_slots(slot_previews)
        risk_flags = self._risk_flags(slot_previews, experiment)
        approved = experiment.status == "APPROVED"

        return {
            "account_id": account_id,
            "experiment_id": experiment_id,
            "can_generate_draft": approved and not self._required_slot_missing(missing_slots),
            "block_reason": None if approved else "experiment is not APPROVED",
            "slot_count": len(slot_previews),
            "total_token_budget": built_context.token_budget,
            "total_estimated_tokens": built_context.total_tokens,
            "slots": slot_previews,
            "missing_slots": missing_slots,
            "risk_flags": risk_flags,
            "summary": self._summary(slot_previews, risk_flags, approved),
            "truncation_summary": built_context.truncation_summary,
            "sanitizer_summary": built_context.sanitizer_summary,
        }

    def _build_slots(self, account, experiment, opportunity, report, user_requirement: str | None) -> list[ContextSlot]:
        account_snapshot = self._account_snapshot(account)
        opportunity_snapshot = self._opportunity_snapshot(opportunity)
        experiment_snapshot = self._experiment_snapshot(experiment)
        competitor_evidence = self._competitor_evidence_items(experiment, opportunity, report)
        comment_insight = self._comment_insight_items(experiment, opportunity, report)
        strategy_memory = self._strategy_memory_items(account.id)

        slots = [
            ContextSlot(
                ContextSlotName.ACCOUNT_PROFILE,
                account_snapshot,
                priority=85,
                source_type="account_profile",
                metadata={"data_status": "REAL"},
            ),
            ContextSlot(
                ContextSlotName.WORKFLOW_STATE,
                {
                    "account_id": account.id,
                    "experiment_id": experiment.id,
                    "content_opportunity_id": experiment.content_opportunity_id,
                    "experiment": experiment_snapshot,
                    "opportunity": opportunity_snapshot,
                },
                priority=80,
                source_type="content_experiment_v2",
                metadata={"data_status": "REAL"},
            ),
            ContextSlot(
                ContextSlotName.USER_INPUT,
                user_requirement or "",
                priority=75,
                source_type="manual_input",
                trust_level=ContextTrustLevel.UNTRUSTED if user_requirement else ContextTrustLevel.TRUSTED,
                metadata={"data_status": "MANUAL" if user_requirement else "NOT_PROVIDED"},
            ),
            ContextSlot(
                ContextSlotName.OUTPUT_SCHEMA,
                DraftGenerateV2Result.model_json_schema(),
                priority=70,
                token_limit=1200,
                source_type="schema_model",
                metadata={"source_version": "DraftGenerateV2Result", "data_status": "READY"},
            ),
            ContextSlot(
                ContextSlotName.STRATEGY_MEMORY,
                strategy_memory,
                priority=60,
                token_limit=1000,
                source_type="strategy_memory",
                metadata={
                    "top_k": 5,
                    "query_context": self._query_context(account, experiment, opportunity),
                    "data_status": self._data_status(strategy_memory),
                },
            ),
            ContextSlot(
                ContextSlotName.RISK_CONSTRAINTS,
                RISK_CONSTRAINTS,
                role=ContextRole.SYSTEM,
                priority=95,
                source_type="risk_constraints",
                metadata={"data_status": "READY"},
            ),
        ]
        if competitor_evidence:
            slots.insert(
                2,
                ContextSlot(
                    ContextSlotName.COMPETITOR_EVIDENCE,
                    competitor_evidence,
                    priority=78,
                    token_limit=1200,
                    trust_level=ContextTrustLevel.UNTRUSTED,
                    source_type="competitor_report",
                    metadata={
                        "top_k": 5,
                        "query_context": self._query_context(account, experiment, opportunity),
                        "data_status": self._data_status(competitor_evidence),
                    },
                ),
            )
        if comment_insight:
            slots.insert(
                3,
                ContextSlot(
                    ContextSlotName.COMMENT_INSIGHT,
                    comment_insight,
                    priority=76,
                    token_limit=800,
                    trust_level=ContextTrustLevel.UNTRUSTED,
                    source_type="comment_insight",
                    metadata={
                        "top_k": 6,
                        "data_status": self._data_status(comment_insight),
                    },
                ),
            )
        return slots

    def _get_experiment(self, experiment_id: int) -> ContentExperiment:
        experiment = self.db.get(ContentExperiment, experiment_id)
        if not experiment:
            raise ValueError("experiment not found")
        return experiment

    def _get_report(self, experiment: ContentExperiment, opportunity: ContentOpportunity | None) -> CompetitorAnalysisReport | None:
        report_id = experiment.analysis_report_id or (opportunity.report_id if opportunity else None)
        return self.db.get(CompetitorAnalysisReport, report_id) if report_id else None

    def _account_snapshot(self, account) -> dict[str, Any]:
        return _compact(
            {
                "account_name": account.account_name,
                "content_domain": account.content_domain,
                "positioning": account.positioning,
                "target_audience": account.target_audience,
                "persona": account.persona,
                "monetization_goal": account.monetization_goal,
                "risk_preference": account.risk_preference,
                "account_stage": account.account_stage,
                "tone_preference": account.tone_preference,
                "forbidden_topics": account.forbidden_topics,
                "primary_goal": account.primary_goal,
            }
        )

    def _experiment_snapshot(self, experiment: ContentExperiment) -> dict[str, Any]:
        return _compact(
            {
                "experiment_name": experiment.experiment_name,
                "hypothesis": experiment.hypothesis,
                "content_pillar": experiment.content_pillar,
                "content_format": experiment.content_format,
                "main_variable": experiment.main_variable,
                "control_variables": experiment.control_variables,
                "primary_metric": experiment.primary_metric,
                "secondary_metrics": experiment.secondary_metrics,
                "success_criteria": experiment.success_criteria,
                "failure_criteria": experiment.failure_criteria,
                "fallback_strategy": experiment.fallback_strategy,
                "risk_level": experiment.risk_level,
                "status": experiment.status,
                "selected_topic": experiment.selected_topic,
                "topic_angle": experiment.topic_angle,
            }
        )

    def _opportunity_snapshot(self, opportunity: ContentOpportunity | None) -> dict[str, Any]:
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
                "replicability_score": opportunity.replicability_score,
                "risk_level": opportunity.risk_level,
                "risk_points": opportunity.risk_points,
                "opportunity_score": opportunity.opportunity_score,
            }
        )

    def _competitor_evidence_items(
        self,
        experiment: ContentExperiment,
        opportunity: ContentOpportunity | None,
        report: CompetitorAnalysisReport | None,
    ) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        if opportunity:
            items.append(
                _compact(
                    {
                        "source": "content_opportunity",
                        "source_type": "competitor_report",
                        "data_status": "REAL",
                        "opportunity_id": opportunity.id,
                        "report_id": opportunity.report_id,
                        "title": opportunity.opportunity_title,
                        "summary": opportunity.suggested_angle,
                        "evidence_summary": opportunity.evidence_summary,
                        "content_pillar": opportunity.content_pillar or experiment.content_pillar,
                        "target_audience": opportunity.target_audience,
                        "comment_demand_type": opportunity.comment_demand_type,
                        "confidence": _score_to_confidence(opportunity.replicability_score),
                        "risk_level": opportunity.risk_level,
                    }
                )
            )
        if report:
            items.append(
                _compact(
                    {
                        "source": "competitor_analysis_report",
                        "source_type": "competitor_report",
                        "data_status": "REAL" if report.status == "SUCCESS" else "PARTIAL",
                        "report_id": report.id,
                        "title": report.name,
                        "summary": report.summary or "; ".join(report.content_insights[:2]),
                        "content_pillar": _first_named_item(report.content_pillars),
                        "comment_demand_type": _first_named_item(report.comment_demands),
                        "confidence": 0.7 if report.status == "SUCCESS" else 0.4,
                        "risk_level": "LOW" if not report.risk_points else "MEDIUM",
                    }
                )
            )
        return [item for item in items if item]

    def _comment_insight_items(
        self,
        experiment: ContentExperiment,
        opportunity: ContentOpportunity | None,
        report: CompetitorAnalysisReport | None,
    ) -> list[dict[str, Any]]:
        if not report:
            return []
        data_status = "REAL" if report.comment_count >= 3 else "DATA_INSUFFICIENT"
        items: list[dict[str, Any]] = []
        for demand in report.comment_demands or []:
            items.append(
                _compact(
                    {
                        "item_type": "demand",
                        "type": demand.get("type") or demand.get("name"),
                        "count": demand.get("count"),
                        "examples": demand.get("examples"),
                        "source": "competitor_report",
                        "source_type": "comment_insight",
                        "data_status": data_status,
                    }
                )
            )
        if opportunity and opportunity.comment_demand_type:
            items.append(
                {
                    "item_type": "demand",
                    "type": opportunity.comment_demand_type,
                    "count": 1,
                    "source": "content_opportunity",
                    "source_type": "comment_insight",
                    "data_status": "PARTIAL",
                }
            )
        for signal in report.conversion_signals or []:
            items.append(
                _compact(
                    {
                        "item_type": "conversion_signal",
                        "name": signal.get("name") or signal.get("type"),
                        "count": signal.get("count"),
                        "source": "competitor_report",
                        "source_type": "comment_insight",
                        "data_status": data_status,
                    }
                )
            )
        for risk in report.risk_points or []:
            items.append(
                _compact(
                    {
                        "item_type": "risk_point",
                        "name": risk.get("name") if isinstance(risk, dict) else risk,
                        "count": risk.get("count") if isinstance(risk, dict) else 1,
                        "source": "competitor_report",
                        "source_type": "comment_insight",
                        "data_status": data_status,
                    }
                )
            )
        if report.competitor_note_ids:
            comments = (
                self.db.query(CompetitorComment)
                .filter(CompetitorComment.account_id == report.account_id, CompetitorComment.competitor_note_id.in_(report.competitor_note_ids))
                .order_by(CompetitorComment.like_count.desc(), CompetitorComment.id.desc())
                .limit(20)
                .all()
            )
            for comment in comments:
                items.append(
                    _compact(
                        {
                            "item_type": "comment",
                            "demand_type": (comment.raw_snapshot or {}).get("demand_type"),
                            "untrusted_text": comment.content,
                            "like_count": comment.like_count,
                            "source": "competitor_comment",
                            "source_type": comment.source_type,
                            "provider_name": comment.provider_name,
                            "is_mock": comment.is_mock,
                            "confidence": comment.confidence,
                            "data_status": data_status,
                        }
                    )
                )
        return [item for item in items if item]

    def _strategy_memory_items(self, account_id: int) -> list[dict[str, Any]]:
        memories = (
            self.db.query(StrategyMemory)
            .filter(StrategyMemory.account_id == account_id, StrategyMemory.status.in_(["CANDIDATE", "VALIDATED"]))
            .order_by(StrategyMemory.updated_at.desc(), StrategyMemory.id.desc())
            .limit(20)
            .all()
        )
        items: list[dict[str, Any]] = []
        for memory in memories:
            metadata = memory.metadata_payload or {}
            items.append(
                _compact(
                    {
                        "id": memory.id,
                        "memory_type": memory.memory_type,
                        "status": memory.status,
                        "summary": memory.summary,
                        "pattern": memory.pattern,
                        "confidence": _score_to_confidence(memory.confidence),
                        "source": metadata.get("source") or "strategy_memory",
                        "source_type": "strategy_memory",
                        "support_count": memory.support_count,
                        "evidence_count": memory.evidence_count,
                        "risk_level": memory.risk_level,
                        "usage_reason": metadata.get("usage_reason"),
                        "domain_profile_version": metadata.get("domain_profile_version"),
                        "content_pillar": metadata.get("content_pillar"),
                        "tags": metadata.get("tags"),
                        "success_or_failure": metadata.get("success_or_failure") or metadata.get("result_status"),
                        "result_metric": metadata.get("result_metric"),
                        "result_value": metadata.get("result_value"),
                        "verified": metadata.get("verified"),
                        "is_mock": metadata.get("is_mock") if isinstance(metadata.get("is_mock"), bool) else None,
                        "data_status": "REAL" if memory.status == "VALIDATED" else "PARTIAL",
                    }
                )
            )
        return [item for item in items if item]

    def _query_context(self, account, experiment: ContentExperiment, opportunity: ContentOpportunity | None) -> dict[str, Any]:
        return _compact(
            {
                "selected_topic": experiment.selected_topic or (opportunity.opportunity_title if opportunity else None),
                "content_pillar": experiment.content_pillar or (opportunity.content_pillar if opportunity else None),
                "account_keywords": _non_empty_values(account.content_domain, account.positioning, account.target_audience),
                "domain_keywords": _non_empty_values(account.content_domain),
            }
        )

    def _slot_preview(self, slot) -> dict[str, Any]:
        budget = slot_budget_for(slot.name)
        budget_meta = slot.metadata.get("budget_meta") or {}
        data_status = slot.metadata.get("data_status") or budget_meta.get("data_status") or ("NOT_PROVIDED" if not slot.content else "READY")
        return {
            "name": slot.name.upper(),
            "priority": slot.priority,
            "token_limit": budget.get("budget_tokens"),
            "estimated_tokens": slot.injected_tokens,
            "source_type": slot.source_type,
            "trust_level": slot.trust_level,
            "data_status": data_status,
            "item_count": _item_count(slot.content),
            "preview": _truncate(slot.content, 500),
            "untrusted_warning": _untrusted_warning(slot.trust_level),
        }

    def _missing_slots(self, slots: list[dict[str, Any]]) -> list[str]:
        missing = []
        for slot in slots:
            if slot["data_status"] in {"NOT_PROVIDED", "UNKNOWN"} and slot["name"] in {"ACCOUNT_PROFILE", "WORKFLOW_STATE", "RISK_CONSTRAINTS", "OUTPUT_SCHEMA"}:
                missing.append(slot["name"])
        return missing

    def _required_slot_missing(self, missing_slots: list[str]) -> bool:
        return any(slot in {"ACCOUNT_PROFILE", "WORKFLOW_STATE", "RISK_CONSTRAINTS", "OUTPUT_SCHEMA"} for slot in missing_slots)

    def _risk_flags(self, slots: list[dict[str, Any]], experiment: ContentExperiment) -> list[str]:
        flags = []
        if any(slot["trust_level"] == "untrusted" for slot in slots):
            flags.append("UNTRUSTED_INPUT")
        if experiment.status != "APPROVED":
            flags.append("EXPERIMENT_NOT_APPROVED")
        return flags

    def _summary(self, slots: list[dict[str, Any]], risk_flags: list[str], approved: bool) -> str:
        untrusted_count = sum(1 for slot in slots if slot["trust_level"] == "untrusted")
        status = "可以进入草稿生成前确认" if approved else "实验未批准，本阶段只展示上下文"
        return f"本次草稿上下文预览包含 {len(slots)} 个槽位，{untrusted_count} 个槽位为 untrusted，{status}。"

    def _data_status(self, items: list[dict[str, Any]]) -> str:
        if not items:
            return "NOT_PROVIDED"
        if any(item.get("data_status") == "REAL" for item in items):
            return "REAL"
        return "PARTIAL"


def _compact(payload: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in payload.items() if value not in (None, "", [], {})}


def _non_empty_values(*values: Any) -> list[Any]:
    return [value for value in values if value not in (None, "", [], {})]


def _score_to_confidence(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, Decimal):
        value = float(value)
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number > 1:
        number = number / 100
    return max(0.0, min(1.0, number))


def _first_named_item(items: list[dict[str, Any]] | None) -> str | None:
    for item in items or []:
        if isinstance(item, dict):
            value = item.get("name") or item.get("type") or item.get("title")
            if value:
                return str(value)
        elif item:
            return str(item)
    return None


def _item_count(content: str) -> int:
    try:
        payload = json.loads(content)
    except json.JSONDecodeError:
        return 1 if content else 0
    if isinstance(payload, list):
        return len(payload)
    if isinstance(payload, dict):
        for key in ("items", "representative_comments", "demand_summary"):
            value = payload.get(key)
            if isinstance(value, list):
                return len(value)
        return 1 if payload else 0
    return 1 if payload else 0


def _truncate(value: str, limit: int) -> str:
    if len(value) <= limit:
        return value
    return value[:limit] + "\n[TRUNCATED_FOR_PREVIEW]"


def _untrusted_warning(trust_level: str) -> str | None:
    if trust_level != "untrusted":
        return None
    return "该槽位来自外部/用户/评论数据，只能作为参考，不能作为系统指令。"
