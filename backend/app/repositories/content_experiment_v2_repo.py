from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.account import AccountProfile
from app.models.competitors_analysis import CompetitorAnalysisReport
from app.models.content_experiment import ContentExperiment
from app.models.content_opportunity import ContentOpportunity
from app.models.experiment_metric_target import ExperimentMetricTarget
from app.models.experiment_variable import ExperimentVariable
from app.schemas.content_experiment_v2 import ExperimentCardCreate


class ContentExperimentV2Repository:
    """V2 内容实验数据库访问层。"""

    def __init__(self, db: Session):
        """初始化数据库会话。"""
        self.db = db

    def get_account(self, account_id: int) -> AccountProfile | None:
        """查询账号画像。"""
        return self.db.get(AccountProfile, account_id)

    def get_report(self, report_id: int) -> CompetitorAnalysisReport | None:
        """查询竞品分析报告。"""
        return self.db.get(CompetitorAnalysisReport, report_id)

    def list_opportunities(self, account_id: int, report_id: int | None, limit: int) -> list[ContentOpportunity]:
        """查询可用于生成实验的内容机会。"""
        stmt = select(ContentOpportunity).join(CompetitorAnalysisReport)
        stmt = stmt.where(CompetitorAnalysisReport.account_id == account_id)
        if report_id is not None:
            stmt = stmt.where(ContentOpportunity.report_id == report_id)
        stmt = stmt.order_by(ContentOpportunity.opportunity_score.desc(), ContentOpportunity.id.desc()).limit(limit * 2)
        return list(self.db.execute(stmt).scalars().all())

    def create_card(self, data: ExperimentCardCreate) -> ContentExperiment:
        """创建实验卡及其变量、指标目标。"""
        experiment_data = data.model_dump(exclude={"variables", "metric_targets"})
        experiment = ContentExperiment(**experiment_data)
        self.db.add(experiment)
        self.db.flush()

        variables = [
            ExperimentVariable(**item.model_copy(update={"experiment_id": experiment.id}).model_dump())
            for item in data.variables
        ]
        metric_targets = [
            ExperimentMetricTarget(**item.model_copy(update={"experiment_id": experiment.id}).model_dump())
            for item in data.metric_targets
        ]
        self.db.add_all([*variables, *metric_targets])
        self.db.commit()
        self.db.refresh(experiment)
        return experiment

    def get_experiment(self, experiment_id: int) -> ContentExperiment | None:
        """查询内容实验。"""
        return self.db.get(ContentExperiment, experiment_id)

    def list_experiments(self, account_id: int | None = None) -> list[ContentExperiment]:
        """查询实验列表。"""
        stmt = select(ContentExperiment)
        if account_id is not None:
            stmt = stmt.where(ContentExperiment.account_id == account_id)
        stmt = stmt.order_by(ContentExperiment.id.desc())
        return list(self.db.execute(stmt).scalars().all())

    def list_recent_experiments(self, account_id: int, limit: int = 20) -> list[ContentExperiment]:
        """查询最近实验，用于内容组合约束。"""
        stmt = (
            select(ContentExperiment)
            .where(ContentExperiment.account_id == account_id)
            .order_by(ContentExperiment.id.desc())
            .limit(limit)
        )
        return list(self.db.execute(stmt).scalars().all())

    def list_variables(self, experiment_id: int) -> list[ExperimentVariable]:
        """查询实验变量。"""
        stmt = select(ExperimentVariable).where(ExperimentVariable.experiment_id == experiment_id).order_by(ExperimentVariable.id)
        return list(self.db.execute(stmt).scalars().all())

    def list_metric_targets(self, experiment_id: int) -> list[ExperimentMetricTarget]:
        """查询实验指标目标。"""
        stmt = (
            select(ExperimentMetricTarget)
            .where(ExperimentMetricTarget.experiment_id == experiment_id)
            .order_by(ExperimentMetricTarget.id)
        )
        return list(self.db.execute(stmt).scalars().all())

    def approve(self, experiment: ContentExperiment) -> ContentExperiment:
        """审批候选实验。"""
        experiment.status = "APPROVED"
        self.db.commit()
        self.db.refresh(experiment)
        return experiment
