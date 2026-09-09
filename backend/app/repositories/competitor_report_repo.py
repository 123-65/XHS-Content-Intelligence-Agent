from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.account import AccountProfile
from app.models.competitor_account import CompetitorAccount
from app.models.competitor_comment import CompetitorComment
from app.models.competitor_note import CompetitorNote
from app.models.competitors_analysis import CompetitorAnalysisReport
from app.models.content_opportunity import ContentOpportunity
from app.models.viral_note_breakdown import ViralNoteBreakdown


class CompetitorReportRepository:
    """V2 竞品分析报告数据库访问层。"""

    def __init__(self, db: Session):
        """初始化数据库会话。"""
        self.db = db

    def get_account(self, account_id: int) -> AccountProfile | None:
        """查询账号配置。"""
        return self.db.get(AccountProfile, account_id)

    def list_competitor_accounts(self, account_id: int) -> list[CompetitorAccount]:
        """查询账号下的同行账号快照。"""
        stmt = select(CompetitorAccount).where(CompetitorAccount.account_id == account_id).order_by(CompetitorAccount.id.desc())
        return list(self.db.execute(stmt).scalars().all())

    def list_competitor_notes(self, account_id: int, keyword: str | None, limit: int) -> list[CompetitorNote]:
        """查询账号下的竞品笔记快照。"""
        stmt = select(CompetitorNote).where(CompetitorNote.account_id == account_id)
        if keyword:
            stmt = stmt.where(CompetitorNote.title.ilike(f"%{keyword}%") | CompetitorNote.content.ilike(f"%{keyword}%"))
        stmt = stmt.order_by(CompetitorNote.id.desc()).limit(limit)
        return list(self.db.execute(stmt).scalars().all())

    def list_comments_for_notes(self, account_id: int, note_ids: list[int]) -> list[CompetitorComment]:
        """查询竞品笔记下的评论样本。"""
        stmt = select(CompetitorComment).where(CompetitorComment.account_id == account_id)
        if note_ids:
            stmt = stmt.where(CompetitorComment.competitor_note_id.in_(note_ids))
        return list(self.db.execute(stmt).scalars().all())

    def create_report_bundle(
        self,
        report: CompetitorAnalysisReport,
        breakdowns: list[ViralNoteBreakdown],
        opportunities: list[ContentOpportunity],
    ) -> CompetitorAnalysisReport:
        """保存报告、爆款拆解和内容机会。"""
        self.db.add(report)
        self.db.flush()
        for item in [*breakdowns, *opportunities]:
            item.report_id = report.id
        self.db.add_all([*breakdowns, *opportunities])
        self.db.commit()
        self.db.refresh(report)
        return report

    def get_report(self, report_id: int) -> CompetitorAnalysisReport | None:
        """查询竞品分析报告。"""
        return self.db.get(CompetitorAnalysisReport, report_id)

    def list_viral_breakdowns(self, report_id: int) -> list[ViralNoteBreakdown]:
        """查询报告下的爆款笔记拆解。"""
        stmt = (
            select(ViralNoteBreakdown)
            .where(ViralNoteBreakdown.report_id == report_id)
            .order_by(ViralNoteBreakdown.engagement_score.desc())
        )
        return list(self.db.execute(stmt).scalars().all())

    def list_opportunities(self, report_id: int) -> list[ContentOpportunity]:
        """查询报告下的内容机会。"""
        stmt = (
            select(ContentOpportunity)
            .where(ContentOpportunity.report_id == report_id)
            .order_by(ContentOpportunity.opportunity_score.desc())
        )
        return list(self.db.execute(stmt).scalars().all())
