from datetime import datetime

from sqlalchemy.orm import Session

from app.models.account import AccountProfile
from app.models.account_evidence_refresh_run import AccountEvidenceRefreshRun
from app.repositories.evidence_refresh_run_repo import EvidenceRefreshRunRepository
from app.schemas.competitor_report import CompetitorReportCreate
from app.schemas.evidence_refresh_run import EvidenceRefreshRunCreate, EvidenceRefreshRunResponse, EvidenceRefreshRunStatus
from app.services.competitor_report_sev import CompetitorReportService, DataAvailabilityError


class EvidenceRefreshRunService:
    """账号证据刷新运行服务，复用竞品报告服务生成证据结构。"""

    def __init__(self, db: Session):
        """初始化证据刷新服务。"""
        self.db = db
        self.repo = EvidenceRefreshRunRepository(db)
        self.report_service = CompetitorReportService(db)

    def create_run(self, data: EvidenceRefreshRunCreate) -> AccountEvidenceRefreshRun:
        """创建并执行一次证据刷新。"""
        self._ensure_account(data.account_id)
        data_refresh_status = self._validate_data_refresh_run(data.account_id, data.data_refresh_run_id)
        run = self.repo.create(
            {
                "account_id": data.account_id,
                "data_refresh_run_id": data.data_refresh_run_id,
                "trigger_type": "MANUAL",
                "status": EvidenceRefreshRunStatus.RUNNING.value,
                "keyword": data.keyword,
                "target_metric": data.target_metric,
                "limit": data.limit,
                "started_at": datetime.now(),
                "stats": {"data_refresh_run_status": data_refresh_status},
            }
        )

        try:
            report = self.report_service.create_report(self._report_create_payload(data))
            stats = self._report_stats(report.id, data_refresh_status)
            data_quality = stats.get("data_quality")
            status = EvidenceRefreshRunStatus.SUCCESS.value if data_quality == "READY" else EvidenceRefreshRunStatus.PARTIAL.value
            return self.repo.update(
                run,
                {
                    "report_id": report.id,
                    "status": status,
                    "stats": stats,
                    "finished_at": datetime.now(),
                },
            )
        except DataAvailabilityError as exc:
            payload = dict(exc.payload)
            return self.repo.update(
                run,
                {
                    "status": EvidenceRefreshRunStatus.DATA_INSUFFICIENT.value,
                    "stats": {**payload, "data_refresh_run_status": data_refresh_status},
                    "error_code": payload.get("reason") or "DATA_INSUFFICIENT",
                    "error_message": payload.get("message") or str(exc),
                    "finished_at": datetime.now(),
                },
            )
        except ValueError as exc:
            return self.repo.update(
                run,
                {
                    "status": EvidenceRefreshRunStatus.FAILED.value,
                    "error_code": "EVIDENCE_REFRESH_FAILED",
                    "error_message": str(exc),
                    "finished_at": datetime.now(),
                },
            )

    def list_runs(self, account_id: int, limit: int = 20) -> list[EvidenceRefreshRunResponse]:
        """查询账号最近证据刷新运行记录。"""
        self._ensure_account(account_id)
        return [self.to_response(run) for run in self.repo.list_by_account(account_id, limit=limit)]

    def get_run(self, run_id: int) -> EvidenceRefreshRunResponse:
        """查询证据刷新运行详情。"""
        run = self.repo.get_by_id(run_id)
        if not run:
            raise ValueError("evidence refresh run not found")
        return self.to_response(run)

    def to_response(self, run: AccountEvidenceRefreshRun) -> EvidenceRefreshRunResponse:
        """把运行记录转换为轻量响应。"""
        report = self.repo.get_report(run.report_id) if run.report_id else None
        stats = run.stats or {}
        return EvidenceRefreshRunResponse.model_validate(run).model_copy(
            update={
                "report_summary": report.summary if report else None,
                "note_count": report.note_count if report else int(stats.get("note_count") or 0),
                "comment_count": report.comment_count if report else int(stats.get("comment_count") or 0),
                "opportunity_count": int(stats.get("opportunity_count") or 0),
                "breakdown_count": int(stats.get("breakdown_count") or 0),
                "data_quality": stats.get("data_quality"),
                "hint": stats.get("hint"),
            }
        )

    def _ensure_account(self, account_id: int) -> None:
        """校验账号是否存在。"""
        if not self.db.get(AccountProfile, account_id):
            raise ValueError("account not found")

    def _validate_data_refresh_run(self, account_id: int, data_refresh_run_id: int | None) -> str | None:
        """校验可选的 B3 数据刷新记录归属。"""
        if data_refresh_run_id is None:
            return None
        run = self.repo.get_data_refresh_run(data_refresh_run_id)
        if not run:
            raise ValueError("data refresh run not found")
        if run.account_id != account_id:
            raise ValueError("data refresh run account_id does not match")
        return run.status

    def _report_create_payload(self, data: EvidenceRefreshRunCreate) -> CompetitorReportCreate:
        """构造竞品报告创建请求。"""
        return CompetitorReportCreate(
            account_id=data.account_id,
            name=data.name or "Evidence Refresh Report",
            keyword=data.keyword,
            target_metric=data.target_metric,
            limit=data.limit,
        )

    def _report_stats(self, report_id: int, data_refresh_status: str | None) -> dict:
        """读取报告轻量统计。"""
        report = self.report_service.get_report(report_id)
        breakdown_count = self.repo.count_breakdowns(report_id)
        opportunity_count = self.repo.count_opportunities(report_id)
        summary = report.replicability_summary or {}
        return {
            "report_id": report.id,
            "note_count": report.note_count,
            "comment_count": report.comment_count,
            "breakdown_count": breakdown_count,
            "opportunity_count": opportunity_count,
            "data_quality": summary.get("data_quality") or "UNKNOWN",
            "reason": summary.get("reason"),
            "hint": summary.get("hint"),
            "data_refresh_run_status": data_refresh_status,
        }
