from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.account import AccountProfile
from app.models.competitors_analysis import CompetitorAnalysisReport
from app.models.content_opportunity import ContentOpportunity
from app.models.content_strategy_artifact import ContentStrategyArtifact
from app.schemas.content_strategy import ContentStrategyResult


class ContentStrategyRepository:
    """Content Strategy Artifact 及其派生 Opportunity 的唯一持久化 Owner。"""

    def __init__(self, db: Session):
        """保存数据库会话。"""
        self.db = db

    def get_account(self, account_id: int) -> AccountProfile | None:
        """读取账号。"""
        return self.db.get(AccountProfile, account_id)

    def get_report(self, report_id: int) -> CompetitorAnalysisReport | None:
        """读取 Research Artifact。"""
        return self.db.get(CompetitorAnalysisReport, report_id)

    def get_opportunity(self, opportunity_id: int) -> ContentOpportunity | None:
        """读取内容机会 Artifact。"""
        return self.db.get(ContentOpportunity, opportunity_id)

    def get_strategy_artifact(self, artifact_id: int) -> ContentStrategyArtifact | None:
        """按稳定主键读取 Content Strategy Artifact。"""
        return self.db.get(ContentStrategyArtifact, artifact_id)

    def list_strategies_by_account(self, account_id: int, offset: int, limit: int) -> tuple[list[ContentStrategyArtifact], int]:
        """按账号分页读取内容策略索引。"""
        total = self.db.execute(
            select(func.count()).select_from(ContentStrategyArtifact).where(ContentStrategyArtifact.account_id == account_id)
        ).scalar_one()
        statement = (
            select(ContentStrategyArtifact)
            .where(ContentStrategyArtifact.account_id == account_id)
            .order_by(ContentStrategyArtifact.created_at.desc(), ContentStrategyArtifact.id.desc())
            .offset(offset).limit(limit)
        )
        return list(self.db.execute(statement).scalars().all()), int(total)

    def list_strategy_opportunities(self, artifact_id: int) -> list[ContentOpportunity]:
        """只按主键升序读取属于指定 Strategy 的派生 Opportunity。"""
        statement = (
            select(ContentOpportunity)
            .where(ContentOpportunity.strategy_artifact_id == artifact_id)
            .order_by(ContentOpportunity.id.asc())
        )
        return list(self.db.execute(statement).scalars().all())

    def get_strategy_opportunity(self, opportunity_id: int) -> ContentOpportunity | None:
        """读取 Strategy Generated Opportunity，拒绝 Research 原始 Opportunity。"""
        item = self.get_opportunity(opportunity_id)
        return item if item is not None and item.strategy_artifact_id is not None else None

    def to_opportunity_result(self, item: ContentOpportunity) -> "ContentOpportunityResult":
        """复用持久化映射的逆向语义，构造正式 Opportunity 合同。"""
        from app.schemas.content_strategy import ContentOpportunityResult

        if item.strategy_artifact_id is None or item.source_opportunity_id is None:
            raise ValueError("Research Opportunity 不能作为 Strategy Generated Opportunity 返回")
        return ContentOpportunityResult(
            source_opportunity_id=item.source_opportunity_id,
            topic=item.opportunity_title,
            angle=item.suggested_angle,
            target_audience=item.target_audience,
            content_goal=item.content_goal,
            why_now=item.why_now,
            evidence_refs=item.evidence_refs,
            suggested_hook=item.suggested_hook,
            constraints=item.constraints,
        )

    def list_opportunities(self, report_id: int, limit: int) -> list[ContentOpportunity]:
        """按得分读取 Research Artifact 下的内容机会。"""
        statement = (
            select(ContentOpportunity)
            .where(ContentOpportunity.report_id == report_id)
            .order_by(ContentOpportunity.opportunity_score.desc(), ContentOpportunity.id.desc())
            .limit(limit)
        )
        return list(self.db.execute(statement).scalars().all())

    def create_strategy_artifact(self, result: ContentStrategyResult) -> ContentStrategyArtifact:
        """在当前事务中创建 Strategy Artifact，由 Bundle 入口统一提交。"""
        artifact = ContentStrategyArtifact(
            account_id=result.account_id,
            research_artifact_id=result.research_report_id,
            strategy_goal=result.strategy_goal,
            target_audience=result.target_audience,
            content_directions=[item.model_dump(mode="json") for item in result.content_directions],
            rationale=result.rationale,
            evidence_refs=[item.model_dump(mode="json") for item in result.evidence_refs],
            applicable_constraints=result.applicable_constraints,
            provider=result.provider,
            model=result.model,
        )
        self.db.add(artifact)
        self.db.flush()
        return artifact

    def create_strategy_bundle(
        self,
        result: ContentStrategyResult,
    ) -> tuple[ContentStrategyArtifact, list[ContentOpportunity]]:
        """校验账号与 Research lineage，原子保存 Strategy Artifact 及本轮派生 Opportunity。"""
        account = self.get_account(result.account_id)
        if account is None:
            raise ValueError("账号配置不存在")
        report = self.get_report(result.research_report_id)
        if report is None:
            raise ValueError("Research Artifact 不存在")
        if report.account_id != result.account_id:
            raise ValueError("Research Artifact 不属于当前账号")

        source_by_id: dict[int, ContentOpportunity] = {}
        for item in result.opportunities:
            source = self.get_opportunity(item.source_opportunity_id)
            if source is None:
                raise ValueError(f"Source Opportunity 不存在: {item.source_opportunity_id}")
            if source.report_id != result.research_report_id:
                raise ValueError("Source Opportunity 不属于当前 Research Artifact")
            if source.strategy_artifact_id is not None:
                raise ValueError("Strategy Opportunity 不能继续作为派生 Source")
            source_by_id[source.id] = source

        try:
            artifact = self.create_strategy_artifact(result)
            generated = [
                self._strategy_opportunity(artifact, source_by_id[item.source_opportunity_id], item, result)
                for item in result.opportunities
            ]
            self.db.add_all(generated)
            self.db.flush()
            self.db.refresh(artifact)
            for item in generated:
                self.db.refresh(item)
            return artifact, generated
        except Exception:
            raise

    def _strategy_opportunity(
        self,
        artifact: ContentStrategyArtifact,
        source: ContentOpportunity,
        generated,
        result: ContentStrategyResult,
    ) -> ContentOpportunity:
        """按冻结映射复制 Research 字段并补充 Strategy 增量语义。"""
        if artifact.research_artifact_id != source.report_id:
            raise ValueError("Strategy Artifact 与 Source Opportunity 的 Research lineage 不一致")
        return ContentOpportunity(
            report_id=source.report_id,
            strategy_artifact_id=artifact.id,
            source_opportunity_id=source.id,
            opportunity_title=source.opportunity_title,
            suggested_angle=source.suggested_angle,
            target_audience=source.target_audience or result.target_audience,
            content_pillar=source.content_pillar,
            comment_demand_type=source.comment_demand_type,
            evidence_summary=source.evidence_summary,
            replicability_score=source.replicability_score,
            risk_level=source.risk_level,
            risk_points=list(source.risk_points or []),
            opportunity_score=source.opportunity_score,
            content_goal=generated.content_goal,
            why_now=generated.why_now,
            suggested_hook=generated.suggested_hook,
            evidence_refs=[item.model_dump(mode="json") for item in generated.evidence_refs],
            constraints=list(generated.constraints),
        )
