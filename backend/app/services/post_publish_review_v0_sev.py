import json

from sqlalchemy.orm import Session

from app.core.config import settings
from app.llm.client import LLMClient
from app.repositories.publication_repo import PublicationRepository
from app.schemas.publication import PostPublishReviewInput, PostPublishReviewLLMResult, PostPublishReviewResult


class PostPublishReviewService:
    """发布后复盘的唯一正式 Owner，严格分离观察、解释与策略候选。"""

    def __init__(self, db: Session, llm_client: LLMClient | None = None, repository: PublicationRepository | None = None):
        """初始化发布后复盘服务。"""
        self.repo = repository or PublicationRepository(db)
        self.db = db or getattr(self.repo, "db", None)
        self._llm_client = llm_client

    def review(self, data: PostPublishReviewInput) -> PostPublishReviewResult:
        """基于已发布笔记和指标快照生成复盘及待确认策略候选。"""
        note = self.repo.get_note(data.published_note_ref)
        if not note or note.account_id != data.account_id:
            raise ValueError("Published Note 不存在或不属于当前账号")
        public_snapshots = self.repo.list_public_metrics(note.id)
        if not public_snapshots:
            raise ValueError("缺少 Public Metric Snapshot，不能进行发布后复盘")
        private_snapshots = self.repo.list_private_metrics(note.id)
        allowed_refs = {("published_note", note.id)}
        allowed_refs.update(("public_metric_snapshot", item.id) for item in public_snapshots)
        allowed_refs.update(("private_metric_snapshot", item.id) for item in private_snapshots)

        llm_result = self._client().generate_structured(
            prompt=json.dumps(
                {
                    "published_note": {"ref": note.id, "url": note.publish_url, "draft_ref": note.draft_id},
                    "public_metrics": [self._public_snapshot(item) for item in public_snapshots],
                    "private_metrics": [self._private_snapshot(item) for item in private_snapshots],
                    "private_metrics_status": "AVAILABLE" if private_snapshots else "UNKNOWN",
                    "strategy_ref": data.strategy_ref,
                    "opportunity_ref": data.opportunity_ref,
                },
                ensure_ascii=False,
            ),
            schema_model=PostPublishReviewLLMResult,
            system_prompt=(
                "你是发布后复盘服务。必须区分观察与解释；不得由公开指标推断私域转化；"
                "缺少私域指标时必须表达 UNKNOWN。只能输出 PROPOSED Candidate，"
                "不得写入 Strategy Memory。"
            ),
            prompt_key="post_publish_review",
            prompt_version="v1",
            **self._execution_policy(),
        )
        result = PostPublishReviewLLMResult.model_validate(llm_result.data)
        invalid_refs = [
            (item.kind, item.id)
            for item in self._result_evidence_refs(result)
            if (item.kind, item.id) not in allowed_refs
        ]
        if invalid_refs:
            raise ValueError(f"PostPublishReview 包含无效 EvidenceRefs: {invalid_refs}")
        if any(item.status != "PROPOSED" for item in result.strategy_candidates):
            raise ValueError("LLM 产生的 Strategy Candidate 必须保持 PROPOSED")

        try:
            report = self.repo.create_post_review(note, data.account_id, result, llm_result)
            if self.db is not None:
                self.db.commit()
        except Exception:
            if self.db is not None:
                self.db.rollback()
            raise
        candidates = [item.model_copy(update={"created_from_review": report.id}) for item in result.strategy_candidates]
        payload = result.model_copy(update={"strategy_candidates": candidates}).model_dump()
        return PostPublishReviewResult(review_ref=report.id, **payload)

    def review_semantic(self, payload: dict) -> PostPublishReviewLLMResult:
        """基于已准备发布事实执行纯语义复盘，不保存 Review、Candidate 或 Memory。"""
        llm_result = self._client().generate_structured(
            prompt=json.dumps(payload, ensure_ascii=False),
            schema_model=PostPublishReviewLLMResult,
            system_prompt=(
                "区分观察与解释；public_metrics_status=UNKNOWN 表示公开指标不可用，"
                "不得将点赞、收藏、评论等伪造或表述为 0；"
                "USER_ATTRIBUTED 私域数据可作为用户归因事实引用，私域 UNKNOWN 不得解释为零；只能输出 PROPOSED Candidate；"
                "不得保存 Review、Candidate 或 Strategy Memory。"
            ),
            prompt_key="post_publish_review_semantic",
            prompt_version="v2",
            **self._execution_policy(),
        )
        result = PostPublishReviewLLMResult.model_validate(llm_result.data)
        allowed = {(item["kind"], item["id"]) for item in payload.get("evidence_refs", [])}
        invalid = [
            (item.kind, item.id)
            for item in self._result_evidence_refs(result)
            if (item.kind, item.id) not in allowed
        ]
        if invalid:
            raise ValueError(f"PostPublishReview 包含无效 EvidenceRefs: {invalid}")
        if any(item.status != "PROPOSED" for item in result.strategy_candidates):
            raise ValueError("Strategy Candidate 必须保持 PROPOSED")
        return result

    @staticmethod
    def _result_evidence_refs(result: PostPublishReviewLLMResult):
        """统一收集 Review 与 Candidate 声明的所有 grounding refs。"""
        refs = list(result.evidence_refs)
        for candidate in result.strategy_candidates:
            refs.extend(candidate.supporting_refs)
            refs.extend(candidate.contradicting_refs)
        return refs

    @staticmethod
    def _execution_policy() -> dict:
        """解析 Review 专属执行策略，未配置时显式回退全局默认值。"""
        policy = {
            "model": settings.llm_post_publish_review_model or settings.llm_model,
            "timeout_seconds": settings.llm_post_publish_review_timeout_seconds or settings.llm_timeout_seconds,
        }
        if settings.llm_post_publish_review_enable_thinking is not None:
            policy["extra_body"] = {
                "enable_thinking": settings.llm_post_publish_review_enable_thinking,
            }
        return policy

    def _client(self) -> LLMClient:
        """延迟创建统一大模型客户端。"""
        if self._llm_client is None:
            self._llm_client = LLMClient()
        return self._llm_client

    def _public_snapshot(self, item) -> dict:
        """将公开指标记录映射为带来源的实测观察。"""
        return {
            "evidence_ref": {"kind": "public_metric_snapshot", "id": item.id},
            "window": item.snapshot_window,
            "observed_at": item.collected_at.isoformat() if item.collected_at else None,
            "metrics": {"likes": item.like_count, "collects": item.collect_count, "comments": item.comment_count, "shares": item.share_count},
            "provenance": "MEASURED",
        }

    def _private_snapshot(self, item) -> dict:
        """按实际填写字段还原私域指标，未填写字段保持未知。"""
        raw = item.raw_snapshot or {}
        provided = set(raw.get("provided_fields", []))
        values = raw.get("values", {})
        names = ("dm_count", "wechat_add_count", "consultation_count", "deal_count", "revenue")
        return {
            "evidence_ref": {"kind": "private_metric_snapshot", "id": item.id},
            "window": item.snapshot_window,
            "metrics": {name: values.get(name) if name in provided else None for name in names},
            "provenance": "USER_ATTRIBUTED",
        }
