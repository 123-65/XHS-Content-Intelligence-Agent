from collections import Counter
from decimal import Decimal

from sqlalchemy.orm import Session

from app.enums.post_publish import OptimizationPlanType, ReviewResultStatus, StrategyMemoryType
from app.models.content_optimization_plan import ContentOptimizationPlan
from app.models.review_report import ReviewReport
from app.repositories.post_publish_repo import PostPublishRepository
from app.schemas.post_publish import (
    CollectMetricsRequest,
    ContentOptimizationPlanResponse,
    MemoryExtractionResponse,
    OptimizationGenerateRequest,
    PrivateConversionSnapshotCreate,
    PrivateConversionSnapshotResponse,
    PublicMetricSnapshotCreate,
    PublicMetricSnapshotResponse,
    PublishedNoteCreate,
    PublishedNoteResponse,
    ReviewCreate,
    ReviewReportV2Response,
    StrategyMemoryResponse,
)


METRIC_FIELD_BY_NAME = {
    "view": "view_count",
    "views": "view_count",
    "like": "like_count",
    "likes": "like_count",
    "collect": "collect_count",
    "comment": "comment_count",
    "share": "share_count",
    "follow": "follow_count",
    "profile_visit": "profile_visit_count",
    "lead": "lead_count",
    "dm": "dm_count",
    "wechat_add": "wechat_add_count",
    "deal": "deal_count",
    "engagement": "engagement_count",
}


