from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.account import AccountProfile
from app.models.competitors_analysis import CompetitorAnalysisReport
from app.models.content_experiment import ContentExperiment
from app.schemas.content_experiment import ContentExperimentCreate, ContentExperimentUpdate


class ContentExperimentRepository:
    """内容实验数据库访问层。"""

    def __init__(self, db: Session):
        """初始化数据库会话。"""
        self.db = db

    def get_account(self, account_id: int) -> AccountProfile | None:
        """查询账号配置。"""
        return self.db.get(AccountProfile, account_id)

    def get_analysis_report(self, report_id: int) -> CompetitorAnalysisReport | None:
        """查询竞品分析报告。"""
        return self.db.get(CompetitorAnalysisReport, report_id)

    def create(self, data: ContentExperimentCreate) -> ContentExperiment:
        """创建内容实验。"""
        experiment = ContentExperiment(**data.model_dump())
        self.db.add(experiment)
        self.db.commit()
        self.db.refresh(experiment)
        return experiment

    def get_by_id(self, experiment_id: int) -> ContentExperiment | None:
        """根据 ID 查询内容实验。"""
        return self.db.get(ContentExperiment, experiment_id)

    def list_latest(self, account_id: int | None = None, limit: int = 20) -> list[ContentExperiment]:
        """查询最新内容实验。"""
        stmt = select(ContentExperiment)
        filters = [ContentExperiment.account_id == account_id] if account_id is not None else []
        stmt = stmt.where(*filters).order_by(ContentExperiment.id.desc()).limit(limit)
        return list(self.db.execute(stmt).scalars().all())

    def update(self, experiment: ContentExperiment, data: ContentExperimentUpdate) -> ContentExperiment:
        """更新内容实验。"""
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(experiment, field, value)
        self.db.commit()
        self.db.refresh(experiment)
        return experiment
