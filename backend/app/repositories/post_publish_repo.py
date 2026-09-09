from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.account import AccountProfile
from app.models.content_draft import ContentDraft
from app.models.content_experiment import ContentExperiment
from app.models.content_optimization_plan import ContentOptimizationPlan
from app.models.memory_evidence import MemoryEvidence
from app.models.note_comment_snapshot import NoteCommentSnapshot
from app.models.private_conversion_snapshot import PrivateConversionSnapshot
from app.models.public_metric_snapshot import PublicMetricSnapshot
from app.models.published_note import PublishedNote
from app.models.review_report import ReviewReport
from app.models.strategy_memory import StrategyMemory


class PostPublishRepository:
    """发布后数据闭环的数据库访问层。"""

    def __init__(self, db: Session):
        """初始化发布后数据仓储。"""
        self.db = db

    def get_account(self, account_id: int) -> AccountProfile | None:
        """根据 ID 查询账号画像。"""
        return self.db.get(AccountProfile, account_id)

    def get_experiment(self, experiment_id: int) -> ContentExperiment | None:
        """根据 ID 查询内容实验。"""
        return self.db.get(ContentExperiment, experiment_id)

    def get_draft(self, draft_id: int) -> ContentDraft | None:
        """根据 ID 查询内容草稿。"""
        return self.db.get(ContentDraft, draft_id)

    def get_published_note(self, published_note_id: int) -> PublishedNote | None:
        """根据 ID 查询已发布笔记。"""
        return self.db.get(PublishedNote, published_note_id)

    def get_review_report(self, review_report_id: int) -> ReviewReport | None:
        """根据 ID 查询复盘报告。"""
        return self.db.get(ReviewReport, review_report_id)

    def create_published_note(self, fields: dict) -> PublishedNote:
        """创建已发布笔记记录。"""
        note = PublishedNote(**fields)
        self.db.add(note)
        self.db.commit()
        self.db.refresh(note)
        return note

    def update_status(self, obj, status: str) -> None:
        """更新数据库对象的状态字段。"""
        obj.status = status
        self.db.commit()

    def create_public_metric_snapshot(self, fields: dict) -> PublicMetricSnapshot:
        """创建公开指标快照。"""
        snapshot = PublicMetricSnapshot(**fields)
        self.db.add(snapshot)
        self.db.commit()
        self.db.refresh(snapshot)
        return snapshot

    def list_public_metrics(self, published_note_id: int) -> list[PublicMetricSnapshot]:
        """按已发布笔记查询公开指标快照。"""
        stmt = (
            select(PublicMetricSnapshot)
            .where(PublicMetricSnapshot.published_note_id == published_note_id)
            .order_by(PublicMetricSnapshot.collected_at.desc(), PublicMetricSnapshot.id.desc())
        )
        return list(self.db.execute(stmt).scalars().all())

    def create_private_conversion_snapshot(self, fields: dict) -> PrivateConversionSnapshot:
        """创建私域转化快照。"""
        snapshot = PrivateConversionSnapshot(**fields)
        self.db.add(snapshot)
        self.db.commit()
        self.db.refresh(snapshot)
        return snapshot

    def list_private_conversions(self, published_note_id: int) -> list[PrivateConversionSnapshot]:
        """按已发布笔记查询私域转化快照。"""
        stmt = (
            select(PrivateConversionSnapshot)
            .where(PrivateConversionSnapshot.published_note_id == published_note_id)
            .order_by(PrivateConversionSnapshot.collected_at.desc(), PrivateConversionSnapshot.id.desc())
        )
        return list(self.db.execute(stmt).scalars().all())

    def list_note_comments(self, published_note_id: int) -> list[NoteCommentSnapshot]:
        """按已发布笔记查询评论快照。"""
        stmt = (
            select(NoteCommentSnapshot)
            .where(NoteCommentSnapshot.published_note_id == published_note_id)
            .order_by(NoteCommentSnapshot.collected_at.desc(), NoteCommentSnapshot.id.desc())
        )
        return list(self.db.execute(stmt).scalars().all())

    def create_review_report(self, fields: dict) -> ReviewReport:
        """创建发布后复盘报告。"""
        report = ReviewReport(**fields)
        self.db.add(report)
        self.db.commit()
        self.db.refresh(report)
        return report

    def create_strategy_memory(self, memory_fields: dict, evidence_items: list[dict]) -> StrategyMemory:
        """创建策略记忆并写入证据明细。"""
        memory = StrategyMemory(**memory_fields)
        self.db.add(memory)
        self.db.flush()
        rows = [MemoryEvidence(memory_id=memory.id, **item) for item in evidence_items]
        self.db.add_all(rows)
        memory.evidence_count = len(rows)
        self.db.commit()
        self.db.refresh(memory)
        return memory

    def list_memories(self, account_id: int) -> list[StrategyMemory]:
        """按账号查询策略记忆。"""
        stmt = (
            select(StrategyMemory)
            .where(StrategyMemory.account_id == account_id)
            .order_by(StrategyMemory.created_at.desc(), StrategyMemory.id.desc())
        )
        return list(self.db.execute(stmt).scalars().all())

    def create_optimization_plan(self, fields: dict) -> ContentOptimizationPlan:
        """创建内容优化计划。"""
        plan = ContentOptimizationPlan(**fields)
        self.db.add(plan)
        self.db.commit()
        self.db.refresh(plan)
        return plan

    def list_recent_reviews(self, account_id: int, limit: int = 10) -> list[ReviewReport]:
        """查询账号最近的发布后复盘报告。"""
        stmt = (
            select(ReviewReport)
            .where(ReviewReport.account_id == account_id, ReviewReport.review_type == "POST_PUBLISH_REVIEW")
            .order_by(ReviewReport.created_at.desc(), ReviewReport.id.desc())
            .limit(limit)
        )
        return list(self.db.execute(stmt).scalars().all())

    def update_plan_applied(self, plan: ContentOptimizationPlan, generated_experiment_id: int | None) -> ContentOptimizationPlan:
        """将内容优化计划标记为已应用。"""
        plan.status = "APPLIED"
        plan.generated_experiment_id = generated_experiment_id
        plan.applied_at = datetime.now(UTC).replace(tzinfo=None)
        self.db.commit()
        self.db.refresh(plan)
        return plan

    def create_experiment(self, fields: dict) -> ContentExperiment:
        """为下一轮优化创建候选内容实验。"""
        experiment = ContentExperiment(**fields)
        self.db.add(experiment)
        self.db.commit()
        self.db.refresh(experiment)
        return experiment
