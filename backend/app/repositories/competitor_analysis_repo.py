from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models.competitors_analysis import CompetitorAnalysisReport
from app.models.xhs_note import XhsNoteSnapshot


class CompetitorAnalysisRepository:
    """竞品分析数据库访问层。"""

    def __init__(self, db: Session):
        """初始化数据库会话。"""
        self.db = db

    def list_notes_for_analysis(
        self,
        source_type: str = "COMPETITOR",
        keyword: str | None = None,
        note_snapshot_ids: list[int] | None = None,
        limit: int = 30,
    ) -> list[XhsNoteSnapshot]:
        """查询参与竞品分析的笔记快照。"""
        stmt = select(XhsNoteSnapshot).where(XhsNoteSnapshot.status == "SUCCESS")

        if note_snapshot_ids:
            stmt = stmt.where(XhsNoteSnapshot.id.in_(note_snapshot_ids))
        else:
            stmt = stmt.where(XhsNoteSnapshot.source_type == source_type)
            if keyword:
                stmt = stmt.where(
                    or_(
                        XhsNoteSnapshot.keyword == keyword,
                        XhsNoteSnapshot.title.ilike(f"%{keyword}%"),
                        XhsNoteSnapshot.merged_text.ilike(f"%{keyword}%"),
                    )
                )

        stmt = stmt.order_by(XhsNoteSnapshot.id.desc()).limit(limit)
        return list(self.db.execute(stmt).scalars().all())

    def create(self, report: CompetitorAnalysisReport) -> CompetitorAnalysisReport:
        """保存竞品分析报告。"""
        self.db.add(report)
        self.db.commit()
        self.db.refresh(report)
        return report

    def get_by_id(self, report_id: int) -> CompetitorAnalysisReport | None:
        """根据 ID 查询竞品分析报告。"""
        return self.db.get(CompetitorAnalysisReport, report_id)

    def list_latest(self, limit: int = 20) -> list[CompetitorAnalysisReport]:
        """查询最新竞品分析报告。"""
        stmt = select(CompetitorAnalysisReport).order_by(CompetitorAnalysisReport.id.desc()).limit(limit)
        return list(self.db.execute(stmt).scalars().all())