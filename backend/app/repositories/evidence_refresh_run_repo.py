from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.account_data_refresh_run import AccountDataRefreshRun
from app.models.account_evidence_refresh_run import AccountEvidenceRefreshRun
from app.models.competitors_analysis import CompetitorAnalysisReport
from app.models.content_opportunity import ContentOpportunity
from app.models.viral_note_breakdown import ViralNoteBreakdown


class EvidenceRefreshRunRepository:
    """证据刷新运行记录数据库访问层。"""

    def __init__(self, db: Session):
        """初始化数据库会话。"""
        self.db = db

    def create(self, payload: dict) -> AccountEvidenceRefreshRun:
        """创建证据刷新运行记录。"""
        run = AccountEvidenceRefreshRun(**payload)
        self.db.add(run)
        self.db.commit()
        self.db.refresh(run)
        return run

    def update(self, run: AccountEvidenceRefreshRun, payload: dict) -> AccountEvidenceRefreshRun:
        """更新证据刷新运行记录。"""
        for field, value in payload.items():
            setattr(run, field, value)
        self.db.commit()
        self.db.refresh(run)
        return run

    def get_by_id(self, run_id: int) -> AccountEvidenceRefreshRun | None:
        """按 ID 查询证据刷新运行记录。"""
        return self.db.get(AccountEvidenceRefreshRun, run_id)

    def list_by_account(self, account_id: int, limit: int = 20) -> list[AccountEvidenceRefreshRun]:
        """按账号查询最近证据刷新运行记录。"""
        stmt = (
            select(AccountEvidenceRefreshRun)
            .where(AccountEvidenceRefreshRun.account_id == account_id)
            .order_by(AccountEvidenceRefreshRun.created_at.desc(), AccountEvidenceRefreshRun.id.desc())
            .limit(limit)
        )
        return list(self.db.execute(stmt).scalars().all())

    def get_data_refresh_run(self, run_id: int) -> AccountDataRefreshRun | None:
        """查询 B3 数据刷新运行记录。"""
        return self.db.get(AccountDataRefreshRun, run_id)

    def get_report(self, report_id: int) -> CompetitorAnalysisReport | None:
        """查询竞品分析报告。"""
        return self.db.get(CompetitorAnalysisReport, report_id)

    def count_breakdowns(self, report_id: int) -> int:
        """统计报告下的爆款拆解数量。"""
        stmt = select(ViralNoteBreakdown).where(ViralNoteBreakdown.report_id == report_id)
        return len(self.db.execute(stmt).scalars().all())

    def count_opportunities(self, report_id: int) -> int:
        """统计报告下的内容机会数量。"""
        stmt = select(ContentOpportunity).where(ContentOpportunity.report_id == report_id)
        return len(self.db.execute(stmt).scalars().all())
