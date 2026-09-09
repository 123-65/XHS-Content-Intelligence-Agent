from collections.abc import Iterable
from typing import Any

from sqlalchemy.orm import Session

from app.models.competitors_analysis import CompetitorAnalysisReport
from app.models.content_experiment import ContentExperiment
from app.repositories.content_experiment_repo import ContentExperimentRepository
from app.schemas.content_experiment import (
    ContentExperimentCreate,
    ContentExperimentUpdate,
    CreateExperimentFromAnalysisRequest,
)


ALLOWED_STATUS_TRANSITIONS: dict[str, set[str]] = {
    "DRAFT": {"READY", "FAILED"},
    "READY": {"PUBLISHED", "FAILED"},
    "PUBLISHED": {"METRICS_COLLECTED", "FAILED"},
    "METRICS_COLLECTED": {"ANALYZED", "FAILED"},
    "ANALYZED": set(),
    "FAILED": {"DRAFT"},
}

TARGET_VALUE_LABELS = {
    "like_count": "点赞数",
    "collect_count": "收藏数",
    "comment_count": "评论数",
    "lead_count": "私信线索数",
    "order_count": "订单数",
    "engagement_count": "互动数",
}


class ContentExperimentService:
    """内容实验业务服务。"""

    def __init__(self, db: Session):
        """初始化内容实验服务。"""
        self.repo = ContentExperimentRepository(db)

    def create_experiment(self, data: ContentExperimentCreate) -> ContentExperiment:
        """创建内容实验。"""
        self._ensure_account_exists(data.account_id)
        self._ensure_analysis_exists(data.analysis_report_id)
        return self.repo.create(data)

    def create_from_analysis(
        self,
        analysis_report_id: int,
        data: CreateExperimentFromAnalysisRequest,
    ) -> ContentExperiment:
        """基于竞品分析报告创建内容实验。"""
        self._ensure_account_exists(data.account_id)
        report = self._get_analysis_or_raise(analysis_report_id)

        topic = data.selected_topic or self._guess_topic_from_report(report)
        topic_angle = data.topic_angle or self._guess_angle_from_report(report)
        create_data = ContentExperimentCreate(
            account_id=data.account_id,
            analysis_report_id=analysis_report_id,
            experiment_name=data.experiment_name or f"{topic} 内容实验",
            hypothesis=self._build_hypothesis(report, topic_angle),
            target_metric=data.target_metric,
            expected_result=self._build_expected_result(data.target_values),
            topic_angle=topic_angle,
            selected_topic=topic,
            target_values=data.target_values,
            source_type="COMPETITOR_ANALYSIS",
        )
        return self.repo.create(create_data)

    def list_experiments(self, account_id: int | None = None, limit: int = 20) -> list[ContentExperiment]:
        """查询内容实验列表。"""
        return self.repo.list_latest(account_id=account_id, limit=limit)

    def get_experiment(self, experiment_id: int) -> ContentExperiment:
        """查询内容实验详情。"""
        experiment = self.repo.get_by_id(experiment_id)
        if experiment:
            return experiment
        raise ValueError("内容实验不存在")

    def update_experiment(self, experiment_id: int, data: ContentExperimentUpdate) -> ContentExperiment:
        """更新内容实验。"""
        experiment = self.get_experiment(experiment_id)
        self._ensure_status_transition(experiment.status, data.status)
        return self.repo.update(experiment, data)

    def _ensure_account_exists(self, account_id: int) -> None:
        """校验账号是否存在。"""
        if self.repo.get_account(account_id):
            return
        raise ValueError("账号配置不存在")

    def _ensure_analysis_exists(self, analysis_report_id: int | None) -> None:
        """校验竞品分析报告是否存在。"""
        if analysis_report_id is None or self.repo.get_analysis_report(analysis_report_id):
            return
        raise ValueError("竞品分析报告不存在")

    def _get_analysis_or_raise(self, analysis_report_id: int) -> CompetitorAnalysisReport:
        """查询竞品分析报告，不存在时抛出业务错误。"""
        report = self.repo.get_analysis_report(analysis_report_id)
        if report:
            return report
        raise ValueError("竞品分析报告不存在")

    def _ensure_status_transition(self, old_status: str, new_status: str | None) -> None:
        """校验实验状态流转。"""
        allowed_next_statuses = ALLOWED_STATUS_TRANSITIONS.get(old_status, set())
        is_valid = new_status is None or old_status == new_status or new_status in allowed_next_statuses
        if is_valid:
            return
        raise ValueError(f"实验状态不能从 {old_status} 变更为 {new_status}")

    def _guess_topic_from_report(self, report: CompetitorAnalysisReport) -> str:
        """根据竞品分析报告推测选题。"""
        return (
            self._first_item_value(report.high_performance_notes, "title", prefix="拆解：")
            or self._format_keyword_topic(report.keyword)
            or "小红书内容增长实验选题"
        )

    def _guess_angle_from_report(self, report: CompetitorAnalysisReport) -> str:
        """根据竞品分析报告推测内容角度。"""
        return (
            self._first_item_value(report.title_patterns, "pattern", prefix="采用「", suffix="」表达结构")
            or "基于竞品高表现内容进行选题测试"
        )

    def _build_hypothesis(self, report: CompetitorAnalysisReport, topic_angle: str) -> str:
        """生成实验假设。"""
        tag_text = "、".join(self._iter_item_values(report.top_tags, "tag", limit=3))
        topic_prefix = f"围绕 {tag_text} 话题，" if tag_text else ""
        return f"{topic_prefix}采用{topic_angle}，可能提升内容互动和后续转化表现。"

    def _build_expected_result(self, target_values: dict) -> str:
        """生成预期结果描述。"""
        parts = [f"{TARGET_VALUE_LABELS.get(key, key)} >= {value}" for key, value in target_values.items()]
        return "，".join(parts) or "预期该实验内容能够获得高于账号近期平均水平的互动表现。"

    def _first_item_value(
        self,
        items: Iterable[dict[str, Any]] | None,
        key: str,
        prefix: str = "",
        suffix: str = "",
    ) -> str | None:
        """读取列表字典里的第一个有效字段值。"""
        return next((f"{prefix}{value}{suffix}" for value in self._iter_item_values(items, key, limit=1)), None)

    def _iter_item_values(
        self,
        items: Iterable[dict[str, Any]] | None,
        key: str,
        limit: int,
    ) -> Iterable[str]:
        """按顺序提取列表字典中的有效字符串字段。"""
        return (str(item[key]) for item in list(items or [])[:limit] if item.get(key))

    def _format_keyword_topic(self, keyword: str | None) -> str | None:
        """根据关键词生成备选选题。"""
        return f"{keyword} 学习路线" if keyword else None
