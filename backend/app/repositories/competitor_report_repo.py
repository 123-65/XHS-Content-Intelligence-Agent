import re

from sqlalchemy import Text, and_, cast, func, or_, select
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
        stmt = (
            select(CompetitorAccount)
            .where(
                CompetitorAccount.account_id == account_id,
                CompetitorAccount.is_mock.is_(False),
            )
            .order_by(CompetitorAccount.id.desc())
        )
        return list(self.db.execute(stmt).scalars().all())

    def list_competitor_notes(self, account_id: int, keyword: str | None, limit: int) -> list[CompetitorNote]:
        """查询用于竞品报告的非 Mock 竞品笔记，支持 MCP、ReadOnly 和手动录入来源。"""
        stmt = select(CompetitorNote).where(
            CompetitorNote.account_id == account_id,
            CompetitorNote.is_mock.is_(False),
        )

        stmt = self._apply_keyword_filter(stmt, keyword)

        stmt = stmt.order_by(
            CompetitorNote.collect_count.desc().nullslast(),
            CompetitorNote.like_count.desc().nullslast(),
            CompetitorNote.id.desc(),
        ).limit(limit)

        return list(self.db.execute(stmt).scalars().all())

    def count_competitor_notes(self, account_id: int, keyword: str | None = None, is_mock: bool | None = None) -> int:
        """统计账号下竞品笔记数量，用于区分不同空数据原因。"""
        stmt = select(func.count()).select_from(CompetitorNote).where(CompetitorNote.account_id == account_id)
        if is_mock is not None:
            stmt = stmt.where(CompetitorNote.is_mock.is_(is_mock))
        stmt = self._apply_keyword_filter(stmt, keyword)
        return int(self.db.execute(stmt).scalar_one())

    def _apply_keyword_filter(self, stmt, keyword: str | None):
        """按关键词分词过滤标题、正文和标签。"""
        keyword_terms = self._keyword_terms(keyword)
        if not keyword_terms:
            return stmt
        searchable_fields = (
            CompetitorNote.title,
            CompetitorNote.content,
            cast(CompetitorNote.tags, Text),
        )
        return stmt.where(and_(*(self._matches_keyword_term(term, searchable_fields) for term in keyword_terms)))

    def _keyword_terms(self, keyword: str | None) -> list[str]:
        """拆分关键词，支持类似 'AI Agent' 的多词搜索。"""
        if not keyword:
            return []
        return [term for term in re.split(r"\s+", keyword.strip()) if term]

    def _matches_keyword_term(self, term: str, searchable_fields) -> object:
        """任一可搜索字段命中关键词分词即可。"""
        pattern = f"%{term}%"
        return or_(*(field.ilike(pattern) for field in searchable_fields))

    def list_comments_for_notes(self, account_id: int, note_ids: list[int]) -> list[CompetitorComment]:
        """查询竞品笔记下的评论样本。"""
        stmt = select(CompetitorComment).where(
            CompetitorComment.account_id == account_id,
            CompetitorComment.is_mock.is_(False),
        )
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
