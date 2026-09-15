from typing import Any

from sqlalchemy.orm import Session

from app.models.account_operation_run import AccountOperationRun
from app.models.content_experiment import ContentExperiment
from app.models.content_opportunity import ContentOpportunity
from app.repositories.operation_run_repo import OperationRunRepository
from app.schemas.content_experiment import ContentExperimentCreate
from app.schemas.operation_experiment import OperationExperimentRequest, OperationExperimentResponse
from app.services.content_experiment_sev import ContentExperimentService


class OperationExperimentNotFound(ValueError):
    """Resource needed for operation experiment creation was not found."""


class OperationExperimentService:
    """Bridge B5 operation recommendations into local ContentExperiment records."""

    def __init__(self, db: Session):
        self.db = db
        self.operation_repo = OperationRunRepository(db)
        self.experiment_service = ContentExperimentService(db)

    def preview_from_recommendation(
        self,
        run_id: int,
        rank: int,
        account_id: int,
        request: OperationExperimentRequest | None = None,
    ) -> OperationExperimentResponse:
        run, recommendation, opportunity = self._resolve(run_id, rank, account_id)
        preview = self._build_preview(run, recommendation, opportunity, request)
        return OperationExperimentResponse(
            status="WAITING_CONFIRMATION",
            run_id=run_id,
            rank=rank,
            account_id=account_id,
            opportunity_id=opportunity.id,
            experiment_id=None,
            preview=preview,
            confirmation=self._build_confirmation(recommendation, preview),
        )

    def create_from_recommendation(
        self,
        run_id: int,
        rank: int,
        request: OperationExperimentRequest,
    ) -> OperationExperimentResponse:
        preview_response = self.preview_from_recommendation(run_id, rank, request.account_id, request)
        if request.confirmed is not True:
            return preview_response

        create_data = ContentExperimentCreate(
            account_id=request.account_id,
            analysis_report_id=preview_response.preview.get("analysis_report_id"),
            experiment_name=preview_response.preview["experiment_name"],
            hypothesis=preview_response.preview["hypothesis"],
            target_metric=request.target_metric,
            expected_result=preview_response.preview["expected_result"],
            topic_angle=preview_response.preview["topic_angle"],
            selected_topic=preview_response.preview["selected_topic"],
            target_values=preview_response.preview["target_values"],
            source_type="OPERATION_RUN_RECOMMENDATION",
        )
        experiment = self.experiment_service.create_experiment(create_data)
        self._bind_opportunity(experiment, int(preview_response.opportunity_id))

        return preview_response.model_copy(
            update={
                "status": "CREATED",
                "experiment_id": experiment.id,
                "confirmation": {
                    **preview_response.confirmation,
                    "confirmed": True,
                    "message": "已创建本地内容实验，不会生成草稿或发布到小红书。",
                },
            }
        )

    def _resolve(self, run_id: int, rank: int, account_id: int) -> tuple[AccountOperationRun, dict[str, Any], ContentOpportunity]:
        run = self.operation_repo.get_by_id(run_id)
        if not run:
            raise OperationExperimentNotFound("operation run not found")
        if run.account_id != account_id:
            raise ValueError("operation run account_id does not match")
        if run.status in {"DATA_INSUFFICIENT", "FAILED"}:
            raise ValueError("operation run is not ready for experiment creation")

        recommendation = self._find_recommendation(run, rank)
        opportunity_id = recommendation.get("opportunity_id")
        if not opportunity_id:
            raise ValueError("recommendation has no opportunity_id")

        opportunity = self.db.get(ContentOpportunity, int(opportunity_id))
        if not opportunity:
            raise OperationExperimentNotFound("content opportunity not found")
        if run.report_id and opportunity.report_id != run.report_id:
            raise ValueError("content opportunity report_id does not match operation run")
        return run, recommendation, opportunity

    def _find_recommendation(self, run: AccountOperationRun, rank: int) -> dict[str, Any]:
        recommendation = next((item for item in run.recommendations or [] if int(item.get("rank") or 0) == rank), None)
        if not recommendation:
            raise ValueError("recommendation rank not found")
        return recommendation

    def _build_preview(
        self,
        run: AccountOperationRun,
        recommendation: dict[str, Any],
        opportunity: ContentOpportunity,
        request: OperationExperimentRequest | None,
    ) -> dict[str, Any]:
        target_metric = request.target_metric if request else "collect"
        experiment_name = (
            request.experiment_name.strip()
            if request and request.experiment_name and request.experiment_name.strip()
            else recommendation.get("title") or opportunity.opportunity_title
        )
        target_values = self._target_values(target_metric)
        notes = request.notes.strip() if request and request.notes else None
        return {
            "experiment_name": experiment_name,
            "analysis_report_id": run.report_id,
            "content_opportunity_id": opportunity.id,
            "selected_topic": opportunity.opportunity_title,
            "topic_angle": opportunity.suggested_angle,
            "target_audience": opportunity.target_audience,
            "content_pillar": opportunity.content_pillar,
            "comment_demand_type": opportunity.comment_demand_type,
            "hypothesis": self._hypothesis(opportunity, target_metric),
            "target_metric": target_metric,
            "expected_result": self._expected_result(target_values),
            "target_values": target_values,
            "risk_level": opportunity.risk_level,
            "opportunity_score": opportunity.opportunity_score,
            "evidence_summary": opportunity.evidence_summary,
            "source_type": "OPERATION_RUN_RECOMMENDATION",
            "notes": notes,
        }

    def _build_confirmation(self, recommendation: dict[str, Any], preview: dict[str, Any]) -> dict[str, Any]:
        return {
            "requires_confirmation": True,
            "title": recommendation.get("title") or preview["selected_topic"],
            "reason": recommendation.get("reason"),
            "evidence": recommendation.get("evidence") or preview["evidence_summary"],
            "opportunity_id": preview["content_opportunity_id"],
            "risk_level": recommendation.get("risk_level") or preview["risk_level"],
            "confidence": recommendation.get("confidence"),
            "experiment_name": preview["experiment_name"],
            "target_metric": preview["target_metric"],
            "message": "这是本地创建内容实验，不会发布到小红书，不会生成草稿，不会调用 LLM。",
        }

    def _bind_opportunity(self, experiment: ContentExperiment, opportunity_id: int) -> ContentExperiment:
        experiment.content_opportunity_id = opportunity_id
        self.db.commit()
        self.db.refresh(experiment)
        return experiment

    def _hypothesis(self, opportunity: ContentOpportunity, target_metric: str) -> str:
        return (
            f"如果围绕「{opportunity.opportunity_title}」进行内容实验，"
            f"并采用「{opportunity.suggested_angle}」角度，预计能提升 {target_metric} 等目标指标。"
        )

    def _target_values(self, target_metric: str) -> dict[str, int]:
        key_by_metric = {
            "like": "like_count",
            "collect": "collect_count",
            "comment": "comment_count",
            "lead": "lead_count",
            "order": "order_count",
            "engagement": "engagement_count",
        }
        return {key_by_metric.get(target_metric, "collect_count"): 100}

    def _expected_result(self, target_values: dict[str, int]) -> str:
        return " / ".join(f"{key} >= {value}" for key, value in target_values.items())
