from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Session

from app.agent.schemas.evidence import EvidenceRef, EvidenceType
from app.agent.schemas.execution import ArtifactRef, ArtifactType
from app.agent.tools.access_scopes import EvidenceAccessScope
from app.agent.tools.definitions import ToolError, ToolResult
from app.agent.tools.query_contracts import (
    ArtifactResult,
    ContentOpportunityArtifactView,
    ContentStrategyArtifactView,
    DraftArtifactView,
    EvidenceBundle,
    EvidenceItem,
    GrowthContextResult,
    GrowthContextSection,
    MetricValue,
    MetricWindowResult,
    PostPublishMetricsResult,
    QueryArtifactInput,
    QueryGrowthContextInput,
    QueryPostPublishMetricsInput,
    RetrieveResearchEvidenceInput,
)
from app.repositories.account_repo import AccountProfileRepository
from app.repositories.competitor_analysis_repo import CompetitorAnalysisRepository
from app.repositories.competitor_report_repo import CompetitorReportRepository
from app.repositories.content_strategy_repo import ContentStrategyRepository
from app.repositories.draft_repo import DraftRepository
from app.repositories.publication_repo import PublicationRepository


class QueryToolFailure(Exception):
    """只读 Tool 可安全暴露的分类业务失败。"""

    def __init__(self, code: str, category: str, safe_message: str):
        """保存稳定错误码、分类与安全消息。"""
        super().__init__(safe_message)
        self.code = code
        self.category = category
        self.safe_message = safe_message


@dataclass(frozen=True)
class ArtifactRecord:
    """不同物理模型适配后的内部 Artifact 记录。"""

    content: dict[str, Any]
    version: str
    created_at: datetime | None
    lineage_refs: tuple[ArtifactRef, ...] = ()


@dataclass(frozen=True)
class EvidenceRecord:
    """不同物理证据模型适配后的内部证据记录。"""

    content: str
    structured_facts: dict[str, Any]
    provenance: str
    source_ref: str | None
    observed_at: datetime | None


