from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session

from app.agent.product_entry.executor import ActionHandlerRegistry
from app.agent.product_entry.schemas import Action, PlanStep
from app.context.context_compressor import (
    select_competitor_evidence_top_k,
    select_strategy_memory_items,
    summarize_comment_insights,
)
from app.models.competitor_comment import CompetitorComment
from app.models.competitors_analysis import CompetitorAnalysisReport
from app.models.content_opportunity import ContentOpportunity
from app.models.strategy_memory import StrategyMemory
from app.services.account_sev import AccountProfileService


def query_account_profile_handler(step: PlanStep, context: dict[str, Any]) -> dict[str, Any]:
    """查询账号画像，只读复用现有 AccountProfileService。"""
    account_id = _account_id(step, context)
    service = _account_service(context)
    account = service.get_account(account_id)

    summary_parts = [
        f"账号定位：{account.positioning}",
        f"目标用户：{account.target_audience}",
    ]
    if account.content_domain:
        summary_parts.append(f"内容领域：{account.content_domain}")
    if account.tone_preference:
        summary_parts.append(f"语气偏好：{account.tone_preference}")

    return {
        "account_id": account.id,
        "account_name": account.account_name,
        "platform": account.platform,
        "content_domain": account.content_domain,
        "positioning": account.positioning,
        "target_audience": account.target_audience,
        "persona": account.persona,
        "tone_preference": account.tone_preference,
        "risk_preference": account.risk_preference,
        "account_stage": account.account_stage,
        "primary_goal": account.primary_goal,
        "summary": "；".join(summary_parts),
    }


def query_competitor_evidence_handler(step: PlanStep, context: dict[str, Any]) -> dict[str, Any]:
    """查询草稿生成前可用的竞品证据，只读复用 Context Engineering Top-K 规则。"""
    account_id = _account_id(step, context)
    account = _account_service(context).get_account(account_id)
    db = _db_session(context)

    items = _competitor_opportunity_items(db, account_id)
    items.extend(_competitor_report_items(db, account_id))
    selected, compression = select_competitor_evidence_top_k(
        items,
        top_k=5,
        query_context=_account_query_context(account),
    )
    return {
        "items": [_public_competitor_evidence_item(item) for item in selected],
        "total": len(selected),
        "data_status": _evidence_data_status(selected, items),
        "summary": f"Found {len(selected)} readonly competitor evidence item(s).",
        "compression": compression,
    }


def query_comment_insight_handler(step: PlanStep, context: dict[str, Any]) -> dict[str, Any]:
    """查询评论洞察摘要；评论原文只作为 untrusted_text 返回。"""
    account_id = _account_id(step, context)
    _account_service(context).get_account(account_id)
    db = _db_session(context)

    items = _comment_insight_items(db, account_id)
    summary, compression = summarize_comment_insights(items, top_k=6)
    return {
        **summary,
        "summary": _comment_summary_text(summary),
        "compression": compression,
    }


def query_strategy_memory_handler(step: PlanStep, context: dict[str, Any]) -> dict[str, Any]:
    """查询当前账号可用于后续草稿上下文的策略记忆，不创建或更新 memory。"""
    account_id = _account_id(step, context)
    account = _account_service(context).get_account(account_id)
    db = _db_session(context)

    memories = (
        db.query(StrategyMemory)
        .filter(StrategyMemory.account_id == account_id, StrategyMemory.status.in_(["CANDIDATE", "VALIDATED"]))
        .order_by(StrategyMemory.updated_at.desc(), StrategyMemory.id.desc())
        .limit(20)
        .all()
    )
    items = [_strategy_memory_item(memory) for memory in memories]
    selected, compression = select_strategy_memory_items(
        items,
        top_k=5,
        query_context=_account_query_context(account),
    )
    return {
        "items": [_public_strategy_memory_item(item) for item in selected],
        "total": len(selected),
        "data_status": _strategy_memory_data_status(selected, items),
        "summary": f"Found {len(selected)} readonly strategy memory item(s).",
        "compression": compression,
    }


