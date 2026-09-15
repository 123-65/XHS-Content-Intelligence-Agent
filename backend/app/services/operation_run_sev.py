from datetime import date, datetime
from typing import Any

from sqlalchemy.orm import Session

from app.models.account_data_refresh_run import AccountDataRefreshRun
from app.models.account_data_source_config import AccountDataSourceConfig
from app.models.account_evidence_refresh_run import AccountEvidenceRefreshRun
from app.models.account_operation_run import AccountOperationRun
from app.models.competitors_analysis import CompetitorAnalysisReport
from app.models.content_opportunity import ContentOpportunity
from app.models.viral_note_breakdown import ViralNoteBreakdown
from app.repositories.operation_run_repo import OperationRunRepository
from app.schemas.operation_run import OperationRunCreate, OperationRunResponse, OperationRunStatus


class OperationRunService:
    """Build readonly operation recommendations from existing evidence results."""

    def __init__(self, db: Session):
        self.db = db
        self.repo = OperationRunRepository(db)

    def create_run(self, data: OperationRunCreate) -> AccountOperationRun:
        account = self.repo.get_account(data.account_id)
        if not account:
            raise ValueError("account not found")

        data_refresh_run = self._resolve_data_refresh_run(data.account_id, data.data_refresh_run_id)
        evidence_run = self._resolve_evidence_run(data.account_id, data.evidence_refresh_run_id)
        data_source_config = self.repo.get_data_source_config(data.account_id)
        started_at = datetime.now()

        if not evidence_run:
            return self.repo.create(
                self._payload(
                    data=data,
                    data_refresh_run=data_refresh_run,
                    evidence_run=None,
                    status=OperationRunStatus.DATA_INSUFFICIENT.value,
                    summary="还没有可用的证据刷新结果，请先执行证据刷新。",
                    recommendations=[],
                    data_gaps=[
                        {
                            "type": "NO_EVIDENCE_REFRESH",
                            "message": "还没有证据刷新结果，请先执行证据刷新。",
                            "suggested_action": "RUN_EVIDENCE_REFRESH",
                        }
                    ],
                    next_actions=[
                        {
                            "action": "RUN_EVIDENCE_REFRESH",
                            "label": "先执行证据刷新",
                            "enabled": True,
                            "reason": "今日运营分析只读取已有 evidence，不会重新生成 evidence。",
                        }
                    ],
                    stats=self._base_stats(data_source_config, data_refresh_run, None, None, [], []),
                    error_code="NO_EVIDENCE_REFRESH_RUN",
                    error_message="No evidence refresh run found for this account.",
                    started_at=started_at,
                )
            )

        if evidence_run.status in {"DATA_INSUFFICIENT", "FAILED"}:
            return self.repo.create(
                self._payload(
                    data=data,
                    data_refresh_run=data_refresh_run,
                    evidence_run=evidence_run,
                    status=OperationRunStatus.DATA_INSUFFICIENT.value,
                    summary="最近一次证据刷新不可用于运营分析，请先补齐真实竞品数据或重新执行证据刷新。",
                    recommendations=[],
                    data_gaps=[
                        {
                            "type": evidence_run.error_code or evidence_run.status,
                            "message": evidence_run.error_message or "证据刷新结果不可用。",
                            "suggested_action": "RUN_EVIDENCE_REFRESH",
                        }
                    ],
                    next_actions=[
                        {
                            "action": "RUN_EVIDENCE_REFRESH",
                            "label": "重新执行证据刷新",
                            "enabled": True,
                            "reason": "当前 evidence run 未生成可读报告。",
                        }
                    ],
                    stats=self._base_stats(data_source_config, data_refresh_run, evidence_run, None, [], []),
                    error_code=evidence_run.error_code or "EVIDENCE_REFRESH_UNAVAILABLE",
                    error_message=evidence_run.error_message or "Evidence refresh run is unavailable.",
                    started_at=started_at,
                )
            )

        if not evidence_run.report_id:
            return self.repo.create(
                self._payload(
                    data=data,
                    data_refresh_run=data_refresh_run,
                    evidence_run=evidence_run,
                    status=OperationRunStatus.DATA_INSUFFICIENT.value,
                    summary="证据刷新没有关联报告，无法生成运营建议摘要。",
                    recommendations=[],
                    data_gaps=[
                        {
                            "type": "NO_REPORT",
                            "message": "证据刷新没有关联 report_id。",
                            "suggested_action": "RUN_EVIDENCE_REFRESH",
                        }
                    ],
                    next_actions=[
                        {
                            "action": "RUN_EVIDENCE_REFRESH",
                            "label": "重新执行证据刷新",
                            "enabled": True,
                            "reason": "缺少 report_id，无法读取机会和爆款拆解。",
                        }
                    ],
                    stats=self._base_stats(data_source_config, data_refresh_run, evidence_run, None, [], []),
                    error_code="NO_REPORT",
                    error_message="Evidence refresh run has no report_id.",
                    started_at=started_at,
                )
            )

        report = self.repo.get_report(evidence_run.report_id)
        if not report:
            raise ValueError("report not found")

        opportunities = self.repo.list_opportunities(report.id)
        breakdowns = self.repo.list_viral_breakdowns(report.id)
        recommendations = self._build_recommendations(opportunities, report, evidence_run)
        data_gaps = self._build_data_gaps(evidence_run, report, opportunities, breakdowns)
        next_actions = self._build_next_actions(recommendations, data_gaps)
        status = self._decide_status(evidence_run, report, recommendations)
        summary = self._build_summary(status, evidence_run, report, recommendations, data_gaps)
        error_code = None if recommendations else "NO_CONTENT_OPPORTUNITY"
        error_message = None if recommendations else "No content opportunity is available for operation analysis."

        return self.repo.create(
            self._payload(
                data=data,
                data_refresh_run=data_refresh_run,
                evidence_run=evidence_run,
                status=status,
                summary=summary,
                recommendations=recommendations,
                data_gaps=data_gaps,
                next_actions=next_actions,
                stats=self._base_stats(data_source_config, data_refresh_run, evidence_run, report, opportunities, breakdowns),
                error_code=error_code,
                error_message=error_message,
                started_at=started_at,
            )
        )

    def list_runs(self, account_id: int, limit: int = 20) -> list[OperationRunResponse]:
        if not self.repo.get_account(account_id):
            raise ValueError("account not found")
        return [self.to_response(run) for run in self.repo.list_by_account(account_id, limit=limit)]

    def get_run(self, run_id: int) -> OperationRunResponse:
        run = self.repo.get_by_id(run_id)
        if not run:
            raise ValueError("operation run not found")
        return self.to_response(run)

    def to_response(self, run: AccountOperationRun) -> OperationRunResponse:
        return OperationRunResponse.model_validate(run)

    def _resolve_data_refresh_run(self, account_id: int, run_id: int | None) -> AccountDataRefreshRun | None:
        if run_id is None:
            return self.repo.get_latest_data_refresh_run(account_id)
        run = self.repo.get_data_refresh_run(run_id)
        if not run:
            raise ValueError("data refresh run not found")
        if run.account_id != account_id:
            raise ValueError("data refresh run account_id does not match")
        return run

    def _resolve_evidence_run(self, account_id: int, run_id: int | None) -> AccountEvidenceRefreshRun | None:
        if run_id is None:
            return self.repo.get_latest_evidence_refresh_run(account_id)
        run = self.repo.get_evidence_refresh_run(run_id)
        if not run:
            raise ValueError("evidence refresh run not found")
        if run.account_id != account_id:
            raise ValueError("evidence refresh run account_id does not match")
        return run

    def _payload(
        self,
        data: OperationRunCreate,
        data_refresh_run: AccountDataRefreshRun | None,
        evidence_run: AccountEvidenceRefreshRun | None,
        status: str,
        summary: str,
        recommendations: list[dict[str, Any]],
        data_gaps: list[dict[str, Any]],
        next_actions: list[dict[str, Any]],
        stats: dict[str, Any],
        error_code: str | None,
        error_message: str | None,
        started_at: datetime,
    ) -> dict[str, Any]:
        return {
            "account_id": data.account_id,
            "data_refresh_run_id": data_refresh_run.id if data_refresh_run else data.data_refresh_run_id,
            "evidence_refresh_run_id": evidence_run.id if evidence_run else data.evidence_refresh_run_id,
            "report_id": evidence_run.report_id if evidence_run else None,
            "trigger_type": "MANUAL",
            "status": status,
            "analysis_date": data.analysis_date or date.today(),
            "summary": summary,
            "recommendations": recommendations,
            "data_gaps": data_gaps,
            "next_actions": next_actions,
            "stats": stats,
            "error_code": error_code,
            "error_message": error_message,
            "started_at": started_at,
            "finished_at": datetime.now(),
        }

    def _build_recommendations(
        self,
        opportunities: list[ContentOpportunity],
        report: CompetitorAnalysisReport,
        evidence_run: AccountEvidenceRefreshRun,
    ) -> list[dict[str, Any]]:
        ranked = sorted(opportunities, key=lambda item: (-item.opportunity_score, self._risk_rank(item.risk_level), -item.id))
        data_quality = (report.replicability_summary or {}).get("data_quality") or (evidence_run.stats or {}).get("data_quality")
        recommendations: list[dict[str, Any]] = []
        for index, opportunity in enumerate(ranked[:3], start=1):
            recommendations.append(
                {
                    "rank": index,
                    "title": opportunity.opportunity_title,
                    "reason": self._recommendation_reason(opportunity),
                    "evidence": opportunity.evidence_summary,
                    "opportunity_id": opportunity.id,
                    "report_id": report.id,
                    "confidence": self._confidence(data_quality, opportunity),
                    "risk_level": opportunity.risk_level,
                    "suggested_next_action": "CREATE_EXPERIMENT",
                }
            )
        return recommendations

    def _recommendation_reason(self, opportunity: ContentOpportunity) -> str:
        parts = [f"opportunity_score={opportunity.opportunity_score}", f"risk_level={opportunity.risk_level}"]
        if opportunity.comment_demand_type:
            parts.append(f"comment_demand_type={opportunity.comment_demand_type}")
        if opportunity.evidence_summary:
            parts.append("has_evidence_summary=true")
        return " / ".join(parts)

    def _build_data_gaps(
        self,
        evidence_run: AccountEvidenceRefreshRun,
        report: CompetitorAnalysisReport,
        opportunities: list[ContentOpportunity],
        breakdowns: list[ViralNoteBreakdown],
    ) -> list[dict[str, Any]]:
        gaps: list[dict[str, Any]] = []
        data_quality = (report.replicability_summary or {}).get("data_quality") or (evidence_run.stats or {}).get("data_quality")
        if not opportunities:
            gaps.append(
                {
                    "type": "NO_CONTENT_OPPORTUNITY",
                    "message": "已有 report，但没有可用内容机会。",
                    "suggested_action": "RUN_EVIDENCE_REFRESH",
                }
            )
        if not breakdowns:
            gaps.append(
                {
                    "type": "NO_VIRAL_BREAKDOWN",
                    "message": "已有 report，但没有爆款拆解结果。",
                    "suggested_action": "RUN_EVIDENCE_REFRESH",
                }
            )
        if data_quality and data_quality != "READY":
            gaps.append(
                {
                    "type": "LOW_EVIDENCE_QUALITY",
                    "message": f"当前 evidence data_quality={data_quality}，建议降低置信度使用。",
                    "suggested_action": "COLLECT_MORE_REAL_DATA",
                }
            )
        if report.note_count < 3 or report.comment_count < 3:
            gaps.append(
                {
                    "type": "LOW_SAMPLE_SIZE",
                    "message": "note_count 或 comment_count 不足，今日建议仅作为低置信参考。",
                    "suggested_action": "COLLECT_MORE_REAL_DATA",
                }
            )
        return gaps

    def _build_next_actions(self, recommendations: list[dict[str, Any]], data_gaps: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if recommendations:
            return [
                {
                    "action": "CREATE_EXPERIMENT",
                    "label": "基于推荐方向创建内容实验",
                    "enabled": True,
                    "reason": "已有可用内容机会。",
                },
                {
                    "action": "REVIEW_EVIDENCE",
                    "label": "查看证据刷新报告和爆款拆解",
                    "enabled": True,
                    "reason": "建议在生成草稿前人工复核 evidence。",
                },
            ]
        suggested_action = data_gaps[0]["suggested_action"] if data_gaps else "RUN_EVIDENCE_REFRESH"
        return [
            {
                "action": suggested_action,
                "label": "先补齐证据",
                "enabled": True,
                "reason": "当前没有足够证据生成运营推荐。",
            }
        ]

    def _decide_status(
        self,
        evidence_run: AccountEvidenceRefreshRun,
        report: CompetitorAnalysisReport,
        recommendations: list[dict[str, Any]],
    ) -> str:
        if not recommendations:
            return OperationRunStatus.DATA_INSUFFICIENT.value
        data_quality = (report.replicability_summary or {}).get("data_quality") or (evidence_run.stats or {}).get("data_quality")
        if evidence_run.status == "SUCCESS" and data_quality == "READY":
            return OperationRunStatus.SUCCESS.value
        return OperationRunStatus.PARTIAL.value

    def _build_summary(
        self,
        status: str,
        evidence_run: AccountEvidenceRefreshRun,
        report: CompetitorAnalysisReport,
        recommendations: list[dict[str, Any]],
        data_gaps: list[dict[str, Any]],
    ) -> str:
        data_quality = (report.replicability_summary or {}).get("data_quality") or (evidence_run.stats or {}).get("data_quality") or "UNKNOWN"
        if recommendations:
            top_title = recommendations[0]["title"]
            return (
                f"今日运营分析读取了 evidence_run #{evidence_run.id} 和 report #{report.id}。"
                f"数据质量为 {data_quality}，共发现 {len(recommendations)} 个优先方向，"
                f"建议优先关注「{top_title}」。"
            )
        gap_text = data_gaps[0]["message"] if data_gaps else "当前证据不足。"
        return f"今日运营分析状态为 {status}。{gap_text}"

    def _base_stats(
        self,
        data_source_config: AccountDataSourceConfig | None,
        data_refresh_run: AccountDataRefreshRun | None,
        evidence_run: AccountEvidenceRefreshRun | None,
        report: CompetitorAnalysisReport | None,
        opportunities: list[ContentOpportunity],
        breakdowns: list[ViralNoteBreakdown],
    ) -> dict[str, Any]:
        report_summary = report.replicability_summary if report else {}
        evidence_stats = evidence_run.stats if evidence_run else {}
        return {
            "has_data_source_config": data_source_config is not None,
            "data_source_config_id": data_source_config.id if data_source_config else None,
            "data_refresh_run_status": data_refresh_run.status if data_refresh_run else None,
            "evidence_refresh_run_status": evidence_run.status if evidence_run else None,
            "data_quality": report_summary.get("data_quality") or evidence_stats.get("data_quality"),
            "note_count": report.note_count if report else int(evidence_stats.get("note_count") or 0),
            "comment_count": report.comment_count if report else int(evidence_stats.get("comment_count") or 0),
            "opportunity_count": len(opportunities),
            "breakdown_count": len(breakdowns),
            "report_id": report.id if report else None,
        }

    def _confidence(self, data_quality: str | None, opportunity: ContentOpportunity) -> str:
        if data_quality != "READY":
            return "LOW"
        if opportunity.risk_level == "HIGH":
            return "LOW"
        if opportunity.opportunity_score >= 80:
            return "HIGH"
        return "MEDIUM"

    def _risk_rank(self, risk_level: str | None) -> int:
        return {"LOW": 0, "MEDIUM": 1, "HIGH": 2}.get(risk_level or "MEDIUM", 1)