class QueryToolDataFacade:
    """复用现有 Canonical Repository 的最薄只读适配层。"""

    def __init__(self, db: Session):
        """初始化所有只读 Canonical Repository。"""
        self.db = db
        self.accounts = AccountProfileRepository(db)
        self.research = CompetitorAnalysisRepository(db)
        self.research_evidence = CompetitorReportRepository(db)
        self.strategy = ContentStrategyRepository(db)
        self.drafts = DraftRepository(db)
        self.publication = PublicationRepository(db)

    def get_account(self, account_ref: int):
        """读取账号画像。"""
        return self.accounts.get_by_id(account_ref)

    def list_strategy_memories(self, account_ref: int):
        """读取已经确认的账号策略记忆。"""
        return self.publication.list_strategy_memories(account_ref)

    def get_artifact(self, account_ref: int, artifact_ref: ArtifactRef, draft_version_ref: int | None = None) -> ArtifactRecord | None:
        """按 Artifact 类型访问对应 Canonical Repository 并校验账号归属。"""
        if artifact_ref.type == ArtifactType.RESEARCH:
            item = self.research.get_by_id(artifact_ref.id)
            self._require_owner(item, account_ref)
            if item is None:
                return None
            opportunities = self.strategy.list_opportunities(item.id, 10)
            return ArtifactRecord(
                content={
                    "name": item.name,
                    "summary": item.summary,
                    "content_insights": item.content_insights,
                    "suggestions": item.suggestions,
                    "status": item.status,
                    "content_opportunities": [
                        {
                            "source_opportunity_id": opportunity.id,
                            "topic": opportunity.opportunity_title,
                            "angle": opportunity.suggested_angle,
                            "target_audience": opportunity.target_audience,
                            "content_pillar": opportunity.content_pillar,
                            "evidence_summary": opportunity.evidence_summary,
                            "risk_points": list(opportunity.risk_points or []),
                        }
                        for opportunity in opportunities
                    ],
                },
                version="v1",
                created_at=item.created_at,
            )
        if artifact_ref.type == ArtifactType.CONTENT_STRATEGY:
            item = self.strategy.get_strategy_artifact(artifact_ref.id)
            self._require_owner(item, account_ref)
            if item is None:
                return None
            opportunities = self.strategy.list_strategy_opportunities(item.id)
            view = ContentStrategyArtifactView(
                account_ref=item.account_id,
                research_artifact_ref=item.research_artifact_id,
                strategy_goal=item.strategy_goal,
                target_audience=item.target_audience,
                content_directions=item.content_directions,
                rationale=item.rationale,
                evidence_refs=item.evidence_refs,
                applicable_constraints=item.applicable_constraints,
                generated_opportunity_refs=[opportunity.id for opportunity in opportunities],
            )
            return ArtifactRecord(
                content=view.model_dump(mode="json"),
                version="v1",
                created_at=item.created_at,
                lineage_refs=(ArtifactRef(type=ArtifactType.RESEARCH, id=item.research_artifact_id),),
            )
        if artifact_ref.type == ArtifactType.CONTENT_OPPORTUNITY:
            item = self.strategy.get_strategy_opportunity(artifact_ref.id)
            if item is None:
                return None
            strategy = self.strategy.get_strategy_artifact(item.strategy_artifact_id)
            self._require_owner(strategy, account_ref)
            if strategy is None or strategy.research_artifact_id != item.report_id:
                raise QueryToolFailure("CONTEXT_ERROR", "CONTEXT", "Opportunity lineage 不完整。")
            research = self.research.get_by_id(strategy.research_artifact_id)
            self._require_owner(research, account_ref)
            if research is None:
                raise QueryToolFailure("CONTEXT_ERROR", "CONTEXT", "Opportunity Research lineage 不存在。")
            note_ids = [int(value) for value in research.competitor_note_ids or []]
            account_ids = [int(value) for value in research.competitor_account_ids or []]
            comments = self.research_evidence.list_comments_for_notes(account_ref, note_ids) if note_ids else []
            retrievable_refs = [
                *[EvidenceRef(type=EvidenceType.ACCOUNT, id=value) for value in account_ids],
                *[EvidenceRef(type=EvidenceType.NOTE, id=value) for value in note_ids],
                *[EvidenceRef(type=EvidenceType.COMMENT, id=value.id) for value in comments],
            ]
            opportunity = self.strategy.to_opportunity_result(item)
            view = ContentOpportunityArtifactView(
                account_ref=strategy.account_id,
                strategy_artifact_ref=strategy.id,
                research_artifact_ref=strategy.research_artifact_id,
                source_opportunity_ref=item.source_opportunity_id,
                opportunity=opportunity,
                retrievable_evidence_refs=list(dict.fromkeys(retrievable_refs)),
            )
            return ArtifactRecord(
                content=view.model_dump(mode="json"),
                version="v1",
                created_at=item.created_at,
                lineage_refs=(
                    ArtifactRef(type=ArtifactType.CONTENT_STRATEGY, id=strategy.id),
                    ArtifactRef(type=ArtifactType.RESEARCH, id=strategy.research_artifact_id),
                ),
            )
        if artifact_ref.type == ArtifactType.DRAFT:
            item = self.drafts.get_draft(artifact_ref.id)
            if item is None:
                return None
            self._require_owner(item, account_ref)
            latest = self.drafts.get_latest_version(item.id)
            resolved = self.drafts.get_version(draft_version_ref) if draft_version_ref is not None else latest
            if draft_version_ref is not None and (resolved is None or resolved.draft_id != item.id):
                raise QueryToolFailure("DRAFT_VERSION_ROOT_MISMATCH", "CONTEXT", "Draft Version 不属于指定 Draft Root。")
            view = DraftArtifactView(
                account_ref=item.account_id,
                strategy_artifact_ref=item.strategy_artifact_id,
                opportunity_ref=item.opportunity_id,
                content_goal=item.content_goal,
                latest_draft_version_ref=latest.id if latest else None,
                latest_version=latest.version if latest else None,
                latest_content=self.drafts.version_content(latest) if latest else None,
                latest_created_from=latest.created_from if latest else None,
                latest_parent_draft_ref=latest.parent_version_id if latest else None,
                resolved_draft_version_ref=resolved.id if resolved else None,
                resolved_version=resolved.version if resolved else None,
                resolved_content=self.drafts.version_content(resolved) if resolved else None,
                resolved_created_from=resolved.created_from if resolved else None,
                resolved_parent_draft_ref=resolved.parent_version_id if resolved else None,
                status=item.status,
                created_at=item.created_at,
                updated_at=item.updated_at,
            )
            return ArtifactRecord(
                content=view.model_dump(mode="json"),
                version=f"v{latest.version}" if latest else f"v{item.version}",
                created_at=item.created_at,
                lineage_refs=tuple(
                    ref
                    for ref in (
                        ArtifactRef(type=ArtifactType.CONTENT_STRATEGY, id=item.strategy_artifact_id) if item.strategy_artifact_id else None,
                        ArtifactRef(type=ArtifactType.CONTENT_OPPORTUNITY, id=item.opportunity_id) if item.opportunity_id else None,
                    )
                    if ref is not None
                ),
            )
        if artifact_ref.type in {ArtifactType.DRAFT_REVIEW, ArtifactType.POST_PUBLISH_REVIEW}:
            item = self.publication.get_review(artifact_ref.id)
            if item is None:
                return None
            self._require_owner(item, account_ref)
            expected_review_type = "DRAFT_REVIEW_V1" if artifact_ref.type == ArtifactType.DRAFT_REVIEW else "POST_PUBLISH_REVIEW_V1"
            if item.review_type != expected_review_type:
                return None
            return ArtifactRecord(
                content={"summary": item.summary, "data_facts": item.data_facts, "inferences": item.inferences, "suggestions": item.action_suggestions, "status": item.status},
                version="v1",
                created_at=item.created_at,
                lineage_refs=(ArtifactRef(type=ArtifactType.DRAFT, id=item.draft_id),),
            )
        return None

    def get_evidence(self, account_ref: int, evidence_ref: EvidenceRef) -> EvidenceRecord | None:
        """读取账号授权边界内的已有 Research Evidence，不触发采集。"""
        if evidence_ref.type == EvidenceType.NOTE:
            item = self.research_evidence.get_competitor_note(evidence_ref.id)
            self._require_owner(item, account_ref)
            raw = item.raw_snapshot or {} if item is not None else {}
            ocr_texts = [str(value).strip() for value in raw.get("image_ocr_texts", []) if str(value).strip()]
            return None if item is None else EvidenceRecord(
                content="\n".join(value for value in (item.title, item.content) if value),
                structured_facts={
                    "account_id": item.account_id,
                    "competitor_account_id": item.competitor_account_id,
                    "author_name": item.author_name,
                    "title": item.title,
                    "body": item.content,
                    "tags": item.tags,
                    "like_count": item.like_count,
                    "collect_count": item.collect_count,
                    "comment_count": item.comment_count,
                    "source_type": item.source_type,
                    "provider_name": item.provider_name,
                    "ocr_used": bool(ocr_texts),
                    "ocr_texts": ocr_texts,
                    "likes": item.like_count,
                    "collects": item.collect_count,
                    "comments": item.comment_count,
                },
                provenance=item.source_type,
                source_ref=item.note_url,
                observed_at=item.collected_at,
            )
        if evidence_ref.type == EvidenceType.COMMENT:
            item = self.research_evidence.get_competitor_comment(evidence_ref.id)
            self._require_owner(item, account_ref)
            return None if item is None else EvidenceRecord(
                content=item.content,
                structured_facts={
                    "account_id": item.account_id,
                    "competitor_note_id": item.competitor_note_id,
                    "like_count": item.like_count,
                    "source_type": item.source_type,
                    "provider_name": item.provider_name,
                    "likes": item.like_count,
                    "competitor_note_ref": item.competitor_note_id,
                },
                provenance=item.source_type,
                source_ref=f"NOTE:{item.competitor_note_id}" if item.competitor_note_id else None,
                observed_at=item.collected_at,
            )
        item = self.research_evidence.get_competitor_account(evidence_ref.id)
        self._require_owner(item, account_ref)
        return None if item is None else EvidenceRecord(
            content="\n".join(value for value in (item.nickname, item.bio) if value),
            structured_facts={
                "account_id": item.account_id,
                "nickname": item.nickname,
                "bio": item.bio,
                "follower_count": item.follower_count,
                "note_count": item.note_count,
                "source_type": item.source_type,
                "provider_name": item.provider_name,
                "followers": item.follower_count,
                "notes": item.note_count,
            },
            provenance=item.source_type,
            source_ref=item.homepage_url,
            observed_at=item.collected_at,
        )

    def get_published_note(self, note_ref: int):
        """读取已绑定 Published Note。"""
        return self.publication.get_note(note_ref)

    def list_public_metrics(self, note_ref: int):
        """读取 Published Note 的公开指标快照。"""
        return self.publication.list_public_metrics(note_ref)

    def list_private_metrics(self, note_ref: int):
        """读取 Published Note 的用户归因私域指标快照。"""
        return self.publication.list_private_metrics(note_ref)

    def resolve_published_lineage(self, note):
        """把 publication binding 解析为稳定 Draft Version 主键。"""
        try:
            binding = self.publication.resolve_published_binding(note)
        except ValueError as exc:
            code = str(exc)
            raise QueryToolFailure(code, "CONTEXT", "Published Draft binding 非法或 lineage 冲突。") from exc
        version = None
        if binding["version_number"] is not None:
            version = self.drafts.get_version_by_number(binding["draft_ref"], binding["version_number"])
            if version is None:
                raise QueryToolFailure("PUBLISHED_VERSION_LINEAGE_MISSING", "CONTEXT", "Published Draft Version 不存在。")
        return binding, version

    def _require_owner(self, item, account_ref: int) -> None:
        """资源存在但不属于当前账号时返回权限错误。"""
        if item is not None and getattr(item, "account_id", None) != account_ref:
            raise QueryToolFailure("PERMISSION_ERROR", "PERMISSION", "当前账号无权读取该资源。")


