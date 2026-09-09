from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.account import AccountProfile
from app.models.competitors_analysis import CompetitorAnalysisReport
from app.models.content_draft import ContentDraft
from app.models.content_experiment import ContentExperiment
from app.schemas.content_draft import ContentDraftCreate


class ContentDraftRepository:
    """内容草稿数据库访问层。"""

    def __init__(self, db: Session):
        """初始化数据库会话。"""
        self.db = db

    def get_experiment(self, experiment_id: int) -> ContentExperiment | None:
        """查询内容实验。"""
        return self.db.get(ContentExperiment, experiment_id)

    def get_account(self, account_id: int) -> AccountProfile | None:
        """查询账号配置。"""
        return self.db.get(AccountProfile, account_id)

    def get_analysis_report(self, report_id: int) -> CompetitorAnalysisReport | None:
        """查询竞品分析报告。"""
        return self.db.get(CompetitorAnalysisReport, report_id)

    def get_latest_version(self, experiment_id: int) -> int:
        """查询某个实验下最新草稿版本号。"""
        stmt = (
            select(ContentDraft.version)
            .where(ContentDraft.experiment_id == experiment_id)
            .order_by(ContentDraft.version.desc())
            .limit(1)
        )
        return self.db.execute(stmt).scalar_one_or_none() or 0

    def create(self, data: ContentDraftCreate) -> ContentDraft:
        """创建内容草稿。"""
        draft = ContentDraft(**data.model_dump())
        self.db.add(draft)
        self.db.commit()
        self.db.refresh(draft)
        return draft

    def list_by_experiment(self, experiment_id: int) -> list[ContentDraft]:
        """查询某个实验下的草稿列表。"""
        stmt = (
            select(ContentDraft)
            .where(ContentDraft.experiment_id == experiment_id)
            .order_by(ContentDraft.version.desc())
        )
        return list(self.db.execute(stmt).scalars().all())

    def get_by_id(self, draft_id: int) -> ContentDraft | None:
        """根据 ID 查询内容草稿。"""
        return self.db.get(ContentDraft, draft_id)
