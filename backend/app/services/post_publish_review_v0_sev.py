from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.content_draft import ContentDraft
from app.models.content_experiment import ContentExperiment
from app.models.private_conversion_snapshot import PrivateConversionSnapshot
from app.models.public_metric_snapshot import PublicMetricSnapshot
from app.models.publish_package import PublishPackage
from app.models.published_note import PublishedNote
from app.models.review_report import ReviewReport
from app.schemas.post_publish_review_v0 import (
    PostPublishAction,
    PostPublishReviewV0Request,
    PostPublishReviewV0Response,
    StrategyMemoryCandidate,
)


TARGET_FIELD_BY_METRIC = {
    "like": "like_count",
    "likes": "like_count",
    "collect": "collect_count",
    "collection": "collect_count",
    "comment": "comment_count",
    "comments": "comment_count",
    "share": "share_count",
    "shares": "share_count",
    "follow": "follower_gain",
    "follower": "follower_gain",
    "lead": "lead_count",
    "leads": "lead_count",
    "engagement": "engagement_count",
}


class PostPublishReviewV0NotFound(ValueError):
    """Resource needed for B14 post-publish review was not found."""


class PostPublishReviewV0Service:
    """Create factual post-publish reviews without LLM, scraping, or memory writes."""

    def __init__(self, db: Session):
        self.db = db

    def create_review(self, published_note_id: int, request: PostPublishReviewV0Request) -> PostPublishReviewV0Response:
        if not request.confirmed:
            return PostPublishReviewV0Response(
                status="WAITING_CONFIRMATION",
                account_id=request.account_id,
                published_note_id=published_note_id,
                confirmation={
                    "requires_confirmation": True,
                    "confirmed": False,
                    "message": "Confirm to generate a local factual review. This will not access XHS or write memory.",
                },
            )

        note = self._get_note_or_raise(published_note_id)
        if note.account_id != request.account_id:
            raise ValueError("published_note account_id does not match")

        public_metric = self._latest_public_metric(published_note_id)
        if not public_metric:
            return PostPublishReviewV0Response(
                status="DATA_INSUFFICIENT",
                account_id=request.account_id,
                published_note_id=published_note_id,
                package_id=self._package_id(note),
                error_code="NO_METRIC_SNAPSHOT",
                error_message="No public metric snapshot is available for this published note.",
                data_gaps=[
                    {"type": "NO_PUBLIC_METRIC_SNAPSHOT", "message": "Add manual metrics before running post-publish review."}
                ],
            )
        if public_metric.source_type == "MOCK":
            return PostPublishReviewV0Response(
                status="DATA_INSUFFICIENT",
                account_id=request.account_id,
                published_note_id=published_note_id,
                package_id=self._package_id(note),
                error_code="MOCK_METRIC_SOURCE",
                error_message="Mock metrics cannot be used for post-publish review.",
                data_gaps=[
                    {
                        "type": "MOCK_METRIC_SOURCE",
                        "message": "Add manual metrics before running post-publish review.",
                    }
                ],
            )

        private_conversion = self._latest_private_conversion(published_note_id)
        draft = self._get_draft(note.draft_id)
        experiment = self._get_experiment(note.experiment_id)
        package = self._get_package(self._package_id(note))
        metric_summary = self._metric_summary(public_metric)
        conversion_summary = self._conversion_summary(private_conversion, metric_summary)
        target_comparison = self._target_comparison(experiment, metric_summary, conversion_summary)
        data_gaps = self._data_gaps(public_metric, private_conversion, metric_summary, target_comparison)
        insights = self._insights(metric_summary, target_comparison, conversion_summary)
        next_actions = self._next_actions(target_comparison, metric_summary, data_gaps)
        candidates = self._strategy_memory_candidates(target_comparison, metric_summary, conversion_summary)
        summary = self._summary(target_comparison, metric_summary, conversion_summary, data_gaps)

        stored_metric_summary = {**metric_summary, "target_comparison": target_comparison}
        report = ReviewReport(
            draft_id=note.draft_id,
            account_id=note.account_id,
            experiment_id=note.experiment_id,
            published_note_id=note.id,
            review_type="POST_PUBLISH_REVIEW_V0",
            result_status=target_comparison.get("result", "UNKNOWN_TARGET"),
            passed=target_comparison.get("result") == "HIT_TARGET",
            score=self._score(target_comparison, metric_summary, conversion_summary),
            quality_score=0,
            conversion_score=min(100, int(conversion_summary.get("lead_count", 0)) * 10),
            evidence_usage_score=100,
            risk_level="LOW",
            issues=self._issues(target_comparison, data_gaps),
            suggestions=[item.label for item in next_actions],
            public_metrics_summary=stored_metric_summary,
            private_conversion_summary=conversion_summary,
            comment_summary={
                "comment_count": metric_summary.get("comment_count", 0),
                "has_comment_detail": False,
            },
            data_facts=self._data_facts(note, package, draft, experiment, public_metric, private_conversion),
            inferences=[
                {"type": "INFERENCE", "text": item, "payload": {"source": "post_publish_review_v0"}}
                for item in insights
            ],
            action_suggestions=[item.model_dump() for item in next_actions],
            summary=summary,
            status="SUCCESS",
        )
        self.db.add(report)
        self.db.commit()
        self.db.refresh(report)
        return self._response_from_report(report, candidates)

    def list_by_published_note(self, published_note_id: int) -> list[PostPublishReviewV0Response]:
        if not self.db.get(PublishedNote, published_note_id):
            raise PostPublishReviewV0NotFound("published note not found")
        stmt = (
            select(ReviewReport)
            .where(ReviewReport.published_note_id == published_note_id, ReviewReport.review_type == "POST_PUBLISH_REVIEW_V0")
            .order_by(ReviewReport.id.desc())
        )
        return [self._response_from_report(item) for item in self.db.execute(stmt).scalars().all()]

    def get_review(self, review_id: int) -> PostPublishReviewV0Response:
        report = self.db.get(ReviewReport, review_id)
        if not report or report.review_type != "POST_PUBLISH_REVIEW_V0":
            raise PostPublishReviewV0NotFound("post publish review not found")
        return self._response_from_report(report)

    def _response_from_report(
        self,
        report: ReviewReport,
        candidates: list[StrategyMemoryCandidate] | None = None,
    ) -> PostPublishReviewV0Response:
        return PostPublishReviewV0Response(
            status="REVIEWED",
            review_id=report.id,
            account_id=report.account_id or 0,
            published_note_id=report.published_note_id or 0,
            package_id=self._package_id(self.db.get(PublishedNote, report.published_note_id)) if report.published_note_id else None,
            summary=report.summary or "",
            metric_summary=report.public_metrics_summary or {},
            target_comparison=(report.public_metrics_summary or {}).get("target_comparison")
            or self._target_from_report_status(report),
            conversion_summary=report.private_conversion_summary or {},
            insights=[item.get("text", "") for item in report.inferences or [] if item.get("text")],
            data_gaps=[item for item in report.issues or [] if item.get("type", "").startswith("NO_") or item.get("category") == "DATA_GAP"],
            next_actions=[PostPublishAction.model_validate(item) for item in report.action_suggestions or []],
            strategy_memory_candidates=candidates or self._candidates_from_report(report),
            created_at=report.created_at,
        )

    def _metric_summary(self, metric: PublicMetricSnapshot) -> dict:
        engagement_count = metric.like_count + metric.collect_count + metric.comment_count + metric.share_count
        return {
            "snapshot_id": metric.id,
            "snapshot_window": metric.snapshot_window,
            "source_type": metric.source_type,
            "view_count": metric.view_count,
            "like_count": metric.like_count,
            "collect_count": metric.collect_count,
            "comment_count": metric.comment_count,
            "share_count": metric.share_count,
            "follower_gain": metric.follow_count,
            "engagement_count": engagement_count,
            "collect_like_ratio": self._rate(metric.collect_count, max(metric.like_count, 1)),
            "comment_like_ratio": self._rate(metric.comment_count, max(metric.like_count, 1)),
        }

    def _conversion_summary(self, conversion: PrivateConversionSnapshot | None, metric_summary: dict) -> dict:
        lead_count = conversion.lead_count if conversion else 0
        follower_gain = metric_summary.get("follower_gain", 0)
        engagement_count = metric_summary.get("engagement_count", 0)
        return {
            "snapshot_id": conversion.id if conversion else None,
            "source_type": conversion.source_type if conversion else "MANUAL",
            "lead_count": lead_count,
            "follower_gain": follower_gain,
            "lead_rate": self._rate(lead_count, max(engagement_count, 1)),
        }

    def _target_comparison(self, experiment: ContentExperiment | None, metric_summary: dict, conversion_summary: dict) -> dict:
        if not experiment:
            return {"target_metric": None, "target_value": None, "actual_value": None, "result": "UNKNOWN_TARGET"}
        target_metric = experiment.target_metric or experiment.primary_metric
        target_values = experiment.target_values or {}
        if not target_metric or not target_values:
            return {
                "target_metric": target_metric,
                "target_value": None,
                "actual_value": self._actual_value(target_metric, metric_summary, conversion_summary),
                "result": "UNKNOWN_TARGET",
            }
        field = TARGET_FIELD_BY_METRIC.get(str(target_metric).lower(), f"{target_metric}_count")
        target_value = target_values.get(field)
        if target_value is None and target_values:
            target_value = target_values.get(str(target_metric)) or target_values.get("value")
        actual_value = self._actual_value(target_metric, metric_summary, conversion_summary)
        if target_value is None:
            return {
                "target_metric": target_metric,
                "target_value": None,
                "actual_value": actual_value,
                "result": "UNKNOWN_TARGET",
            }
        if metric_summary.get("engagement_count", 0) == 0:
            return {
                "target_metric": target_metric,
                "target_value": target_value,
                "actual_value": actual_value,
                "result": "UNKNOWN_TARGET",
            }
        return {
            "target_metric": target_metric,
            "target_value": target_value,
            "actual_value": actual_value,
            "result": "HIT_TARGET" if Decimal(str(actual_value)) >= Decimal(str(target_value)) else "MISS_TARGET",
        }

    def _actual_value(self, target_metric: str | None, metric_summary: dict, conversion_summary: dict) -> int | float:
        key = TARGET_FIELD_BY_METRIC.get(str(target_metric or "").lower(), f"{target_metric}_count")
        if key in conversion_summary:
            return conversion_summary[key]
        return metric_summary.get(key, 0)

    def _data_gaps(
        self,
        metric: PublicMetricSnapshot,
        conversion: PrivateConversionSnapshot | None,
        metric_summary: dict,
        target_comparison: dict,
    ) -> list[dict]:
        gaps: list[dict] = [
            {
                "type": "NO_COMMENT_DETAIL",
                "message": "Only comment count is available; comment content was not backfilled.",
            }
        ]
        if not conversion:
            gaps.append({"type": "NO_PRIVATE_CONVERSION_SNAPSHOT", "message": "No private conversion snapshot is available."})
        if target_comparison.get("result") == "UNKNOWN_TARGET":
            gaps.append({"type": "UNKNOWN_TARGET", "message": "Target values are missing or not comparable."})
        if metric_summary.get("engagement_count", 0) == 0:
            gaps.append(
                {
                    "type": "ZERO_METRICS",
                    "message": "All engagement metrics are zero; confirm publish time and observation window before judging performance.",
                }
            )
        if metric.source_type == "MOCK":
            gaps.append({"type": "MOCK_METRIC_SOURCE", "message": "Metric source is MOCK and must not be treated as real review evidence."})
        return gaps

    def _insights(self, metric_summary: dict, target_comparison: dict, conversion_summary: dict) -> list[str]:
        insights = [
            f"Engagement count is {metric_summary.get('engagement_count', 0)} from manual metrics.",
            f"Collect-like ratio is {metric_summary.get('collect_like_ratio', 0)}.",
            f"Comment-like ratio is {metric_summary.get('comment_like_ratio', 0)}.",
            f"Lead count is {conversion_summary.get('lead_count', 0)} with lead rate {conversion_summary.get('lead_rate', 0)}.",
        ]
        result = target_comparison.get("result")
        if result == "HIT_TARGET":
            insights.append("The target metric was reached in the current manual snapshot.")
        elif result == "MISS_TARGET":
            insights.append("The target metric was not reached in the current manual snapshot.")
        else:
            insights.append("The target cannot be judged from current target settings or metrics.")
        return insights

    def _next_actions(self, target_comparison: dict, metric_summary: dict, data_gaps: list[dict]) -> list[PostPublishAction]:
        if any(gap["type"] == "ZERO_METRICS" for gap in data_gaps):
            return [
                PostPublishAction(action="WAIT_FOR_OBSERVATION_WINDOW", label="Confirm publish time and collect a later snapshot"),
                PostPublishAction(action="REFILL_METRICS", label="Backfill the next manual metrics snapshot"),
            ]
        if target_comparison.get("result") == "HIT_TARGET":
            return [
                PostPublishAction(action="CREATE_STRATEGY_MEMORY_CANDIDATE", label="Review strategy memory candidates in B15"),
                PostPublishAction(action="CONTINUE_TOPIC", label="Continue testing this direction"),
            ]
        if target_comparison.get("result") == "MISS_TARGET":
            return [
                PostPublishAction(action="ADJUST_TOPIC_OR_STRUCTURE", label="Adjust the next draft before scaling"),
                PostPublishAction(action="COLLECT_NEXT_SNAPSHOT", label="Backfill a later metric snapshot"),
            ]
        return [
            PostPublishAction(action="COLLECT_NEXT_SNAPSHOT", label="Backfill a later metric snapshot"),
            PostPublishAction(action="DEFINE_TARGET", label="Confirm target metric and target values"),
        ]

    def _strategy_memory_candidates(
        self,
        target_comparison: dict,
        metric_summary: dict,
        conversion_summary: dict,
    ) -> list[StrategyMemoryCandidate]:
        if target_comparison.get("result") != "HIT_TARGET":
            return []
        target_metric = target_comparison.get("target_metric") or "target"
        return [
            StrategyMemoryCandidate(
                type="CONTENT_DIRECTION",
                content="This topic direction has a positive manual post-publish signal and can be considered in B15.",
                evidence=f"{target_metric} actual={target_comparison.get('actual_value')}, target={target_comparison.get('target_value')}",
                confidence="MEDIUM" if metric_summary.get("engagement_count", 0) > 0 else "LOW",
            ),
            StrategyMemoryCandidate(
                type="CONVERSION_SIGNAL",
                content="Manual lead signal is available and can be reviewed as a candidate conversion memory in B15.",
                evidence=f"lead_count={conversion_summary.get('lead_count', 0)}, lead_rate={conversion_summary.get('lead_rate', 0)}",
                confidence="MEDIUM" if conversion_summary.get("lead_count", 0) > 0 else "LOW",
            ),
        ]

    def _summary(self, target_comparison: dict, metric_summary: dict, conversion_summary: dict, data_gaps: list[dict]) -> str:
        result = target_comparison.get("result", "UNKNOWN_TARGET")
        return (
            f"Post-publish review result is {result}. "
            f"Engagement={metric_summary.get('engagement_count', 0)}, "
            f"collects={metric_summary.get('collect_count', 0)}, comments={metric_summary.get('comment_count', 0)}, "
            f"leads={conversion_summary.get('lead_count', 0)}, data_gaps={len(data_gaps)}."
        )

    def _score(self, target_comparison: dict, metric_summary: dict, conversion_summary: dict) -> int:
        if metric_summary.get("engagement_count", 0) == 0:
            return 50
        if target_comparison.get("result") == "HIT_TARGET":
            return min(95, 80 + min(15, int(conversion_summary.get("lead_count", 0)) * 3))
        if target_comparison.get("result") == "MISS_TARGET":
            return 55
        return 60

    def _issues(self, target_comparison: dict, data_gaps: list[dict]) -> list[dict]:
        issues = [{"category": "DATA_GAP", **gap} for gap in data_gaps]
        if target_comparison.get("result") == "MISS_TARGET":
            issues.append({"category": "TARGET", "type": "MISS_TARGET", "message": "Target metric was not reached."})
        return issues

    def _data_facts(
        self,
        note: PublishedNote,
        package: PublishPackage | None,
        draft: ContentDraft | None,
        experiment: ContentExperiment | None,
        public_metric: PublicMetricSnapshot,
        private_conversion: PrivateConversionSnapshot | None,
    ) -> list[dict]:
        return [
            {"type": "FACT", "text": "Published note", "payload": {"published_note_id": note.id, "url": note.publish_url}},
            {"type": "FACT", "text": "Publish package", "payload": {"package_id": package.id if package else None}},
            {"type": "FACT", "text": "Content draft", "payload": {"draft_id": draft.id if draft else note.draft_id}},
            {"type": "FACT", "text": "Content experiment", "payload": {"experiment_id": experiment.id if experiment else note.experiment_id}},
            {"type": "FACT", "text": "Latest public metric snapshot", "payload": {"snapshot_id": public_metric.id}},
            {"type": "FACT", "text": "Latest private conversion snapshot", "payload": {"snapshot_id": private_conversion.id if private_conversion else None}},
        ]

    def _target_from_report_status(self, report: ReviewReport) -> dict:
        return {"result": report.result_status or "UNKNOWN_TARGET"}

    def _candidates_from_report(self, report: ReviewReport) -> list[StrategyMemoryCandidate]:
        if report.result_status != "HIT_TARGET":
            return []
        public_summary = report.public_metrics_summary or {}
        return [
            StrategyMemoryCandidate(
                type="CONTENT_DIRECTION",
                content="This reviewed note can be considered as a B15 strategy-memory candidate.",
                evidence=report.summary or f"review_id={report.id}",
                confidence="MEDIUM" if public_summary.get("engagement_count", 0) > 0 else "LOW",
            )
        ]

    def _rate(self, numerator: int, denominator: int) -> float:
        return round(numerator / denominator, 4) if denominator else 0

    def _package_id(self, note: PublishedNote | None) -> int | None:
        if not note:
            return None
        raw_snapshot = note.raw_snapshot or {}
        try:
            return int(raw_snapshot.get("publish_package_id")) if raw_snapshot.get("publish_package_id") is not None else None
        except (TypeError, ValueError):
            return None

    def _get_note_or_raise(self, published_note_id: int) -> PublishedNote:
        note = self.db.get(PublishedNote, published_note_id)
        if not note:
            raise PostPublishReviewV0NotFound("published note not found")
        return note

    def _latest_public_metric(self, published_note_id: int) -> PublicMetricSnapshot | None:
        stmt = (
            select(PublicMetricSnapshot)
            .where(PublicMetricSnapshot.published_note_id == published_note_id)
            .order_by(PublicMetricSnapshot.collected_at.desc(), PublicMetricSnapshot.id.desc())
            .limit(1)
        )
        return self.db.execute(stmt).scalar_one_or_none()

    def _latest_private_conversion(self, published_note_id: int) -> PrivateConversionSnapshot | None:
        stmt = (
            select(PrivateConversionSnapshot)
            .where(PrivateConversionSnapshot.published_note_id == published_note_id)
            .order_by(PrivateConversionSnapshot.collected_at.desc(), PrivateConversionSnapshot.id.desc())
            .limit(1)
        )
        return self.db.execute(stmt).scalar_one_or_none()

    def _get_package(self, package_id: int | None) -> PublishPackage | None:
        return self.db.get(PublishPackage, package_id) if package_id else None

    def _get_draft(self, draft_id: int) -> ContentDraft | None:
        return self.db.get(ContentDraft, draft_id)

    def _get_experiment(self, experiment_id: int) -> ContentExperiment | None:
        return self.db.get(ContentExperiment, experiment_id)