class QueryToolBase:
    """四个只读 Tool 共用的失败结果标准化能力。"""

    def _failure(self, failure: QueryToolFailure) -> ToolResult:
        """把已分类业务失败转换为统一 ToolResult。"""
        return ToolResult(success=False, error=ToolError(code=failure.code, category=failure.category, retryable=False, safe_message=failure.safe_message))

    def _internal_failure(self, exc: Exception) -> ToolResult:
        """把 Repository 技术异常转换为安全内部错误并保留异常类型元数据。"""
        return ToolResult(
            success=False,
            error=ToolError(code="INTERNAL_ERROR", category="INTERNAL", retryable=True, safe_message="内部数据读取失败，请稍后重试。"),
            metadata={"exception_type": type(exc).__name__},
        )


class QueryGrowthContextTool(QueryToolBase):
    """读取白名单章节内的账号增长上下文。"""

    name = "query_growth_context"

    def __init__(self, db: Session | None = None, facade: QueryToolDataFacade | None = None):
        """注入只读数据 Facade。"""
        self.facade = facade or QueryToolDataFacade(db)

    def execute(self, data: QueryGrowthContextInput) -> ToolResult[GrowthContextResult]:
        """读取请求章节，缺失可选章节保持 UNKNOWN 而不编造默认值。"""
        try:
            account = self.facade.get_account(data.account_ref)
            if account is None:
                raise QueryToolFailure("CONTEXT_ERROR", "CONTEXT", "账号上下文不存在。")
            observed_at = datetime.now(UTC)
            result: dict[str, Any] = {"account": None, "business_profile": None, "customer_model": None, "growth_goal": None, "strategy_memory": [], "missing_sections": [], "context_version": f"account:{account.id}:{getattr(account, 'updated_at', None)}", "observed_at": observed_at}
            for section in data.requested_sections:
                self._fill_section(result, section, account, data.as_of)
            return ToolResult(success=True, data=GrowthContextResult(**result))
        except QueryToolFailure as exc:
            return self._failure(exc)
        except Exception as exc:
            return self._internal_failure(exc)

    def _fill_section(self, result: dict[str, Any], section: GrowthContextSection, account, as_of: datetime | None) -> None:
        """将一个白名单章节映射到结果，无法确定时记录缺失。"""
        if section == GrowthContextSection.ACCOUNT_PROFILE:
            result["account"] = {"id": account.id, "name": account.account_name, "platform": account.platform, "positioning": account.positioning, "persona": account.persona}
        elif section == GrowthContextSection.BUSINESS_PROFILE:
            value = {"business_model": account.business_model, "main_product": account.main_product, "monetization_goal": account.monetization_goal}
            result["business_profile"] = value if any(item is not None for item in value.values()) else None
        elif section == GrowthContextSection.CUSTOMER_MODEL:
            result["customer_model"] = {"target_audience": account.target_audience} if account.target_audience else None
        elif section == GrowthContextSection.GROWTH_GOAL:
            result["growth_goal"] = {"primary_goal": account.primary_goal, "account_stage": account.account_stage} if account.primary_goal else None
        else:
            memories = self.facade.list_strategy_memories(account.id)
            if as_of is not None:
                memories = [item for item in memories if _datetime_in_upper_bound(item.updated_at, as_of)]
            result["strategy_memory"] = [{"ref": item.id, "type": item.memory_type, "summary": item.summary, "pattern": item.pattern, "confidence": item.confidence} for item in memories]
        key = _SECTION_RESULT_KEYS[section]
        if result[key] is None or result[key] == []:
            result["missing_sections"].append(section)