def build_readonly_action_handler_registry(db: Session) -> ActionHandlerRegistry:
    """构建只读 REAL 执行白名单，只注册安全的查询类 Action。"""
    registry = ActionHandlerRegistry()
    registry.register(Action.QUERY_ACCOUNT_PROFILE, query_account_profile_handler)
    registry.register(Action.QUERY_COMPETITOR_EVIDENCE, query_competitor_evidence_handler)
    registry.register(Action.QUERY_COMMENT_INSIGHT, query_comment_insight_handler)
    registry.register(Action.QUERY_STRATEGY_MEMORY, query_strategy_memory_handler)
    return registry


def _account_id(step: PlanStep, context: dict[str, Any]) -> int:
    value = step.input_params.get("account_id") or step.inputs.get("account_id") or context.get("account_id")
    if value is None:
        raise ValueError("account_id is required")
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("account_id must be an integer") from exc


def _account_service(context: dict[str, Any]) -> AccountProfileService:
    service = context.get("account_service")
    if isinstance(service, AccountProfileService):
        return service
    db = context.get("db")
    if db is None:
        raise ValueError("db session is required")
    return AccountProfileService(db)


def _db_session(context: dict[str, Any]) -> Session:
    db = context.get("db")
    if db is None:
        raise ValueError("db session is required")
    return db


def _competitor_opportunity_items(db: Session, account_id: int) -> list[dict[str, Any]]:
    rows = (
        db.query(ContentOpportunity, CompetitorAnalysisReport)
        .join(CompetitorAnalysisReport, ContentOpportunity.report_id == CompetitorAnalysisReport.id)
        .filter(CompetitorAnalysisReport.account_id == account_id)
        .order_by(ContentOpportunity.opportunity_score.desc(), ContentOpportunity.id.desc())
        .limit(20)
        .all()
    )
    items: list[dict[str, Any]] = []
    for opportunity, report in rows:
        item = _compact_dict(
            {
                "source": "content_opportunity",
                "source_type": "competitor_report",
                "data_status": "REAL" if report.status == "SUCCESS" else "PARTIAL",
                "opportunity_id": opportunity.id,
                "report_id": report.id,
                "title": opportunity.opportunity_title,
                "summary": opportunity.suggested_angle,
                "evidence_summary": opportunity.evidence_summary,
                "content_pillar": opportunity.content_pillar,
                "target_audience": opportunity.target_audience,
                "comment_demand_type": opportunity.comment_demand_type,
                "confidence": _score_to_confidence(opportunity.replicability_score),
                "risk_level": opportunity.risk_level,
                "created_at": _iso(opportunity.created_at),
            }
        )
        if item:
            items.append(item)
    return items


def _competitor_report_items(db: Session, account_id: int) -> list[dict[str, Any]]:
    reports = (
        db.query(CompetitorAnalysisReport)
        .filter(CompetitorAnalysisReport.account_id == account_id)
        .order_by(CompetitorAnalysisReport.updated_at.desc(), CompetitorAnalysisReport.id.desc())
        .limit(10)
        .all()
    )
    items: list[dict[str, Any]] = []
    for report in reports:
        item = _compact_dict(
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
                "created_at": _iso(report.created_at),
            }
        )
        if item.get("summary") or item.get("content_pillar") or item.get("comment_demand_type"):
            items.append(item)
    return items


