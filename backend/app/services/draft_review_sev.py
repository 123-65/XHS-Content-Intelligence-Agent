import json

from sqlalchemy.orm import Session

from app.core.config import settings
from app.llm.client import LLMClient
from app.repositories.draft_repo import DraftRepository
from app.schemas.content_strategy import EvidenceRef
from app.schemas.draft import DraftReviewInput, DraftReviewLLMResult, DraftReviewResult


DRAFT_REVIEW_PROMPT_VERSION = "v2"


class DraftReviewService:
    """CAP-DRAFT-REVIEW 的唯一正式 Owner；只检查，不修改 Draft。"""

    def __init__(self, db: Session, llm_client: LLMClient | None = None, repository: DraftRepository | None = None):
        """初始化 Draft Review 服务。"""
        self.repo = repository or DraftRepository(db)
        self._llm_client = llm_client

    def review(self, data: DraftReviewInput) -> DraftReviewResult:
        """审核并持久化兼容业务 Review。"""
        account = self.repo.get_account(data.account_id)
        if not account:
            raise ValueError("账号配置不存在")
        draft = self.repo.get_draft(data.draft_ref)
        if not draft:
            raise ValueError("Draft 不存在")
        lineage = draft.generation_context or {}
        if lineage.get("strategy_ref") != data.strategy_ref or lineage.get("opportunity_ref") != data.opportunity_ref:
            raise ValueError("Draft 的 Strategy / Opportunity identity 不匹配")
        allowed_refs = {
            (item.kind, item.id) for item in data.evidence_refs
        } | {
            (item["kind"], item["id"]) for item in lineage.get("evidence_refs", [])
        }
        client = self._client()
        llm_result = client.generate_structured(
            prompt=json.dumps({
                "draft": self._snapshot(draft),
                "account_context": {
                    "positioning": account.positioning,
                    "target_audience": account.target_audience,
                    "tone_preference": account.tone_preference,
                    "forbidden_topics": account.forbidden_topics,
                },
                "strategy_ref": data.strategy_ref,
                "opportunity_ref": data.opportunity_ref,
                "evidence_refs": [item.model_dump() for item in data.evidence_refs],
                "user_style_constraints": data.user_style_constraints,
            }, ensure_ascii=False),
            schema_model=DraftReviewLLMResult,
            system_prompt=(
                "你是结构化 Draft Reviewer。检查策略对齐、证据支撑、风格、结构和风险。"
                "不得重写或保存 Draft，不得预测点赞、爆款或成交。"
            ),
            prompt_key="draft_review",
            prompt_version=DRAFT_REVIEW_PROMPT_VERSION,
            **self._execution_policy(),
        )
        result = DraftReviewLLMResult.model_validate(llm_result.data)
        invalid = [(item.kind, item.id) for item in result.cited_evidence_refs if (item.kind, item.id) not in allowed_refs]
        if invalid:
            raise ValueError(f"Review 包含无效 EvidenceRefs: {invalid}")
        report = self.repo.create_review(draft, data.account_id, result, llm_result)
        return DraftReviewResult(review_result_ref=report.id, draft_ref=draft.id, **result.model_dump())

    def review_semantic(self, payload: dict) -> DraftReviewLLMResult:
        """仅评价已准备 Draft，不修改或持久化任何内容。"""
        llm_result = self._client().generate_structured(
            prompt=(
                "请审核以下 Draft。cited_evidence_refs 只能逐项复制 evidence_refs 中的引用；"
                "Strategy、Opportunity 和 Research identity 只有出现在 evidence_refs 时才可引用。\n"
                + json.dumps(payload, ensure_ascii=False)
            ),
            schema_model=DraftReviewLLMResult,
            system_prompt=(
                "仅评价 Draft 的策略对齐、证据、风格和风险；不得重写、搜索或保存 Draft。"
                "不得创造 EvidenceRef，cited_evidence_refs 必须是输入 evidence_refs 的子集。"
            ),
            prompt_key="draft_review_semantic",
            prompt_version=DRAFT_REVIEW_PROMPT_VERSION,
            **self._execution_policy(),
        )
        result = DraftReviewLLMResult.model_validate(llm_result.data)
        allowed = {(item["kind"], item["id"]) for item in payload.get("evidence_refs", [])}
        invalid = [(item.kind, item.id) for item in result.cited_evidence_refs if (item.kind, item.id) not in allowed]
        if invalid:
            raise ValueError(f"Review 包含无效 EvidenceRefs: {invalid}")
        return result

    @staticmethod
    def _execution_policy() -> dict:
        """Use the task-specific structured model without altering timeout or retry ownership."""
        return {
            "model": settings.llm_draft_review_model,
            "timeout_seconds": settings.llm_draft_review_timeout_seconds,
        }

    def _client(self):
        """延迟创建统一 LLMClient。"""
        if self._llm_client is None:
            self._llm_client = LLMClient()
        return self._llm_client

    def _snapshot(self, draft) -> dict:
        """提取 Draft 审核快照。"""
        return {
            "draft_ref": draft.id,
            "title": draft.recommended_title or draft.title,
            "body": draft.body_text or draft.body,
            "tags": draft.tag_list or draft.tags,
            "cta": draft.cta_text or draft.cta,
        }