class QueryArtifactTool(QueryToolBase):
    """按明确 ArtifactRef 读取现有系统产物。"""

    name = "query_artifact"

    def __init__(self, db: Session | None = None, facade: QueryToolDataFacade | None = None):
        """注入只读数据 Facade。"""
        self.facade = facade or QueryToolDataFacade(db)

    def execute(self, data: QueryArtifactInput) -> ToolResult[ArtifactResult]:
        """读取并统一不同物理模型，不创建通用 Artifact 表。"""
        try:
            if data.draft_version_ref is None:
                record = self.facade.get_artifact(data.account_ref, data.artifact_ref)
            else:
                record = self.facade.get_artifact(data.account_ref, data.artifact_ref, data.draft_version_ref)
            if record is None:
                raise QueryToolFailure("CONTEXT_ERROR", "CONTEXT", "请求的 Artifact 不存在。")
            result = ArtifactResult(artifact_ref=data.artifact_ref, artifact_type=data.artifact_ref.type, version=record.version, content=record.content, created_at=record.created_at, lineage_refs=list(record.lineage_refs))
            return ToolResult(success=True, data=result)
        except QueryToolFailure as exc:
            return self._failure(exc)
        except Exception as exc:
            return self._internal_failure(exc)


class RetrieveResearchEvidenceTool(QueryToolBase):
    """只读解析白名单内的 EvidenceRef，不触发任何外部采集。"""

    name = "retrieve_research_evidence"

    def __init__(
        self,
        db: Session | None = None,
        facade: QueryToolDataFacade | None = None,
        access_scope: EvidenceAccessScope | None = None,
    ):
        """注入只读数据 Facade 与可信证据授权范围。"""
        self.facade = facade or QueryToolDataFacade(db)
        self.access_scope = access_scope or EvidenceAccessScope.deny_all()

    def execute(self, data: RetrieveResearchEvidenceInput) -> ToolResult[EvidenceBundle]:
        """校验授权集合并返回有条数和字符上限的 Evidence Bundle。"""
        try:
            allowed = self.access_scope.authorized_refs
            if any(item not in allowed for item in data.evidence_refs):
                raise QueryToolFailure("VALIDATION_ERROR", "VALIDATION", "EvidenceRef 不在授权证据集合中。")
            selected = data.evidence_refs[: data.max_items]
            items: list[EvidenceItem] = []
            truncated = len(data.evidence_refs) > len(selected)
            for evidence_ref in selected:
                record = self.facade.get_evidence(data.account_ref, evidence_ref)
                if record is None:
                    raise QueryToolFailure("CONTEXT_ERROR", "CONTEXT", f"Evidence {evidence_ref.type}:{evidence_ref.id} 不存在。")
                content = record.content[: data.max_content_chars]
                truncated = truncated or len(content) < len(record.content)
                items.append(EvidenceItem(evidence_ref=evidence_ref, evidence_type=evidence_ref.type, content=content, structured_facts=record.structured_facts, provenance=record.provenance, source_ref=record.source_ref, observed_at=record.observed_at))
            return ToolResult(success=True, data=EvidenceBundle(items=items, purpose=data.purpose, truncated=truncated))
        except QueryToolFailure as exc:
            return self._failure(exc)
        except Exception as exc:
            return self._internal_failure(exc)


