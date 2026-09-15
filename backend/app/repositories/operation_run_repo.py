from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.account import AccountProfile
from app.models.account_data_refresh_run import AccountDataRefreshRun
from app.models.account_data_source_config import AccountDataSourceConfig
from app.models.account_evidence_refresh_run import AccountEvidenceRefreshRun
from app.models.account_operation_run import AccountOperationRun
from app.models.competitors_analysis import CompetitorAnalysisReport
from app.models.content_opportunity import ContentOpportunity
from app.models.viral_note_breakdown import ViralNoteBreakdown


class OperationRunRepository:
    """Database access for readonly operation analysis runs."""

    def __init__(self, db: Session):
        self.db = db

    def create(self, payload: dict) -> AccountOperationRun:
        run = AccountOperationRun(**payload)
        self.db.add(run)
        self.db.commit()
        self.db.refresh(run)
        return run

    def update(self, run: AccountOperationRun, payload: dict) -> AccountOperationRun:
        for field, value in payload.items():
            setattr(run, field, value)
        self.db.commit()
        self.db.refresh(run)
        return run

    def get_by_id(self, run_id: int) -> AccountOperationRun | None:
        return self.db.get(AccountOperationRun, run_id)

    def list_by_account(self, account_id: int, limit: int = 20) -> list[AccountOperationRun]:
        stmt = (
            select(AccountOperationRun)
            .where(AccountOperationRun.account_id == account_id)
            .order_by(AccountOperationRun.created_at.desc(), AccountOperationRun.id.desc())
            .limit(limit)
        )
        return list(self.db.execute(stmt).scalars().all())

    def get_account(self, account_id: int) -> AccountProfile | None:
        return self.db.get(AccountProfile, account_id)

    def get_latest_data_refresh_run(self, account_id: int) -> AccountDataRefreshRun | None:
        stmt = (
            select(AccountDataRefreshRun)
            .where(AccountDataRefreshRun.account_id == account_id)
            .order_by(AccountDataRefreshRun.created_at.desc(), AccountDataRefreshRun.id.desc())
            .limit(1)
        )
        return self.db.execute(stmt).scalar_one_or_none()

    def get_data_refresh_run(self, run_id: int) -> AccountDataRefreshRun | None:
        return self.db.get(AccountDataRefreshRun, run_id)

    def get_latest_evidence_refresh_run(self, account_id: int) -> AccountEvidenceRefreshRun | None:
        stmt = (
            select(AccountEvidenceRefreshRun)
            .where(AccountEvidenceRefreshRun.account_id == account_id)
            .order_by(AccountEvidenceRefreshRun.created_at.desc(), AccountEvidenceRefreshRun.id.desc())
            .limit(1)
        )
        return self.db.execute(stmt).scalar_one_or_none()

    def get_evidence_refresh_run(self, run_id: int) -> AccountEvidenceRefreshRun | None:
        return self.db.get(AccountEvidenceRefreshRun, run_id)

    def get_report(self, report_id: int) -> CompetitorAnalysisReport | None:
        return self.db.get(CompetitorAnalysisReport, report_id)

    def list_opportunities(self, report_id: int) -> list[ContentOpportunity]:
        stmt = (
            select(ContentOpportunity)
            .where(ContentOpportunity.report_id == report_id)
            .order_by(ContentOpportunity.opportunity_score.desc(), ContentOpportunity.id.desc())
        )
        return list(self.db.execute(stmt).scalars().all())

    def list_viral_breakdowns(self, report_id: int) -> list[ViralNoteBreakdown]:
        stmt = (
            select(ViralNoteBreakdown)
            .where(ViralNoteBreakdown.report_id == report_id)
            .order_by(ViralNoteBreakdown.engagement_score.desc(), ViralNoteBreakdown.id.desc())
        )
        return list(self.db.execute(stmt).scalars().all())

    def get_data_source_config(self, account_id: int) -> AccountDataSourceConfig | None:
        stmt = (
            select(AccountDataSourceConfig)
            .where(AccountDataSourceConfig.account_id == account_id)
            .order_by(AccountDataSourceConfig.updated_at.desc(), AccountDataSourceConfig.id.desc())
            .limit(1)
        )
        return self.db.execute(stmt).scalar_one_or_none()
