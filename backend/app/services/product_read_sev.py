from app.repositories.competitor_report_repo import CompetitorReportRepository
from app.repositories.content_strategy_repo import ContentStrategyRepository
from app.repositories.draft_repo import DraftRepository
from app.repositories.publication_repo import PublicationRepository
from app.schemas.product_read import (
    DraftContentView,
    DraftDetail,
    DraftListPage,
    DraftReviewSummary,
    DraftSummary,
    DraftVersionMetadata,
    MetricSnapshot,
    PostPublishReviewSummary,
    PublicationDetail,
    PublicationListPage,
    PublicationSummary,
    ResearchDetail,
    ResearchListPage,
    ResearchOpportunity,
    ResearchSummary,
    ReviewListPage,
    ReviewSummary,
    StrategyCandidateSummary,
    StrategyDetail,
    StrategyListPage,
    StrategyOpportunity,
    StrategySummary,
)


class ProductReadError(RuntimeError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


class ProductReadService:
    """面向产品详情页的只读投影；复用四个 canonical persistence owners。"""

    def __init__(self, db):
        self.research = CompetitorReportRepository(db)
        self.strategies = ContentStrategyRepository(db)
        self.drafts = DraftRepository(db)
        self.publications = PublicationRepository(db)

    def research_detail(self, ref: int, account_ref: int) -> ResearchDetail:
        report = self.research.get_report(ref)
        self._owned(report, account_ref, "RESEARCH")
        opportunities = self.research.list_opportunities(ref)
        limitations = [str(item) for item in (report.risk_points or [])]
        if report.error_message:
            limitations.append(report.error_message)
        return ResearchDetail(
            ref=report.id,
            account_ref=report.account_id,
            name=report.name,
            topic=report.keyword,
            summary=report.summary,
            status=report.status,
            findings={
                "persona_patterns": report.persona_patterns or [],
                "content_pillars": report.content_pillars or [],
                "content_insights": report.content_insights or [],
                "suggestions": report.suggestions or [],
            },
            source_metadata={
                "source_type": report.source_type,
                "target_metric": report.target_metric,
                "note_count": report.note_count,
                "comment_count": report.comment_count,
                "note_refs": report.competitor_note_ids or report.note_snapshot_ids or [],
                "account_refs": report.competitor_account_ids or [],
            },
            opportunities=[
                ResearchOpportunity(
                    ref=item.id,
                    title=item.opportunity_title,
                    angle=item.suggested_angle,
                    target_audience=item.target_audience,
                    evidence_summary=item.evidence_summary,
                    score=item.opportunity_score,
                    risk_level=item.risk_level,
                )
                for item in opportunities
                if item.strategy_artifact_id is None
            ],
            warnings=[] if report.status == "SUCCESS" else [report.status],
            limitations=limitations,
            created_at=report.created_at,
            updated_at=report.updated_at,
        )

    def list_research(self, account_ref: int, page_no: int, page_size: int) -> ResearchListPage:
        self._account(account_ref)
        items, total = self.research.list_reports_by_account(account_ref, self._offset(page_no, page_size), page_size)
        return ResearchListPage(
            items=[ResearchSummary(ref=item.id, name=item.name, topic=item.keyword, status=item.status, created_at=item.created_at, updated_at=item.updated_at) for item in items],
            **self._page(page_no, page_size, total),
        )

    def strategy_detail(self, ref: int, account_ref: int) -> StrategyDetail:
        strategy = self.strategies.get_strategy_artifact(ref)
        self._owned(strategy, account_ref, "STRATEGY")
        opportunities = self.strategies.list_strategy_opportunities(ref)
        return StrategyDetail(
            ref=strategy.id,
            account_ref=strategy.account_id,
            research_ref=strategy.research_artifact_id,
            goal=strategy.strategy_goal,
            audience=strategy.target_audience,
            directions=strategy.content_directions or [],
            rationale=strategy.rationale,
            evidence_refs=strategy.evidence_refs or [],
            constraints=strategy.applicable_constraints or [],
            opportunities=[
                StrategyOpportunity(
                    ref=item.id,
                    source_opportunity_ref=item.source_opportunity_id,
                    topic=item.opportunity_title,
                    angle=item.suggested_angle,
                    target_audience=item.target_audience,
                    content_goal=item.content_goal,
                    why_now=item.why_now,
                    suggested_hook=item.suggested_hook,
                    evidence_refs=item.evidence_refs or [],
                    constraints=item.constraints or [],
                )
                for item in opportunities
            ],
            created_at=strategy.created_at,
        )

    def list_strategies(self, account_ref: int, page_no: int, page_size: int) -> StrategyListPage:
        self._account(account_ref)
        items, total = self.strategies.list_strategies_by_account(account_ref, self._offset(page_no, page_size), page_size)
        return StrategyListPage(
            items=[StrategySummary(ref=item.id, research_ref=item.research_artifact_id, goal=item.strategy_goal, audience=item.target_audience, created_at=item.created_at) for item in items],
            **self._page(page_no, page_size, total),
        )

    def draft_detail(self, ref: int, account_ref: int) -> DraftDetail:
        draft = self.drafts.get_draft(ref)
        self._owned(draft, account_ref, "DRAFT")
        versions = self.drafts.list_versions(ref)
        latest = max(versions, key=lambda item: (item.version, item.id), default=None)
        snapshot = (latest.draft_snapshot or {}) if latest else {}
        reviews = self.drafts.list_reviews(ref)
        return DraftDetail(
            ref=draft.id,
            account_ref=draft.account_id,
            strategy_ref=draft.strategy_artifact_id,
            opportunity_ref=draft.opportunity_id,
            content_goal=draft.content_goal,
            status=draft.status,
            latest_version_ref=latest.id if latest else None,
            latest_version=latest.version if latest else draft.version,
            current_content=DraftContentView(
                title=snapshot.get("title") or draft.recommended_title or draft.title,
                body=snapshot.get("body") or draft.body_text or draft.body,
                tags=snapshot.get("tags") or draft.tag_list or draft.tags or [],
                cta=snapshot.get("cta") if "cta" in snapshot else draft.cta_text or draft.cta,
            ),
            versions=[
                DraftVersionMetadata(
                    ref=item.id,
                    version=item.version,
                    parent_version_ref=item.parent_version_id,
                    created_from=item.created_from,
                    created_at=item.created_at,
                    content=DraftContentView(
                        title=(item.draft_snapshot or {}).get("title", ""),
                        body=(item.draft_snapshot or {}).get("body", ""),
                        tags=(item.draft_snapshot or {}).get("tags") or [],
                        cta=(item.draft_snapshot or {}).get("cta"),
                    ),
                )
                for item in versions
            ],
            reviews=[
                DraftReviewSummary(
                    ref=item.id,
                    status=item.status,
                    passed=item.passed,
                    score=item.score,
                    risk_level=item.risk_level,
                    summary=item.summary,
                    created_at=item.created_at,
                )
                for item in reviews
            ],
            created_at=draft.created_at,
            updated_at=draft.updated_at,
        )

    def list_drafts(self, account_ref: int, page_no: int, page_size: int) -> DraftListPage:
        self._account(account_ref)
        items, total = self.drafts.list_drafts_by_account(account_ref, self._offset(page_no, page_size), page_size)
        return DraftListPage(
            items=[DraftSummary(ref=item.id, title=item.recommended_title or item.title, version=item.version, status=item.status, updated_at=item.updated_at) for item in items],
            **self._page(page_no, page_size, total),
        )

    def publication_detail(self, ref: int, account_ref: int) -> PublicationDetail:
        note = self.publications.get_note(ref)
        self._owned(note, account_ref, "PUBLICATION")
        try:
            binding = self.publications.resolve_published_binding(note)
        except ValueError as exc:
            raise ProductReadError("PUBLICATION_LINEAGE_INVALID", str(exc)) from exc
        version = None
        if binding["version_number"] is not None:
            version = self.drafts.get_version_by_number(note.draft_id, binding["version_number"])
        content = None
        if version is not None:
            snapshot = version.draft_snapshot or {}
            content = DraftContentView(
                title=snapshot.get("title", ""), body=snapshot.get("body", ""),
                tags=snapshot.get("tags") or [], cta=snapshot.get("cta"),
            )
        public = self.publications.list_public_metrics(note.id)
        private = self.publications.list_private_metrics(note.id)
        review = self.publications.get_post_publish_review(note.id)
        candidates = self.publications.list_strategy_candidates(review.id) if review else []
        return PublicationDetail(
            ref=note.id,
            account_ref=note.account_id,
            publish_url=note.publish_url,
            platform=note.platform,
            status=note.status,
            published_at=note.published_at,
            draft_ref=note.draft_id,
            published_draft_version_ref=version.id if version else None,
            published_draft_version=binding["version_number"],
            published_content=content,
            public_metrics=[self._public_metric(item) for item in public],
            private_metrics_status="AVAILABLE" if private else "UNKNOWN",
            private_metrics=[self._private_metric(item) for item in private],
            post_publish_review=self._review(review),
            strategy_candidates=[
                StrategyCandidateSummary(
                    ref=item.id, statement=item.statement, scope=item.scope,
                    supporting_refs=item.supporting_refs or [],
                    contradicting_refs=item.contradicting_refs or [],
                    confidence_context=item.confidence_context,
                    status=item.status,
                )
                for item in candidates
            ],
            created_at=note.created_at,
        )

    def list_publications(self, account_ref: int, page_no: int, page_size: int) -> PublicationListPage:
        self._account(account_ref)
        rows, total = self.publications.list_notes_by_account(account_ref, self._offset(page_no, page_size), page_size)
        return PublicationListPage(
            items=[PublicationSummary(
                ref=note.id, draft_ref=note.draft_id, draft_version_ref=note.draft_version_id,
                version_number=version.version if version else None,
                title=draft.recommended_title or draft.title, status=note.status, published_at=note.published_at,
            ) for note, draft, version in rows],
            **self._page(page_no, page_size, total),
        )

    def list_reviews(self, account_ref: int, page_no: int, page_size: int) -> ReviewListPage:
        self._account(account_ref)
        items, total = self.publications.list_reviews_by_account(account_ref, self._offset(page_no, page_size), page_size)
        return ReviewListPage(
            items=[ReviewSummary(ref=item.id, published_note_ref=item.published_note_id, status=item.status, result_status=item.result_status, created_at=item.created_at) for item in items],
            **self._page(page_no, page_size, total),
        )

    def _account(self, account_ref: int):
        if self.research.get_account(account_ref) is None:
            raise ProductReadError("ACCOUNT_NOT_FOUND", "Account 不存在。")

    @staticmethod
    def _offset(page_no: int, page_size: int) -> int:
        return (page_no - 1) * page_size

    @staticmethod
    def _page(page_no: int, page_size: int, total: int) -> dict[str, int]:
        return {"page_no": page_no, "page_size": page_size, "total": total, "pages": (total + page_size - 1) // page_size}

    @staticmethod
    def _owned(item, account_ref: int, resource: str):
        if item is None:
            raise ProductReadError(f"{resource}_NOT_FOUND", f"{resource} 不存在。")
        if item.account_id != account_ref:
            raise ProductReadError(f"{resource}_ACCOUNT_MISMATCH", f"{resource} 不属于当前 Account。")

    @staticmethod
    def _public_metric(item):
        return MetricSnapshot(
            ref=item.id, window=item.snapshot_window,
            values={name: getattr(item, name) for name in (
                "view_count", "like_count", "collect_count", "comment_count", "share_count",
                "follow_count", "profile_visit_count",
            )},
            source_type=item.source_type, collected_at=item.collected_at,
        )

    @staticmethod
    def _private_metric(item):
        provided = set((item.raw_snapshot or {}).get("provided_fields") or [])
        field_map = {"revenue": "revenue_amount"}
        names = ("dm_count", "wechat_add_count", "consultation_count", "deal_count", "revenue")
        return MetricSnapshot(
            ref=item.id, window=item.snapshot_window,
            values={name: getattr(item, field_map.get(name, name)) if name in provided else None for name in names},
            source_type=item.source_type, collected_at=item.collected_at,
        )

    @staticmethod
    def _review(item):
        if item is None:
            return None
        return PostPublishReviewSummary(
            ref=item.id, status=item.status, result_status=item.result_status,
            summary=item.summary, observed_facts=item.data_facts or [],
            inferences=item.inferences or [], created_at=item.created_at,
        )