class QueryPostPublishMetricsTool(QueryToolBase):
    """查询已绑定笔记现有指标快照，不刷新平台数据。"""

    name = "query_post_publish_metrics"

    def __init__(self, db: Session | None = None, facade: QueryToolDataFacade | None = None):
        """注入只读数据 Facade。"""
        self.facade = facade or QueryToolDataFacade(db)

    def execute(self, data: QueryPostPublishMetricsInput) -> ToolResult[PostPublishMetricsResult]:
        """返回窗口内最新公开与私域快照，并保持私域缺失值为 UNKNOWN。"""
        try:
            note = self.facade.get_published_note(data.published_note_ref)
            if note is None:
                raise QueryToolFailure("CONTEXT_ERROR", "CONTEXT", "Published Note 不存在。")
            if note.account_id != data.account_ref:
                raise QueryToolFailure("PERMISSION_ERROR", "PERMISSION", "当前账号无权读取该 Published Note。")
            binding, published_version = self.facade.resolve_published_lineage(note)
            public = _latest_in_window(self.facade.list_public_metrics(note.id), data.window_start, data.window_end)
            private = _latest_in_window(self.facade.list_private_metrics(note.id), data.window_start, data.window_end) if data.include_private else None
            private_metrics, missing = self._private_metrics(private, data.include_private)
            public_metrics = self._public_metrics(public) if public is not None else {}
            observed_values = [value for value in (getattr(public, "collected_at", None), getattr(private, "collected_at", None)) if value is not None]
            observed = max(observed_values) if observed_values else None
            result = PostPublishMetricsResult(
                published_note_ref=note.id,
                publish_url=note.publish_url or None,
                account_ref=note.account_id,
                draft_ref=note.draft_id,
                published_draft_binding_ref=binding["binding_ref"],
                published_draft_version_number=binding["version_number"],
                published_draft_version_ref=published_version.id if published_version else None,
                publish_package_ref=binding["publish_package_ref"],
                published_lineage_complete=published_version is not None,
                public_metrics_status="AVAILABLE" if public is not None else "UNKNOWN",
                public_metric_snapshot_ref=getattr(public, "id", None) if public is not None else None,
                public_metrics=public_metrics,
                private_metric_snapshot_ref=getattr(private, "id", None) if private is not None else None,
                private_metrics=private_metrics,
                window=MetricWindowResult(start=data.window_start, end=data.window_end),
                provenance=[*(["MEASURED"] if public is not None else []), *(["USER_ATTRIBUTED"] if private is not None else [])],
                observed_at=observed,
                missing_metrics=[*(["public_metrics"] if public is None else []), *missing],
            )
            return ToolResult(success=True, data=result)
        except QueryToolFailure as exc:
            return self._failure(exc)
        except Exception as exc:
            return self._internal_failure(exc)

    def _private_metrics(self, snapshot, include_private: bool) -> tuple[dict[str, MetricValue] | None, list[str]]:
        """从 provided_fields 还原私域值，无法确认的数据库零值保持 UNKNOWN。"""
        if not include_private:
            return None, []
        names = ("dm_count", "wechat_add_count", "consultation_count", "deal_count", "revenue")
        if snapshot is None:
            return {name: MetricValue(value=None, provenance="UNKNOWN") for name in names}, list(names)
        raw = snapshot.raw_snapshot or {}
        provided = set(raw.get("provided_fields", []))
        values = raw.get("values", {})
        result = {name: MetricValue(value=values.get(name) if name in provided else None, provenance="USER_ATTRIBUTED" if name in provided else "UNKNOWN") for name in names}
        return result, [name for name in names if name not in provided]

    def _public_metrics(self, snapshot) -> dict[str, MetricValue]:
        """只把采集响应中真实存在的公开指标标记为 MEASURED。"""
        columns = {
            "views": ("view_count", snapshot.view_count),
            "likes": ("like_count", snapshot.like_count),
            "collects": ("collect_count", snapshot.collect_count),
            "comments": ("comment_count", snapshot.comment_count),
            "shares": ("share_count", snapshot.share_count),
            "follows": ("follow_count", snapshot.follow_count),
            "profile_visits": ("profile_visit_count", snapshot.profile_visit_count),
        }
        raw = getattr(snapshot, "raw_snapshot", None) or {}
        provided = set((raw.get("metrics") or {}).keys())
        if not provided:
            return {name: MetricValue(value=value, provenance="MEASURED") for name, (_, value) in columns.items()}
        return {
            name: MetricValue(value=value if source in provided else None, provenance="MEASURED" if source in provided else "UNKNOWN")
            for name, (source, value) in columns.items()
        }


_SECTION_RESULT_KEYS = {
    GrowthContextSection.ACCOUNT_PROFILE: "account",
    GrowthContextSection.BUSINESS_PROFILE: "business_profile",
    GrowthContextSection.CUSTOMER_MODEL: "customer_model",
    GrowthContextSection.GROWTH_GOAL: "growth_goal",
    GrowthContextSection.STRATEGY_MEMORY: "strategy_memory",
}


def _normalize_datetime(value: datetime) -> datetime:
    """将数据库可能返回的无时区时间统一为 UTC。"""
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def _datetime_in_upper_bound(value: datetime, upper: datetime) -> bool:
    """判断时间是否不晚于上界。"""
    return _normalize_datetime(value) <= _normalize_datetime(upper)


def _latest_in_window(items: list[Any], start: datetime, end: datetime):
    """选择真实采集时间位于窗口内的最新快照。"""
    normalized_start = _normalize_datetime(start)
    normalized_end = _normalize_datetime(end)
    matched = [item for item in items if normalized_start <= _normalize_datetime(item.collected_at) <= normalized_end]
    return max(matched, key=lambda item: _normalize_datetime(item.collected_at), default=None)
