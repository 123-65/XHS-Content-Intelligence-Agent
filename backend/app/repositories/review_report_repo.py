from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.account import AccountProfile
from app.models.content_draft import ContentDraft
from app.models.content_experiment import ContentExperiment
from app.models.review_report import ReviewReport
from app.schemas.review_report import ReviewReportCreate


class ReviewReportRepository:
    """内容审核报告数据库访问层。"""

    def __init__(self, db: Session):
        """初始化数据库会话。"""
        self.db = db

    def get_draft(self, draft_id: int) -> ContentDraft | None:
        """查询草稿。"""
        return self.db.get(ContentDraft, draft_id)

    def get_experiment(self, experiment_id: int) -> ContentExperiment | None:
        """查询内容实验。"""
        return self.db.get(ContentExperiment, experiment_id)

    def get_account(self, account_id: int) -> AccountProfile | None:
        """查询账号配置。"""
        return self.db.get(AccountProfile, account_id)

    def create(self, data: ReviewReportCreate) -> ReviewReport:
        """创建审核报告。"""
        report = ReviewReport(**data.model_dump())
        self.db.add(report)
        self.db.commit()
        self.db.refresh(report)
        return report

    def get_by_id(self, report_id: int) -> ReviewReport | None:
        """根据 ID 查询审核报告。"""
        return self.db.get(ReviewReport, report_id)

    def list_by_draft(self, draft_id: int) -> list[ReviewReport]:
        """查询某个草稿的审核报告列表。"""
        stmt = select(ReviewReport).where(ReviewReport.draft_id == draft_id).order_by(ReviewReport.id.desc())
        return list(self.db.execute(stmt).scalars().all())

    def update_draft_status(self, draft: ContentDraft, status: str) -> None:
        """更新草稿状态。"""
        draft.status = status
        self.db.commit()
