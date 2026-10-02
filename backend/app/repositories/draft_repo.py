from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.account import AccountProfile
from app.models.content_draft import ContentDraft
from app.models.content_draft_version import ContentDraftVersion
from app.models.content_experiment import ContentExperiment
from app.models.content_opportunity import ContentOpportunity
from app.models.content_strategy_artifact import ContentStrategyArtifact
from app.models.review_report import ReviewReport
from app.schemas.draft import DraftContent, DraftPersistenceMetadata


class DraftRepository:
    """Draft、Review 和 Version lineage 的唯一持久化边界。"""

    def __init__(self, db: Session):
        """保存数据库会话。"""
        self.db = db

    def get_account(self, account_id: int):
        """读取账号。"""
        return self.db.get(AccountProfile, account_id)

    def get_opportunity(self, opportunity_id: int):
        """读取内容机会。"""
        return self.db.get(ContentOpportunity, opportunity_id)

    def get_draft(self, draft_id: int):
        """读取 Draft。"""
        return self.db.get(ContentDraft, draft_id)

    def list_drafts_by_account(self, account_id: int, offset: int, limit: int) -> tuple[list[ContentDraft], int]:
        """按账号分页读取内容草稿索引。"""
        total = self.db.execute(
            select(func.count()).select_from(ContentDraft).where(ContentDraft.account_id == account_id)
        ).scalar_one()
        statement = (
            select(ContentDraft)
            .where(ContentDraft.account_id == account_id)
            .order_by(ContentDraft.updated_at.desc(), ContentDraft.id.desc())
            .offset(offset).limit(limit)
        )
        return list(self.db.execute(statement).scalars().all()), int(total)

    def get_version(self, version_id: int):
        """读取 Draft Version 快照。"""
        return self.db.get(ContentDraftVersion, version_id)

    def get_version_by_number(self, draft_id: int, version: int) -> ContentDraftVersion | None:
        """按 Draft Root 与版本号确定性读取正式 Version。"""
        statement = select(ContentDraftVersion).where(
            ContentDraftVersion.draft_id == draft_id,
            ContentDraftVersion.version == version,
        )
        return self.db.execute(statement).scalar_one_or_none()

    def get_review(self, review_id: int):
        """读取 Draft Review。"""
        return self.db.get(ReviewReport, review_id)

    def resolve_legacy_experiment_id(self, account_id: int, opportunity_id: int) -> int | None:
        """解析当前物理模型仍需要的兼容实验标识。"""
        statement = (
            select(ContentExperiment.id)
            .where(
                ContentExperiment.account_id == account_id,
                ContentExperiment.content_opportunity_id == opportunity_id,
            )
            .order_by(ContentExperiment.id.desc())
            .limit(1)
        )
        return self.db.execute(statement).scalar_one_or_none()

    def create_draft(self, *, experiment_id: int, content, version: int, status: str, context: dict, llm_result) -> ContentDraft:
        """保存 Legacy-compatible Draft，并从 Experiment 确定必填 account_id。"""
        experiment = self.db.get(ContentExperiment, experiment_id)
        if experiment is None:
            raise ValueError("Content Experiment 不存在")
        draft = ContentDraft(
            experiment_id=experiment_id,
            account_id=experiment.account_id,
            title=content.title,
            body=content.body,
            tags=content.tags,
            cta=content.cta,
            title_candidates=[content.title],
            recommended_title=content.title,
            body_text=content.body,
            tag_list=content.tags,
            cta_text=content.cta,
            version=version,
            status=status,
            generation_context=context,
            prompt_tokens=llm_result.usage.prompt_tokens,
            completion_tokens=llm_result.usage.completion_tokens,
            total_tokens=llm_result.usage.total_tokens,
            estimated_cost=Decimal(str(llm_result.estimated_cost)),
            raw_response_id=llm_result.raw_response_id,
        )
        self.db.add(draft)
        self.db.commit()
        self.db.refresh(draft)
        return draft

    def create_agent_draft_root(
        self,
        *,
        account_id: int,
        strategy_artifact_id: int,
        opportunity_id: int,
        content_goal: str,
        content: DraftContent,
        metadata: DraftPersistenceMetadata | None = None,
        context: dict | None = None,
    ) -> tuple[ContentDraft, ContentDraftVersion]:
        """原子创建不依赖 Experiment 的 Draft Root 及 GENERATED V1。"""
        strategy, opportunity = self._validate_agent_identity(
            account_id=account_id,
            strategy_artifact_id=strategy_artifact_id,
            opportunity_id=opportunity_id,
            content_goal=content_goal,
        )
        explicit = metadata or DraftPersistenceMetadata()
        root = ContentDraft(
            experiment_id=None,
            account_id=account_id,
            strategy_artifact_id=strategy.id,
            opportunity_id=opportunity.id,
            content_goal=content_goal,
            title=content.title,
            body=content.body,
            tags=content.tags,
            cta=content.cta,
            title_candidates=[content.title],
            recommended_title=content.title,
            body_text=content.body,
            tag_list=content.tags,
            cta_text=content.cta,
            version=1,
            status="GENERATED",
            generation_context=context or {},
            prompt_tokens=explicit.prompt_tokens,
            completion_tokens=explicit.completion_tokens,
            total_tokens=explicit.total_tokens,
            estimated_cost=explicit.estimated_cost,
            raw_response_id=explicit.raw_response_id,
        )
        try:
            self.db.add(root)
            self.db.flush()
            version = self._agent_version(
                root,
                content=content,
                version=1,
                parent_version_id=None,
                created_from="GENERATED",
                applied_changes=[],
            )
            self.db.add(version)
            self.db.flush()
            self.db.refresh(root)
            self.db.refresh(version)
            return root, version
        except Exception:
            raise

    def append_agent_draft_version(
        self,
        *,
        draft_id: int,
        parent_version_id: int,
        created_from: str,
        content: DraftContent,
        metadata: DraftPersistenceMetadata | None = None,
        context: dict | None = None,
        applied_changes: list[str] | None = None,
    ) -> tuple[ContentDraft, ContentDraftVersion]:
        """在同一 New Agent Draft Root 下追加无分支的下一版本。"""
        if created_from not in {"REVIEW_REVISION", "USER_REVISION"}:
            raise ValueError("append_agent_draft_version 只允许 REVIEW_REVISION 或 USER_REVISION")
        root = self.get_draft(draft_id)
        if root is None:
            raise ValueError("Draft Root 不存在")
        if root.experiment_id is not None or not all(
            (root.account_id, root.strategy_artifact_id, root.opportunity_id, root.content_goal)
        ):
            raise ValueError("仅允许向 Identity 完整的 New Agent Draft Root 追加版本")
        parent = self.get_version(parent_version_id)
        if parent is None or parent.draft_id != root.id:
            raise ValueError("Parent Version 不属于当前 Draft Root")
        latest = self.get_latest_version(root.id)
        if latest is None or latest.id != parent.id:
            raise ValueError("Parent Version 不是当前 latest Version")

        explicit = metadata or DraftPersistenceMetadata()
        version_number = parent.version + 1
        version = self._agent_version(
            root,
            content=content,
            version=version_number,
            parent_version_id=parent.id,
            created_from=created_from,
            applied_changes=applied_changes or [],
        )
        self._mirror_content(root, content)
        root.version = version_number
        root.status = "REVISED"
        root.generation_context = context or root.generation_context or {}
        root.prompt_tokens = explicit.prompt_tokens
        root.completion_tokens = explicit.completion_tokens
        root.total_tokens = explicit.total_tokens
        root.estimated_cost = explicit.estimated_cost
        root.raw_response_id = explicit.raw_response_id
        try:
            self.db.add(version)
            self.db.flush()
            self.db.refresh(root)
            self.db.refresh(version)
            return root, version
        except Exception:
            raise

    def get_latest_version(self, draft_id: int) -> ContentDraftVersion | None:
        """读取同一 Draft Root 下版本号最高的正式 Version。"""
        statement = (
            select(ContentDraftVersion)
            .where(ContentDraftVersion.draft_id == draft_id)
            .order_by(ContentDraftVersion.version.desc(), ContentDraftVersion.id.desc())
            .limit(1)
        )
        return self.db.execute(statement).scalar_one_or_none()

    def list_versions(self, draft_id: int) -> list[ContentDraftVersion]:
        """按版本号返回 Draft 的轻量版本索引数据源。"""
        statement = (
            select(ContentDraftVersion)
            .where(ContentDraftVersion.draft_id == draft_id)
            .order_by(ContentDraftVersion.version.asc(), ContentDraftVersion.id.asc())
        )
        return list(self.db.execute(statement).scalars().all())

    def list_reviews(self, draft_id: int) -> list[ReviewReport]:
        """读取 Draft Review；详情服务只投影安全字段。"""
        statement = (
            select(ReviewReport)
            .where(ReviewReport.draft_id == draft_id, ReviewReport.review_type != "POST_PUBLISH_REVIEW_V1")
            .order_by(ReviewReport.created_at.desc(), ReviewReport.id.desc())
        )
        return list(self.db.execute(statement).scalars().all())

    def version_content(self, version: ContentDraftVersion) -> DraftContent:
        """从正式 Version snapshot 恢复 DraftContent，不读取 Root mirror。"""
        snapshot = version.draft_snapshot or {}
        return DraftContent.model_validate(
            {name: snapshot.get(name) for name in ("title", "body", "tags", "cta")}
        )

    def _validate_agent_identity(
        self,
        *,
        account_id: int,
        strategy_artifact_id: int,
        opportunity_id: int,
        content_goal: str,
    ) -> tuple[ContentStrategyArtifact, ContentOpportunity]:
        """校验 New Agent Draft Root 的账号、Strategy、Opportunity 与 Research lineage。"""
        if self.get_account(account_id) is None:
            raise ValueError("账号配置不存在")
        strategy = self.db.get(ContentStrategyArtifact, strategy_artifact_id)
        if strategy is None or strategy.account_id != account_id:
            raise ValueError("Content Strategy Artifact 不属于当前账号")
        opportunity = self.get_opportunity(opportunity_id)
        if opportunity is None or opportunity.strategy_artifact_id != strategy.id:
            raise ValueError("Content Opportunity 不属于当前 Strategy Artifact")
        if opportunity.content_goal != content_goal:
            raise ValueError("Content Opportunity content_goal 不一致")
        if strategy.research_artifact_id != opportunity.report_id:
            raise ValueError("Strategy 与 Opportunity 的 Research lineage 不一致")
        return strategy, opportunity

    def _agent_version(
        self,
        root: ContentDraft,
        *,
        content: DraftContent,
        version: int,
        parent_version_id: int | None,
        created_from: str,
        applied_changes: list[str],
    ) -> ContentDraftVersion:
        """构造包含完整内容、正式来源与审计 Identity 的 Draft Version。"""
        snapshot = {
            "draft_id": root.id,
            "version": version,
            "parent_version_id": parent_version_id,
            "created_from": created_from,
            "title": content.title,
            "body": content.body,
            "tags": content.tags,
            "cta": content.cta,
            "applied_changes": applied_changes,
            "identity": {
                "account_id": root.account_id,
                "strategy_artifact_id": root.strategy_artifact_id,
                "opportunity_id": root.opportunity_id,
                "content_goal": root.content_goal,
            },
        }
        return ContentDraftVersion(
            draft_id=root.id,
            version=version,
            parent_version_id=parent_version_id,
            created_from=created_from,
            regenerate_scope=created_from,
            draft_snapshot=snapshot,
        )

    def _mirror_content(self, root: ContentDraft, content: DraftContent) -> None:
        """把 latest Version 正文同步到 Root 的兼容读取列。"""
        root.title = content.title
        root.recommended_title = content.title
        root.body = content.body
        root.body_text = content.body
        root.tags = content.tags
        root.tag_list = content.tags
        root.cta = content.cta
        root.cta_text = content.cta

    def create_version(self, draft: ContentDraft, *, created_from: str, parent_draft_ref: int | None, applied_changes: list[str]) -> ContentDraftVersion:
        """保存带 lineage 的 Draft Version 快照。"""
        snapshot = {
            "draft_id": draft.id,
            "version": draft.version,
            "parent_draft_ref": parent_draft_ref,
            "created_from": created_from,
            "title": draft.recommended_title or draft.title,
            "body": draft.body_text or draft.body,
            "tags": draft.tag_list or draft.tags,
            "cta": draft.cta_text or draft.cta,
            "applied_changes": applied_changes,
            "lineage": draft.generation_context,
        }
        version = ContentDraftVersion(
            draft_id=draft.id,
            version=draft.version,
            regenerate_scope=created_from,
            draft_snapshot=snapshot,
        )
        self.db.add(version)
        self.db.commit()
        self.db.refresh(version)
        return version

    def create_review(self, draft: ContentDraft, account_id: int, result, llm_result) -> ReviewReport:
        """保存 Draft Review 结果。"""
        severity_score = {"LOW": 5, "MEDIUM": 15, "HIGH": 30}
        score = max(0, 100 - sum(severity_score[item.severity] for item in result.issues))
        report = ReviewReport(
            draft_id=draft.id,
            account_id=account_id,
            experiment_id=draft.experiment_id,
            review_type="DRAFT_REVIEW_V1",
            passed=result.overall_status == "PASS" and not result.revision_required,
            score=score,
            quality_score=score,
            evidence_usage_score=score,
            risk_level=max((item.severity for item in result.issues), default="LOW", key={"LOW": 0, "MEDIUM": 1, "HIGH": 2}.get),
            issues=[item.model_dump() for item in result.issues],
            suggestions=[item.suggestion for item in result.issues],
            data_facts=[{"evidence_refs": [item.model_dump() for item in result.cited_evidence_refs]}],
            inferences=[{"strategy_alignment": result.strategy_alignment, "evidence_grounding": result.evidence_grounding}],
            action_suggestions=[{"revision_required": result.revision_required}],
            summary=result.summary,
            status="SUCCESS",
            prompt_tokens=llm_result.usage.prompt_tokens,
            completion_tokens=llm_result.usage.completion_tokens,
            total_tokens=llm_result.usage.total_tokens,
            estimated_cost=Decimal(str(llm_result.estimated_cost)),
            raw_response_id=llm_result.raw_response_id,
        )
        self.db.add(report)
        self.db.commit()
        self.db.refresh(report)
        return report