class PostPublishService:
    """编排发布后指标、复盘、策略记忆和下一轮优化。"""

    def __init__(self, db: Session):
        """初始化发布后业务服务。"""
        self.repo = PostPublishRepository(db)

    def create_published_note(self, data: PublishedNoteCreate) -> PublishedNoteResponse:
        """在用户提交发布链接后创建已发布笔记。"""
        self._ensure_account(data.account_id)
        experiment = self._ensure_experiment(data.experiment_id)
        draft = self._ensure_draft(data.draft_id)
        if draft.experiment_id != experiment.id:
            raise ValueError("Draft does not belong to the experiment")
        note = self.repo.create_published_note(data.model_dump())
        self.repo.update_status(experiment, "PUBLISHED")
        self.repo.update_status(draft, "PUBLISHED")
        return PublishedNoteResponse.model_validate(note)

    def list_public_metrics(self, published_note_id: int) -> list[PublicMetricSnapshotResponse]:
        """查询已发布笔记的公开指标快照。"""
        self._ensure_published_note(published_note_id)
        return [PublicMetricSnapshotResponse.model_validate(item) for item in self.repo.list_public_metrics(published_note_id)]

    def collect_public_metrics(self, published_note_id: int, data: CollectMetricsRequest) -> PublicMetricSnapshotResponse:
        """使用手动数据或确定性 Mock 数据回采公开指标。"""
        self._ensure_published_note(published_note_id)
        metrics = self._mock_metrics(data.snapshot_window.value) if data.use_mock else data.metrics
        if metrics is None:
            raise ValueError("metrics is required when use_mock is false")
        snapshot_data = metrics.model_dump()
        snapshot_data["published_note_id"] = published_note_id
        if data.use_mock:
            snapshot_data["source_type"] = "MOCK"
            snapshot_data["raw_snapshot"] = {"provider": "MockPublicMetricProvider", "snapshot_window": data.snapshot_window.value}
            snapshot_data["confidence"] = Decimal("0.8000")
        snapshot = self.repo.create_public_metric_snapshot(snapshot_data)
        return PublicMetricSnapshotResponse.model_validate(snapshot)

    def create_private_conversion_snapshot(self, data: PrivateConversionSnapshotCreate) -> PrivateConversionSnapshotResponse:
        """保存人工录入的私域转化指标。"""
        published_note = self._ensure_published_note(data.published_note_id)
        account_id = data.account_id or published_note.account_id
        if account_id != published_note.account_id:
            raise ValueError("Private conversion snapshot account_id does not match published note")
        payload = data.model_dump()
        payload["account_id"] = account_id
        snapshot = self.repo.create_private_conversion_snapshot(payload)
        return PrivateConversionSnapshotResponse.model_validate(snapshot)

    def create_review(self, data: ReviewCreate) -> ReviewReportV2Response:
        """创建发布后复盘报告。"""
        note = self._ensure_published_note(data.published_note_id)
        experiment = self._ensure_experiment(note.experiment_id)
        metrics = self.repo.list_public_metrics(note.id)
        conversions = self.repo.list_private_conversions(note.id)
        comments = self.repo.list_note_comments(note.id)

        public_summary = self._public_summary(metrics)
        private_summary = self._private_summary(conversions)
        comment_summary = self._comment_summary(comments)
        result_status = self._result_status(experiment, public_summary, private_summary, comment_summary)
        facts = self._data_facts(note, experiment, public_summary, private_summary, comment_summary)
        inferences = self._inferences(result_status, experiment, public_summary, private_summary, comment_summary)
        action_suggestions = self._action_suggestions(result_status, experiment, public_summary, private_summary)
        report = self.repo.create_review_report(
            {
                "draft_id": note.draft_id,
                "account_id": note.account_id,
                "experiment_id": note.experiment_id,
                "published_note_id": note.id,
                "review_type": "POST_PUBLISH_REVIEW",
                "result_status": result_status.value,
                "passed": result_status in {ReviewResultStatus.SUCCESS, ReviewResultStatus.PARTIAL_SUCCESS, ReviewResultStatus.RISKY_SUCCESS},
                "score": self._review_score(result_status, public_summary, private_summary),
                "quality_score": 0,
                "conversion_score": self._conversion_score(private_summary),
                "evidence_usage_score": 100 if facts else 0,
                "risk_level": "HIGH" if result_status == ReviewResultStatus.RISKY_SUCCESS else "LOW",
                "issues": self._review_issues(result_status, comment_summary),
                "suggestions": [item["text"] for item in action_suggestions],
                "public_metrics_summary": public_summary,
                "private_conversion_summary": private_summary,
                "comment_summary": comment_summary,
                "data_facts": facts,
                "inferences": inferences,
                "action_suggestions": action_suggestions,
                "summary": self._review_summary(result_status, public_summary, private_summary),
                "status": "SUCCESS",
            }
        )
        self.repo.update_status(experiment, "ANALYZED")
        return ReviewReportV2Response.model_validate(report)

    def get_review(self, review_report_id: int) -> ReviewReportV2Response:
        """查询发布后复盘报告。"""
        report = self._ensure_review_report(review_report_id)
        return ReviewReportV2Response.model_validate(report)

    def extract_memories(self, review_report_id: int) -> MemoryExtractionResponse:
        """从复盘报告中提取候选策略记忆。"""
        report = self._ensure_review_report(review_report_id)
        specs = self._memory_specs(report)
        memories = [self.repo.create_strategy_memory(memory, evidence) for memory, evidence in specs]
        return MemoryExtractionResponse(
            review_report_id=review_report_id,
            count=len(memories),
            memories=[StrategyMemoryResponse.model_validate(item) for item in memories],
        )

    def list_memories(self, account_id: int) -> list[StrategyMemoryResponse]:
        """查询账号策略记忆列表。"""
        self._ensure_account(account_id)
        return [StrategyMemoryResponse.model_validate(item) for item in self.repo.list_memories(account_id)]

    def generate_optimization(self, data: OptimizationGenerateRequest) -> ContentOptimizationPlanResponse:
        """生成下一轮内容优化计划。"""
        self._ensure_account(data.account_id)
        report = self._resolve_review_for_optimization(data.account_id, data.review_report_id)
        plan_type = data.plan_type or self._plan_type(report)
        plan = self.repo.create_optimization_plan(
            {
                "account_id": data.account_id,
                "source_review_report_id": report.id,
                "plan_type": plan_type.value,
                "status": "CANDIDATE",
                "summary": self._plan_summary(plan_type, report),
                "rationale": self._plan_rationale(plan_type, report),
                "actions": self._plan_actions(plan_type, report),
            }
        )
        return ContentOptimizationPlanResponse.model_validate(plan)

    def apply_optimization(self, optimization_plan_id: int) -> ContentOptimizationPlanResponse:
        """应用优化计划并按需创建下一轮候选实验。"""
        plan = self.repo.db.get(ContentOptimizationPlan, optimization_plan_id)
        if not plan:
            raise ValueError("Content optimization plan does not exist")
        if plan.status == "APPLIED":
            return ContentOptimizationPlanResponse.model_validate(plan)
        generated_id = None if plan.plan_type == OptimizationPlanType.PAUSE.value else self._create_next_experiment(plan)
        applied = self.repo.update_plan_applied(plan, generated_id)
        return ContentOptimizationPlanResponse.model_validate(applied)

    def _mock_metrics(self, snapshot_window: str) -> PublicMetricSnapshotCreate:
        """按指标窗口生成确定性的 Mock 公开指标。"""
        multiplier = {"24h": 1, "48h": 2, "72h": 3, "7d": 5}[snapshot_window]
        return PublicMetricSnapshotCreate(
            snapshot_window=snapshot_window,
            view_count=500 * multiplier,
            like_count=45 * multiplier,
            collect_count=35 * multiplier,
            comment_count=8 * multiplier,
            share_count=3 * multiplier,
            follow_count=4 * multiplier,
            profile_visit_count=18 * multiplier,
        )

    def _public_summary(self, metrics) -> dict:
        """基于最新快照汇总公开指标。"""
        latest = metrics[0] if metrics else None
        if not latest:
            return {"has_metrics": False}
        engagement_count = latest.like_count + latest.collect_count + latest.comment_count + latest.share_count
        return {
            "has_metrics": True,
            "snapshot_window": latest.snapshot_window,
            "view_count": latest.view_count,
            "like_count": latest.like_count,
            "collect_count": latest.collect_count,
            "comment_count": latest.comment_count,
            "share_count": latest.share_count,
            "follow_count": latest.follow_count,
            "profile_visit_count": latest.profile_visit_count,
            "engagement_count": engagement_count,
            "collect_rate": self._rate(latest.collect_count, latest.view_count),
        }

    def _private_summary(self, conversions) -> dict:
        """基于最新快照汇总私域转化指标。"""
        latest = conversions[0] if conversions else None
        if not latest:
            return {"has_conversions": False}
        return {
            "has_conversions": True,
            "dm_count": latest.dm_count,
            "lead_count": latest.lead_count,
            "wechat_add_count": latest.wechat_add_count,
            "group_join_count": latest.group_join_count,
            "consultation_count": latest.consultation_count,
            "price_inquiry_count": latest.price_inquiry_count,
            "resource_request_count": latest.resource_request_count,
            "deal_count": latest.deal_count,
            "revenue_amount": str(latest.revenue_amount),
        }

    def _comment_summary(self, comments) -> dict:
        """汇总评论需求快照。"""
        counts = Counter(comment.demand_type for comment in comments)
        return {"total_comments": len(comments), "demand_counts": dict(counts), "marketing_resistance_count": counts.get("MARKETING_RESISTANCE", 0)}

    def _result_status(self, experiment, public_summary: dict, private_summary: dict, comment_summary: dict) -> ReviewResultStatus:
        """根据指标目标、私域转化和风险信号判断实验结果。"""
        if not public_summary.get("has_metrics"):
            return ReviewResultStatus.INCONCLUSIVE
        actual_value = self._actual_metric_value(experiment.primary_metric, public_summary, private_summary)
        target_value = self._target_value(experiment)
        if target_value <= 0:
            return ReviewResultStatus.INCONCLUSIVE
        if actual_value >= target_value and comment_summary.get("marketing_resistance_count", 0) > 0:
            return ReviewResultStatus.RISKY_SUCCESS
        if actual_value >= target_value:
            return ReviewResultStatus.SUCCESS
        if actual_value >= target_value * Decimal("0.6"):
            return ReviewResultStatus.PARTIAL_SUCCESS
        return ReviewResultStatus.FAILED

    def _data_facts(self, note, experiment, public_summary: dict, private_summary: dict, comment_summary: dict) -> list[dict]:
        """构造独立于推断和建议的数据事实。"""
        return [
            {"type": "FACT", "text": f"Published note URL: {note.publish_url}", "payload": {"published_note_id": note.id}},
            {"type": "FACT", "text": f"Experiment primary metric: {experiment.primary_metric}", "payload": {"experiment_id": experiment.id}},
            {"type": "FACT", "text": "Latest public metrics snapshot", "payload": public_summary},
            {"type": "FACT", "text": "Latest private conversion snapshot", "payload": private_summary},
            {"type": "FACT", "text": "Collected comment demand summary", "payload": comment_summary},
        ]

    def _inferences(self, result_status: ReviewResultStatus, experiment, public_summary: dict, private_summary: dict, comment_summary: dict) -> list[dict]:
        """基于数据事实构造推断记录。"""
        return [
            {"type": "INFERENCE", "text": f"Experiment result is {result_status.value}", "payload": {"result_status": result_status.value}},
            {"type": "INFERENCE", "text": "Content hypothesis has usable signal, but needs repeated validation.", "payload": {"one_success_only_candidate": True}},
        ]

    def _action_suggestions(self, result_status: ReviewResultStatus, experiment, public_summary: dict, private_summary: dict) -> list[dict]:
        """根据复盘结果构造行动建议。"""
        suggestions = {
            ReviewResultStatus.SUCCESS: ("Scale this angle with a controlled variation.", OptimizationPlanType.SCALE),
            ReviewResultStatus.PARTIAL_SUCCESS: ("Repair the weak variable and rerun the experiment.", OptimizationPlanType.REPAIR),
            ReviewResultStatus.FAILED: ("Explore a different topic angle or audience cut.", OptimizationPlanType.EXPLORE),
            ReviewResultStatus.INCONCLUSIVE: ("Refresh metric snapshots before making a strategic call.", OptimizationPlanType.REFRESH),
            ReviewResultStatus.RISKY_SUCCESS: ("Pause scaling and reduce risky conversion wording.", OptimizationPlanType.PAUSE),
        }
        text, plan_type = suggestions[result_status]
        return [{"type": "SUGGESTION", "text": text, "payload": {"recommended_plan_type": plan_type.value}}]

    def _memory_specs(self, report: ReviewReport) -> list[tuple[dict, list[dict]]]:
        """从复盘报告构造候选策略记忆规格。"""
        result = ReviewResultStatus(report.result_status or "INCONCLUSIVE")
        memory_type = {
            ReviewResultStatus.SUCCESS: StrategyMemoryType.TOPIC_MEMORY,
            ReviewResultStatus.PARTIAL_SUCCESS: StrategyMemoryType.STRUCTURE_MEMORY,
            ReviewResultStatus.FAILED: StrategyMemoryType.NEGATIVE_MEMORY,
            ReviewResultStatus.INCONCLUSIVE: StrategyMemoryType.AUDIENCE_MEMORY,
            ReviewResultStatus.RISKY_SUCCESS: StrategyMemoryType.RISK_MEMORY,
        }[result]
        evidence = [
            {"review_report_id": report.id, "evidence_type": "FACT", "evidence_text": item["text"], "evidence_payload": item}
            for item in report.data_facts[:2]
        ] + [
            {"review_report_id": report.id, "evidence_type": "INFERENCE", "evidence_text": item["text"], "evidence_payload": item}
            for item in report.inferences[:1]
        ] + [
            {"review_report_id": report.id, "evidence_type": "SUGGESTION", "evidence_text": item["text"], "evidence_payload": item}
            for item in report.action_suggestions[:1]
        ]
        memory = {
            "account_id": report.account_id,
            "memory_type": memory_type.value,
            "status": "CANDIDATE",
            "summary": f"{memory_type.value} from review {report.id}: {report.result_status}",
            "pattern": self._memory_pattern(memory_type, report),
            "confidence": Decimal("0.6000") if result != ReviewResultStatus.INCONCLUSIVE else Decimal("0.3000"),
            "source_review_report_id": report.id,
            "support_count": 1,
            "risk_level": report.risk_level,
            "metadata_payload": {"result_status": report.result_status, "one_success_only_candidate": True},
        }
        return [(memory, evidence)]

    def _resolve_review_for_optimization(self, account_id: int, review_report_id: int | None) -> ReviewReport:
        """解析用于生成优化计划的来源复盘报告。"""
        if review_report_id:
            report = self._ensure_review_report(review_report_id)
            if report.account_id != account_id:
                raise ValueError("Review report account_id does not match")
            return report
        reports = self.repo.list_recent_reviews(account_id, 1)
        if not reports:
            raise ValueError("No post-publish review report is available")
        return reports[0]

    def _plan_type(self, report: ReviewReport) -> OptimizationPlanType:
        """根据复盘结果选择优化计划类型。"""
        return {
            "SUCCESS": OptimizationPlanType.SCALE,
            "PARTIAL_SUCCESS": OptimizationPlanType.REPAIR,
            "FAILED": OptimizationPlanType.EXPLORE,
            "INCONCLUSIVE": OptimizationPlanType.REFRESH,
            "RISKY_SUCCESS": OptimizationPlanType.PAUSE,
        }.get(report.result_status or "INCONCLUSIVE", OptimizationPlanType.REFRESH)

    def _create_next_experiment(self, plan) -> int:
        """根据优化计划创建候选实验。"""
        report = self._ensure_review_report(plan.source_review_report_id)
        source_experiment = self._ensure_experiment(report.experiment_id)
        fields = {
            "account_id": plan.account_id,
            "analysis_report_id": source_experiment.analysis_report_id,
            "content_opportunity_id": source_experiment.content_opportunity_id,
            "experiment_name": f"{plan.plan_type} follow-up: {source_experiment.experiment_name}",
            "hypothesis": f"Based on review {report.id}, apply {plan.plan_type} adjustment and observe {source_experiment.primary_metric}.",
            "content_pillar": source_experiment.content_pillar,
            "content_format": source_experiment.content_format,
            "main_variable": plan.actions[0]["variable"] if plan.actions else source_experiment.main_variable,
            "control_variables": source_experiment.control_variables,
            "primary_metric": source_experiment.primary_metric,
            "secondary_metrics": source_experiment.secondary_metrics,
            "success_criteria": source_experiment.success_criteria,
            "failure_criteria": source_experiment.failure_criteria,
            "fallback_strategy": "If this follow-up underperforms, pause the direction and return to opportunity analysis.",
            "risk_level": "LOW" if plan.plan_type != "CONVERT" else "MEDIUM",
            "target_metric": source_experiment.target_metric,
            "expected_result": source_experiment.expected_result,
            "topic_angle": source_experiment.topic_angle,
            "selected_topic": plan.summary,
            "target_values": source_experiment.target_values,
            "source_type": "OPTIMIZATION_PLAN",
            "status": "CANDIDATE",
        }
        return self.repo.create_experiment(fields).id

    def _plan_summary(self, plan_type: OptimizationPlanType, report: ReviewReport) -> str:
        """构造优化计划摘要。"""
        return f"{plan_type.value} plan for review {report.id}: {report.result_status}"

    def _plan_rationale(self, plan_type: OptimizationPlanType, report: ReviewReport) -> str:
        """构造优化计划依据。"""
        return f"Generated from facts={len(report.data_facts)}, inferences={len(report.inferences)}, suggestions={len(report.action_suggestions)}."

    def _plan_actions(self, plan_type: OptimizationPlanType, report: ReviewReport) -> list[dict]:
        """构造优化计划动作。"""
        action_by_type = {
            OptimizationPlanType.SCALE: {"variable": "topic_angle", "action": "keep core angle and test a stronger evidence opening"},
            OptimizationPlanType.REPAIR: {"variable": "content_structure", "action": "repair weak section and keep the same audience"},
            OptimizationPlanType.EXPLORE: {"variable": "audience_cut", "action": "test a different audience pain point"},
            OptimizationPlanType.CONVERT: {"variable": "cta_text", "action": "use a softer conversion bridge"},
            OptimizationPlanType.PAUSE: {"variable": "risk_control", "action": "pause publishing follow-ups until risk wording is repaired"},
            OptimizationPlanType.REFRESH: {"variable": "metric_snapshot", "action": "collect the next metric window before changing strategy"},
        }
        return [{**action_by_type[plan_type], "source_review_report_id": report.id}]

    def _actual_metric_value(self, primary_metric: str, public_summary: dict, private_summary: dict) -> Decimal:
        """从公开和私域汇总中解析实际指标值。"""
        if primary_metric == "engagement":
            return Decimal(str(public_summary.get("engagement_count", 0)))
        field = METRIC_FIELD_BY_NAME.get(primary_metric, f"{primary_metric}_count")
        return Decimal(str(public_summary.get(field, private_summary.get(field, 0))))

    def _target_value(self, experiment) -> Decimal:
        """从实验目标配置中解析目标指标值。"""
        target_values = experiment.target_values or {}
        if not target_values:
            return Decimal("0")
        if experiment.primary_metric == "engagement" and "engagement_count" in target_values:
            return Decimal(str(target_values["engagement_count"]))
        field = METRIC_FIELD_BY_NAME.get(experiment.primary_metric, f"{experiment.primary_metric}_count")
        return Decimal(str(target_values.get(field, next(iter(target_values.values()), 0))))

    def _review_score(self, result_status: ReviewResultStatus, public_summary: dict, private_summary: dict) -> int:
        """为发布后复盘结果打分。"""
        return {
            ReviewResultStatus.SUCCESS: 88,
            ReviewResultStatus.PARTIAL_SUCCESS: 72,
            ReviewResultStatus.FAILED: 45,
            ReviewResultStatus.INCONCLUSIVE: 50,
            ReviewResultStatus.RISKY_SUCCESS: 65,
        }[result_status]

    def _conversion_score(self, private_summary: dict) -> int:
        """为私域转化信号强度打分。"""
        return min(100, int(private_summary.get("lead_count", 0)) * 10 + int(private_summary.get("deal_count", 0)) * 25)

    def _review_issues(self, result_status: ReviewResultStatus, comment_summary: dict) -> list[dict]:
        """构造复盘问题列表。"""
        issue_by_status = {
            ReviewResultStatus.FAILED: [{"field": "primary_metric", "level": "MEDIUM", "message": "Primary metric missed the failure threshold."}],
            ReviewResultStatus.INCONCLUSIVE: [{"field": "metrics", "level": "LOW", "message": "Not enough metric snapshots to judge the experiment."}],
            ReviewResultStatus.RISKY_SUCCESS: [{"field": "risk", "level": "HIGH", "message": "Metric target was met but marketing resistance appeared."}],
        }
        return issue_by_status.get(result_status, [])

    def _review_summary(self, result_status: ReviewResultStatus, public_summary: dict, private_summary: dict) -> str:
        """构造复盘摘要。"""
        return f"Post-publish review result is {result_status.value}. Public={public_summary}. Private={private_summary}."

    def _memory_pattern(self, memory_type: StrategyMemoryType, report: ReviewReport) -> str:
        """构造可复用的策略模式描述。"""
        return f"Use {memory_type.value} cautiously; this is candidate memory from a single review, not validated strategy."

    def _rate(self, numerator: int, denominator: int) -> float:
        """计算保留四位小数的比例。"""
        return round(numerator / denominator, 4) if denominator else 0

    def _ensure_account(self, account_id: int):
        """返回账号画像，不存在时抛出业务错误。"""
        account = self.repo.get_account(account_id)
        if not account:
            raise ValueError("Account profile does not exist")
        return account

    def _ensure_experiment(self, experiment_id: int | None):
        """返回内容实验，不存在时抛出业务错误。"""
        if experiment_id is None:
            raise ValueError("Content experiment does not exist")
        experiment = self.repo.get_experiment(experiment_id)
        if not experiment:
            raise ValueError("Content experiment does not exist")
        return experiment

    def _ensure_draft(self, draft_id: int):
        """返回内容草稿，不存在时抛出业务错误。"""
        draft = self.repo.get_draft(draft_id)
        if not draft:
            raise ValueError("Content draft does not exist")
        return draft

    def _ensure_published_note(self, published_note_id: int):
        """返回已发布笔记，不存在时抛出业务错误。"""
        note = self.repo.get_published_note(published_note_id)
        if not note:
            raise ValueError("Published note does not exist")
        return note

    def _ensure_review_report(self, review_report_id: int) -> ReviewReport:
        """返回复盘报告，不存在时抛出业务错误。"""
        report = self.repo.get_review_report(review_report_id)
        if not report:
            raise ValueError("Review report does not exist")
        return report
