from decimal import Decimal
import re

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.account import AccountProfile
from app.models.content_draft import ContentDraft
from app.models.content_draft_version import ContentDraftVersion
from app.models.private_conversion_snapshot import PrivateConversionSnapshot
from app.models.public_metric_snapshot import PublicMetricSnapshot
from app.models.publish_package import PublishPackage
from app.models.published_note import PublishedNote
from app.models.review_report import ReviewReport
from app.models.strategy_memory import StrategyMemory
from app.models.strategy_candidate import StrategyCandidate as StrategyCandidateRecord
from app.schemas.publication import StrategyCandidate


class PublicationRepository:
    """人工发布、指标、复盘和记忆的统一持久化边界。"""

    def __init__(self, db: Session):
        """保存数据库会话。"""
        self.db = db

    def get_account(self, object_id: int):
        """读取账号。"""
        return self.db.get(AccountProfile, object_id)

    def get_draft(self, object_id: int):
        """读取 Draft。"""
        return self.db.get(ContentDraft, object_id)

    def get_draft_version(self, object_id: int):
        """按 canonical identity 读取不可变 Draft Version。"""
        return self.db.get(ContentDraftVersion, object_id)

    def get_package(self, object_id: int):
        """读取 Publish Package。"""
        return self.db.get(PublishPackage, object_id)

    def get_note(self, object_id: int):
        """读取 Published Note。"""
        return self.db.get(PublishedNote, object_id)

    def list_notes_by_account(self, account_id: int, offset: int, limit: int):
        """按账号分页读取已发布内容及其版本摘要。"""
        total = self.db.execute(
            select(func.count()).select_from(PublishedNote).where(PublishedNote.account_id == account_id)
        ).scalar_one()
        statement = (
            select(PublishedNote, ContentDraft, ContentDraftVersion)
            .join(ContentDraft, ContentDraft.id == PublishedNote.draft_id)
            .outerjoin(ContentDraftVersion, ContentDraftVersion.id == PublishedNote.draft_version_id)
            .where(PublishedNote.account_id == account_id)
            .order_by(PublishedNote.published_at.desc().nullslast(), PublishedNote.id.desc())
            .offset(offset).limit(limit)
        )
        return list(self.db.execute(statement).all()), int(total)

    def list_reviews_by_account(self, account_id: int, offset: int, limit: int):
        """按账号分页读取已绑定发布笔记的复盘报告。"""
        predicate = (ReviewReport.account_id == account_id, ReviewReport.published_note_id.is_not(None))
        total = self.db.execute(select(func.count()).select_from(ReviewReport).where(*predicate)).scalar_one()
        statement = (
            select(ReviewReport)
            .where(*predicate)
            .order_by(ReviewReport.created_at.desc(), ReviewReport.id.desc())
            .offset(offset).limit(limit)
        )
        return list(self.db.execute(statement).scalars().all()), int(total)

    def list_notes_published_between(self, account_id: int, start, end):
        """按账号与半开发布时间窗口确定性读取 Published Note。"""
        statement = (
            select(PublishedNote)
            .where(
                PublishedNote.account_id == account_id,
                PublishedNote.published_at >= start,
                PublishedNote.published_at < end,
            )
            .order_by(PublishedNote.published_at.asc(), PublishedNote.id.asc())
        )
        return list(self.db.execute(statement).scalars().all())

    def get_latest_published_note(self, account_id: int):
        """仅为明确 latest 语义读取账号最近一条 Published Note。"""
        statement = (
            select(PublishedNote)
            .where(PublishedNote.account_id == account_id, PublishedNote.published_at.is_not(None))
            .order_by(PublishedNote.published_at.desc(), PublishedNote.id.desc())
            .limit(1)
        )
        return self.db.execute(statement).scalar_one_or_none()

    def resolve_published_binding(self, note: PublishedNote) -> dict:
        """解析并交叉校验 PublishedNote 与 PublishPackage 的版本绑定。"""
        raw = note.raw_snapshot or {}
        canonical_version_id = getattr(note, "draft_version_id", None)
        if canonical_version_id is not None:
            version = self.get_draft_version(canonical_version_id)
            package_ref = raw.get("publish_package_id")
            package = self.get_package(int(package_ref)) if package_ref else None
            if version is None or version.draft_id != note.draft_id:
                raise ValueError("PUBLISHED_VERSION_LINEAGE_MISMATCH")
            if package is not None and (package.draft_id != note.draft_id or package.draft_version_id != canonical_version_id):
                raise ValueError("PUBLISHED_VERSION_LINEAGE_MISMATCH")
            return {"binding_ref": f"draft:{note.draft_id}:v{version.version}", "draft_ref": note.draft_id, "version_number": version.version, "publish_package_ref": int(package_ref) if package_ref else None}
        binding = raw.get("draft_version_ref")
        package_ref = raw.get("publish_package_id")
        if not binding:
            return {"binding_ref": None, "draft_ref": note.draft_id, "version_number": None, "publish_package_ref": int(package_ref) if package_ref else None}
        match = re.fullmatch(r"draft:(\d+):v(\d+)", str(binding))
        if match is None:
            raise ValueError("INVALID_PUBLISHED_DRAFT_BINDING")
        draft_ref, version_number = (int(value) for value in match.groups())
        if draft_ref != note.draft_id:
            raise ValueError("PUBLISHED_VERSION_LINEAGE_MISMATCH")
        if package_ref:
            package = self.get_package(int(package_ref))
            if package is None or package.draft_id != note.draft_id:
                raise ValueError("PUBLISHED_VERSION_LINEAGE_MISMATCH")
            package_binding = (package.stats or {}).get("draft_version_ref")
            if package_binding and package_binding != binding:
                raise ValueError("PUBLISHED_VERSION_LINEAGE_MISMATCH")
        return {"binding_ref": binding, "draft_ref": draft_ref, "version_number": version_number, "publish_package_ref": int(package_ref) if package_ref else None}

    def get_review(self, object_id: int):
        """读取 Review Report。"""
        return self.db.get(ReviewReport, object_id)

    def get_strategy_candidate(self, object_id: int):
        """按稳定数据库标识读取策略候选。"""
        return self.db.get(StrategyCandidateRecord, object_id)

    def list_strategy_candidates(self, review_report_id: int):
        """读取指定发布后复盘派生的全部持久化策略候选。"""
        statement = (
            select(StrategyCandidateRecord)
            .where(StrategyCandidateRecord.review_report_id == review_report_id)
            .order_by(StrategyCandidateRecord.id)
        )
        return list(self.db.execute(statement).scalars().all())

    def get_post_publish_review(self, note_id: int):
        """读取 Published Note 最新正式发布后复盘。"""
        statement = (
            select(ReviewReport)
            .where(
                ReviewReport.published_note_id == note_id,
                ReviewReport.review_type == "POST_PUBLISH_REVIEW_V1",
            )
            .order_by(ReviewReport.created_at.desc(), ReviewReport.id.desc())
            .limit(1)
        )
        return self.db.execute(statement).scalar_one_or_none()

    def create_strategy_candidate(
        self,
        *,
        account_id: int,
        review_report_id: int,
        candidate: StrategyCandidate,
    ) -> StrategyCandidateRecord:
        """从 Review 快照创建状态固定为 PROPOSED 的稳定策略候选。"""
        report = self.get_review(review_report_id)
        if (
            report is None
            or report.account_id != account_id
            or report.review_type != "POST_PUBLISH_REVIEW_V1"
        ):
            raise ValueError("PostPublishReview 不存在或不属于当前账号")
        if candidate.status != "PROPOSED":
            raise ValueError("Strategy Candidate 创建状态必须为 PROPOSED")

        candidate_payload = candidate.model_dump(mode="json")
        source = next(
            (
                item
                for item in (report.action_suggestions or [])
                if item.get("candidate_index") == candidate.candidate_index
            ),
            None,
        )
        comparable_fields = (
            "statement",
            "scope",
            "supporting_refs",
            "contradicting_refs",
            "confidence_context",
        )
        if source is None or any(source.get(field) != candidate_payload[field] for field in comparable_fields):
            raise ValueError("Strategy Candidate 内容不属于当前 PostPublishReview")

        record = StrategyCandidateRecord(
            review_report_id=report.id,
            account_id=account_id,
            source_candidate_index=candidate.candidate_index,
            statement=candidate.statement,
            scope=candidate.scope,
            supporting_refs=candidate_payload["supporting_refs"],
            contradicting_refs=candidate_payload["contradicting_refs"],
            confidence_context=candidate.confidence_context,
            status="PROPOSED",
        )
        try:
            self.db.add(record)
            self.db.flush()
            self.db.refresh(record)
            return record
        except Exception:
            raise

    def create_package(self, account_id: int, draft: ContentDraft, version: ContentDraftVersion, notes: str | None):
        """创建仅用于人工发布的内容包。"""
        snapshot = version.draft_snapshot or {}
        package = PublishPackage(
            account_id=account_id,
            draft_id=draft.id,
            draft_version_id=version.id,
            version_number=version.version,
            source_type="FINAL_DRAFT_VERSION",
            status="READY",
            title=snapshot.get("title", ""),
            body=snapshot.get("body", ""),
            tags=snapshot.get("tags") or [],
            cta=snapshot.get("cta"),
            manual_publish_steps=["复制内容", "用户在小红书手动发布", "回到系统绑定真实 Note URL"],
            stats={"draft_version_ref": f"draft:{draft.id}:v{version.version}", "optional_publish_notes": notes, "auto_publish": False},
        )
        self.db.add(package)
        self.db.commit()
        self.db.refresh(package)
        return package

    def create_published_note(self, package, draft, note_url, published_at):
        """建立 Draft Version 与真实平台笔记的绑定。"""
        note = PublishedNote(
            account_id=package.account_id,
            experiment_id=draft.experiment_id,
            draft_id=draft.id,
            draft_version_id=package.draft_version_id,
            publish_url=note_url,
            platform="xhs",
            status="PUBLISHED",
            source_type="USER_BOUND",
            published_at=published_at,
            raw_snapshot={
                "publish_package_id": package.id,
                "draft_version_ref": f"draft:{draft.id}:v{package.version_number}",
                "platform_note_id": self._platform_note_id(note_url),
                "registration_source": "USER_PROVIDED",
            },
        )
        self.db.add(note)
        self.db.commit()
        self.db.refresh(note)
        return note

    @staticmethod
    def _platform_note_id(note_url: str) -> str | None:
        """从用户提交 URL 中提取显示标识，不执行外部平台调用。"""
        match = re.search(r"/(?:explore|discovery/item)/([^/?#]+)", note_url)
        return match.group(1) if match else None

    def create_public_metrics(self, note_id, window, metrics, source, raw):
        """新增一条不覆盖历史的公开指标快照。"""
        snapshot = PublicMetricSnapshot(
            published_note_id=note_id,
            snapshot_window=window.label,
            view_count=metrics.get("view_count", 0),
            like_count=metrics.get("like_count", 0),
            collect_count=metrics.get("collect_count", 0),
            comment_count=metrics.get("comment_count", 0),
            share_count=metrics.get("share_count", 0),
            follow_count=metrics.get("follow_count", 0),
            profile_visit_count=metrics.get("profile_visit_count", 0),
            source_type="XHS_MCP",
            confidence=Decimal("1"),
            raw_snapshot={**raw, "window_start": window.window_start.isoformat(), "window_end": window.window_end.isoformat(), "provenance": "MEASURED", "source": source},
        )
        self.db.add(snapshot)
        self.db.commit()
        self.db.refresh(snapshot)
        return snapshot

    def create_private_metrics(self, data):
        """按用户实际提供的字段新增私域指标快照。"""
        provided = {name: getattr(data, name) for name in ("dm_count", "wechat_add_count", "consultation_count", "deal_count", "revenue") if getattr(data, name) is not None}
        snapshot = PrivateConversionSnapshot(
            account_id=data.account_id,
            published_note_id=data.published_note_ref,
            snapshot_window=data.window.label,
            dm_count=data.dm_count or 0,
            wechat_add_count=data.wechat_add_count or 0,
            consultation_count=data.consultation_count or 0,
            deal_count=data.deal_count or 0,
            revenue_amount=data.revenue or 0,
            source_type="USER_ATTRIBUTED",
            confidence=Decimal("1"),
            raw_snapshot={"provided_fields": list(provided), "values": {key: str(value) for key, value in provided.items()}, "window_start": data.window.window_start.isoformat(), "window_end": data.window.window_end.isoformat(), "provenance": "USER_ATTRIBUTED"},
        )
        self.db.add(snapshot)
        self.db.commit()
        self.db.refresh(snapshot)
        return snapshot

    def list_public_metrics(self, note_id: int):
        """按时间正序读取公开指标快照。"""
        return list(self.db.execute(select(PublicMetricSnapshot).where(PublicMetricSnapshot.published_note_id == note_id).order_by(PublicMetricSnapshot.collected_at)).scalars().all())

    def list_private_metrics(self, note_id: int):
        """按时间正序读取用户归因的私域快照。"""
        return list(self.db.execute(select(PrivateConversionSnapshot).where(PrivateConversionSnapshot.published_note_id == note_id).order_by(PrivateConversionSnapshot.collected_at)).scalars().all())

    def list_strategy_memories(self, account_id: int):
        """读取账号已经确认的长期策略记忆。"""
        statement = (
            select(StrategyMemory)
            .where(
                StrategyMemory.account_id == account_id,
                StrategyMemory.status == "VALIDATED",
            )
            .order_by(StrategyMemory.updated_at.desc(), StrategyMemory.id.desc())
        )
        return list(self.db.execute(statement).scalars().all())

    def create_post_review(self, note, account_id, result, llm_result=None, metadata=None):
        """保存观察、解释和 PROPOSED Candidate 快照，并兼容显式生成元数据。"""
        generation = metadata or llm_result
        if generation is None:
            raise ValueError("PostPublishReview 持久化缺少生成元数据")
        usage = getattr(generation, "usage", generation)
        candidates = [item.model_copy(update={"created_from_review": None}).model_dump(mode="json") for item in result.strategy_candidates]
        report = ReviewReport(
            draft_id=note.draft_id,
            account_id=account_id,
            experiment_id=note.experiment_id,
            published_note_id=note.id,
            review_type="POST_PUBLISH_REVIEW_V1",
            passed=True,
            summary=result.public_performance_analysis,
            status="SUCCESS",
            data_facts=[{"observed_results": result.observed_results, "evidence_refs": [item.model_dump() for item in result.evidence_refs]}],
            inferences=[{"strategy_alignment": result.strategy_alignment, "what_worked": result.what_worked, "what_did_not_work": result.what_did_not_work, "uncertainties": result.uncertainties}],
            action_suggestions=candidates,
            prompt_tokens=usage.prompt_tokens,
            completion_tokens=usage.completion_tokens,
            total_tokens=usage.total_tokens,
            estimated_cost=Decimal(str(generation.estimated_cost)),
            raw_response_id=generation.raw_response_id,
        )
        self.db.add(report)
        self.db.flush()
        report.action_suggestions = [
            {**item, "created_from_review": report.id}
            for item in report.action_suggestions
        ]
        self.db.flush()
        self.db.refresh(report)
        return report

    def create_memory(self, account_id: int, review_id: int, candidate: dict):
        """将已经显式确认的 Candidate 保存为 Strategy Memory。"""
        memory = StrategyMemory(
            account_id=account_id,
            memory_type="CONTENT_DIRECTION",
            status="VALIDATED",
            summary=candidate["statement"],
            pattern=candidate["statement"],
            confidence=Decimal("0.6000"),
            source_review_report_id=review_id,
            support_count=1,
            evidence_count=len(candidate.get("supporting_refs", [])),
            metadata_payload={"candidate": candidate, "human_confirmed": True},
        )
        self.db.add(memory)
        self.db.commit()
        self.db.refresh(memory)
        return memory
