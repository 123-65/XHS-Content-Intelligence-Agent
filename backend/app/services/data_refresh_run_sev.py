from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.account import AccountProfile
from app.models.account_data_source_config import AccountDataSourceConfig
from app.models.account_data_refresh_run import AccountDataRefreshRun
from app.repositories.data_refresh_run_repo import DataRefreshRunRepository
from app.schemas.crawler_collection import CrawlTaskCreate
from app.schemas.data_refresh_run import DataRefreshRunCreate, RefreshRunStatus
from app.services.crawler_collection_sev import CrawlerCollectionService


class DataRefreshProviderUnavailable(Exception):
    """数据刷新 Provider 未配置。"""


class DataRefreshRunService:
    """账号数据刷新运行服务，负责编排用户触发式刷新。"""

    def __init__(self, db: Session):
        """初始化刷新服务。"""
        self.db = db
        self.repo = DataRefreshRunRepository(db)

    def create_run(self, data: DataRefreshRunCreate) -> AccountDataRefreshRun:
        """创建并执行一次用户触发的数据刷新。"""
        self._ensure_account(data.account_id)
        configs = self._resolve_enabled_configs(data)
        stats = self._build_stats(configs)
        refresh_scope_days = self._refresh_scope_days(configs)
        selected_config_id = data.data_source_config_id or (configs[0].id if len(configs) == 1 else None)

        if not configs:
            now = datetime.now()
            return self.repo.create(
                {
                    "account_id": data.account_id,
                    "data_source_config_id": selected_config_id,
                    "trigger_type": data.trigger_type.value,
                    "status": RefreshRunStatus.FAILED.value,
                    "refresh_scope_days": refresh_scope_days,
                    "started_at": now,
                    "finished_at": now,
                    "stats": {**stats, "provider_status": "NO_ENABLED_DATA_SOURCE"},
                    "error_code": "NO_ENABLED_DATA_SOURCE",
                    "error_message": "请先保存并启用数据源配置。",
                }
            )

        run = self.repo.create(
            {
                "account_id": data.account_id,
                "data_source_config_id": selected_config_id,
                "trigger_type": data.trigger_type.value,
                "status": RefreshRunStatus.RUNNING.value,
                "refresh_scope_days": refresh_scope_days,
                "started_at": datetime.now(),
                "stats": stats,
            }
        )

        try:
            task = self._run_existing_provider_if_payload_available(data.account_id, configs, refresh_scope_days)
            next_stats = {**stats, "crawl_task_count": 1, "provider_status": task.status}
            status = RefreshRunStatus.SUCCESS.value if task.status == "SUCCESS" else RefreshRunStatus.PARTIAL.value
            return self.repo.update(run, {"status": status, "finished_at": datetime.now(), "stats": next_stats})
        except DataRefreshProviderUnavailable as exc:
            next_stats = {**stats, "provider_status": RefreshRunStatus.PROVIDER_NOT_CONFIGURED.value}
            return self.repo.update(
                run,
                {
                    "status": RefreshRunStatus.PROVIDER_NOT_CONFIGURED.value,
                    "finished_at": datetime.now(),
                    "stats": next_stats,
                    "error_code": "PROVIDER_NOT_CONFIGURED",
                    "error_message": str(exc),
                },
            )
        except Exception as exc:
            next_stats = {**stats, "provider_status": RefreshRunStatus.FAILED.value}
            return self.repo.update(
                run,
                {
                    "status": RefreshRunStatus.FAILED.value,
                    "finished_at": datetime.now(),
                    "stats": next_stats,
                    "error_code": "DATA_REFRESH_FAILED",
                    "error_message": str(exc),
                },
            )

    def list_runs(self, account_id: int | None = None, limit: int = 20) -> list[AccountDataRefreshRun]:
        """查询最近刷新运行记录。"""
        if account_id is not None:
            self._ensure_account(account_id)
        return self.repo.list(account_id=account_id, limit=limit)

    def get_run(self, run_id: int) -> AccountDataRefreshRun:
        """查询刷新运行详情。"""
        run = self.repo.get(run_id)
        if not run:
            raise ValueError("data refresh run not found")
        return run

    def _ensure_account(self, account_id: int) -> None:
        """校验账号画像是否存在。"""
        if not self.db.get(AccountProfile, account_id):
            raise ValueError("account not found")

    def _resolve_enabled_configs(self, data: DataRefreshRunCreate) -> list[AccountDataSourceConfig]:
        """读取本次刷新可用的 B2 数据源配置。"""
        if data.data_source_config_id:
            config = self.db.get(AccountDataSourceConfig, data.data_source_config_id)
            if not config or config.account_id != data.account_id:
                raise ValueError("data source config not found")
            return [config] if config.status == "ACTIVE" else []

        stmt = (
            select(AccountDataSourceConfig)
            .where(AccountDataSourceConfig.account_id == data.account_id, AccountDataSourceConfig.status == "ACTIVE")
            .order_by(AccountDataSourceConfig.updated_at.desc(), AccountDataSourceConfig.id.desc())
        )
        return list(self.db.execute(stmt).scalars().all())

    def _build_stats(self, configs: list[AccountDataSourceConfig]) -> dict[str, Any]:
        """统计本次刷新使用的数据源配置数量。"""
        return {
            "config_count": len(configs),
            "keyword_count": sum(self._enabled_count(config.keywords) for config in configs),
            "competitor_account_count": sum(self._enabled_count(config.competitor_accounts) for config in configs),
            "seed_url_count": sum(len(config.note_urls or []) for config in configs),
            "crawl_task_count": 0,
            "note_count": 0,
            "comment_count": 0,
            "provider_status": "PENDING" if configs else "NO_ENABLED_DATA_SOURCE",
        }

    def _refresh_scope_days(self, configs: list[AccountDataSourceConfig]) -> int:
        """从配置中解析刷新天数，默认只刷新当天。"""
        values = []
        for config in configs:
            value = (config.refresh_policy or {}).get("refresh_scope_days")
            if isinstance(value, int) and value > 0:
                values.append(value)
        return max(values) if values else 1

    def _enabled_count(self, items: list[dict] | None) -> int:
        """统计启用的数据源项数量。"""
        return sum(1 for item in items or [] if item.get("enabled", True))

    def _run_existing_provider_if_payload_available(
        self,
        account_id: int,
        configs: list[AccountDataSourceConfig],
        refresh_scope_days: int,
    ):
        """仅在配置中已有真实快照 payload 时复用现有 CrawlTask / Provider。"""
        payload = self._manual_or_public_snapshot_payload(configs)
        if not payload:
            raise DataRefreshProviderUnavailable("当前未配置真实数据刷新 Provider，本次仅创建刷新记录。")

        provider_name = "readonly_xhs" if payload.get("public_snapshot") else "manual_snapshot"
        task = CrawlerCollectionService(self.db).create_task(
            CrawlTaskCreate(
                account_id=account_id,
                task_type="DATA_REFRESH",
                provider_name=provider_name,
                input_payload={
                    **payload,
                    "refresh_scope_days": refresh_scope_days,
                    "data_source_config_ids": [config.id for config in configs],
                },
            )
        )
        return CrawlerCollectionService(self.db).run_task(task.id)

    def _manual_or_public_snapshot_payload(self, configs: list[AccountDataSourceConfig]) -> dict[str, Any]:
        """读取显式人工快照 payload；不会根据 URL 访问外部链接。"""
        for config in configs:
            metadata = config.metadata_payload or {}
            if isinstance(metadata.get("public_snapshot"), dict):
                return {"public_snapshot": metadata["public_snapshot"]}
            if any(isinstance(metadata.get(key), list) for key in ("accounts", "notes", "comments")):
                return {
                    "accounts": metadata.get("accounts") or [],
                    "notes": metadata.get("notes") or [],
                    "comments": metadata.get("comments") or [],
                }
        return {}