def _comment_insight_items(db: Session, account_id: int) -> list[dict[str, Any]]:
    reports = (
        db.query(CompetitorAnalysisReport)
        .filter(CompetitorAnalysisReport.account_id == account_id)
        .order_by(CompetitorAnalysisReport.updated_at.desc(), CompetitorAnalysisReport.id.desc())
        .limit(10)
        .all()
    )
    items: list[dict[str, Any]] = []
    for report in reports:
        data_status = "REAL" if report.comment_count >= 3 else "DATA_INSUFFICIENT"
        for demand in report.comment_demands or []:
            items.append(
                _compact_dict(
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
        for signal in report.conversion_signals or []:
            items.append(
                _compact_dict(
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
                _compact_dict(
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

    comments = (
        db.query(CompetitorComment)
        .filter(CompetitorComment.account_id == account_id)
        .order_by(CompetitorComment.like_count.desc(), CompetitorComment.id.desc())
        .limit(20)
        .all()
    )
    comment_status = "REAL" if len(comments) >= 3 else ("DATA_INSUFFICIENT" if comments else "NOT_PROVIDED")
    for comment in comments:
        raw = comment.raw_snapshot or {}
        items.append(
            _compact_dict(
                {
                    "item_type": "comment",
                    "demand_type": raw.get("demand_type"),
                    "untrusted_text": comment.content,
                    "like_count": comment.like_count,
                    "source": "competitor_comment",
                    "source_type": comment.source_type,
                    "provider_name": comment.provider_name,
                    "is_mock": comment.is_mock,
                    "confidence": comment.confidence,
                    "data_status": comment_status,
                    "collected_at": _iso(comment.collected_at),
                }
            )
        )
    return [item for item in items if item]


def _strategy_memory_item(memory: StrategyMemory) -> dict[str, Any]:
    metadata = memory.metadata_payload or {}
    return _compact_dict(
        {
            "memory_id": memory.id,
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
            "created_at": _iso(memory.created_at),
            "updated_at": _iso(memory.updated_at),
        }
    )


def _account_query_context(account) -> dict[str, Any]:
    return _compact_dict(
        {
            "account_keywords": _non_empty_values(account.content_domain, account.positioning, account.target_audience),
            "domain_keywords": _non_empty_values(account.content_domain),
            "account_profile": {
                "content_domain": account.content_domain,
                "positioning": account.positioning,
                "target_audience": account.target_audience,
                "account_type": account.account_stage,
            },
        }
    )


def _public_competitor_evidence_item(item: dict[str, Any]) -> dict[str, Any]:
    return _compact_dict(
        {
            "source_type": item.get("source_type"),
            "opportunity_id": item.get("opportunity_id"),
            "report_id": item.get("report_id"),
            "title": item.get("title"),
            "summary": item.get("summary") or item.get("evidence_summary"),
            "content_pillar": item.get("content_pillar"),
            "target_audience": item.get("target_audience"),
            "comment_demand_type": item.get("comment_demand_type"),
            "confidence": item.get("confidence"),
            "risk_level": item.get("risk_level"),
        }
    )


def _public_strategy_memory_item(item: dict[str, Any]) -> dict[str, Any]:
    return _compact_dict(
        {
            "memory_id": item.get("memory_id") or item.get("id"),
            "memory_type": item.get("memory_type"),
            "status": item.get("status"),
            "summary": item.get("summary"),
            "pattern": item.get("pattern"),
            "confidence": item.get("confidence"),
            "support_count": item.get("support_count"),
            "risk_level": item.get("risk_level"),
        }
    )


def _comment_summary_text(summary: dict[str, Any]) -> str:
    data_status = summary.get("data_status") or "NOT_PROVIDED"
    demand_count = len(summary.get("demand_summary") or [])
    comment_count = len(summary.get("representative_comments") or [])
    return f"Comment insight status={data_status}, demands={demand_count}, representative_comments={comment_count}."


def _evidence_data_status(selected: list[dict[str, Any]], all_items: list[dict[str, Any]]) -> str:
    if not all_items:
        return "NOT_PROVIDED"
    if not selected:
        return "DATA_INSUFFICIENT"
    if any(item.get("data_status") == "REAL" for item in selected):
        return "REAL"
    return "PARTIAL"


def _strategy_memory_data_status(selected: list[dict[str, Any]], all_items: list[dict[str, Any]]) -> str:
    if not all_items:
        return "NOT_PROVIDED"
    if not selected:
        return "DATA_INSUFFICIENT"
    if any(item.get("data_status") == "REAL" for item in selected):
        return "REAL"
    return "PARTIAL"


def _first_named_item(items: list[dict[str, Any]] | None) -> str | None:
    for item in items or []:
        if isinstance(item, dict):
            value = item.get("name") or item.get("type") or item.get("title")
            if value:
                return str(value)
        elif item:
            return str(item)
    return None


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


def _compact_dict(payload: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in payload.items() if value not in (None, "", [], {})}


def _non_empty_values(*values: Any) -> list[Any]:
    return [value for value in values if value not in (None, "", [], {})]


def _iso(value: Any) -> str | None:
    return value.isoformat() if value else None
