import json

from sqlalchemy.orm import Session

from app.core.config import settings
from app.llm.client import LLMClient
from app.repositories.draft_repo import DraftRepository
from app.schemas.content_strategy import EvidenceRef
from app.schemas.draft import DraftRevisionInput, DraftRevisionLLMResult, RevisedDraft


DRAFT_REVISION_PROMPT_VERSION = "v2"
DRAFT_REVISION_OUTPUT_CONTRACT = (
    "必须返回非空 applied_changes 字符串数组，逐项说明根据用户要求实际应用了哪些修改；"
    "不得省略该字段、返回空数组或填写未实际发生的模板修改。"
)


class DraftRevisionService:
    """CAP-DRAFT-REVISION 的唯一正式 Owner。"""

    def __init__(self, db: Session, llm_client: LLMClient | None = None, repository: DraftRepository | None = None):
        """初始化 Draft Revision 服务。"""
        self.repo = repository or DraftRepository(db)
        self._llm_client = llm_client

    def revise(self, data: DraftRevisionInput) -> RevisedDraft:
        """修订并持久化兼容业务 Draft Version。"""
        account = self.repo.get_account(data.account_id)
        if not account:
            raise ValueError("账号配置不存在")
        source = self.repo.get_draft(data.source_draft_ref)
        if not source:
            raise ValueError("Source Draft 不存在")
        review = None
        if data.revision_source == "REVIEW_RESULT":
            review = self.repo.get_review(data.review_result_ref)
            if not review or review.draft_id != source.id:
                raise ValueError("Review Result 不属于 Source Draft")
        lineage = dict(source.generation_context or {})
        if not lineage.get("opportunity_ref") or not lineage.get("strategy_ref"):
            raise ValueError("Source Draft 缺少 Strategy / Opportunity lineage")
        instruction = data.user_instruction or (review.summary if review else "")
        client = self._client()
        llm_result = client.generate_structured(
            prompt=json.dumps({
                "source_draft": self._snapshot(source),
                "account_style": {
                    "positioning": account.positioning,
                    "target_audience": account.target_audience,
                    "tone_preference": account.tone_preference,
                    "forbidden_topics": account.forbidden_topics,
                },
                "revision_source": data.revision_source,
                "instruction": instruction,
                "review": self._review_snapshot(review),
                "preserved_constraints": data.preserved_constraints,
                "context_refs": [item.model_dump() for item in data.context_refs],
                "immutable_identity": {
                    "strategy_ref": lineage["strategy_ref"],
                    "opportunity_ref": lineage["opportunity_ref"],
                    "content_goal": lineage.get("content_goal"),
                },
            }, ensure_ascii=False),
            schema_model=DraftRevisionLLMResult,
            system_prompt=(
                "根据明确修改依据修订 Draft。不得更换 topic、content goal、strategy 或 opportunity；"
                f"不得重新 Research、发布或写入 Memory。{DRAFT_REVISION_OUTPUT_CONTRACT}返回结构化 JSON。"
            ),
            prompt_key="draft_revision",
            prompt_version=DRAFT_REVISION_PROMPT_VERSION,
            **self._execution_policy(),
        )
        content = DraftRevisionLLMResult.model_validate(llm_result.data)
        created_from = "USER_REVISION" if data.revision_source == "USER_FEEDBACK" else "REVIEW_REVISION"
        evidence_refs = self._evidence_refs(lineage, data.context_refs)
        new_lineage = {
            **lineage,
            "created_from": created_from,
            "parent_draft_ref": source.id,
            "review_result_ref": data.review_result_ref,
            "revision_source": data.revision_source,
            "preserved_constraints": data.preserved_constraints,
            "evidence_refs": [item.model_dump() for item in evidence_refs],
        }
        draft = self.repo.create_draft(
            experiment_id=source.experiment_id,
            content=content,
            version=source.version + 1,
            status="REVISED",
            context=new_lineage,
            llm_result=llm_result,
        )
        self.repo.create_version(
            draft,
            created_from=created_from,
            parent_draft_ref=source.id,
            applied_changes=content.applied_changes,
        )
        return RevisedDraft(
            draft_ref=draft.id,
            parent_draft_ref=source.id,
            version=draft.version,
            title=content.title,
            body=content.body,
            tags=content.tags,
            cta=content.cta,
            applied_changes=content.applied_changes,
            preserved_constraints=data.preserved_constraints,
            evidence_refs=evidence_refs,
            opportunity_ref=lineage["opportunity_ref"],
            strategy_ref=lineage["strategy_ref"],
        )

    def revise_semantic(self, payload: dict) -> DraftRevisionLLMResult:
        """在不可变内容身份下执行纯语义修订，不保存 Draft Version。"""
        result = self._client().generate_structured(
            prompt=json.dumps(payload, ensure_ascii=False),
            schema_model=DraftRevisionLLMResult,
            system_prompt=(
                "仅按明确反馈修订表达，不得改变 strategy_ref、opportunity_ref 或 content_goal，不得保存结果。"
                f"{DRAFT_REVISION_OUTPUT_CONTRACT}"
            ),
            prompt_key="draft_revision_semantic",
            prompt_version=DRAFT_REVISION_PROMPT_VERSION,
            **self._execution_policy(),
        )
        return DraftRevisionLLMResult.model_validate(result.data)

    @staticmethod
    def _execution_policy() -> dict:
        """解析 Revision 专属执行策略，未配置时显式回退全局默认值。"""
        policy = {
            "model": settings.llm_draft_revision_model or settings.llm_model,
            "timeout_seconds": settings.llm_draft_revision_timeout_seconds or settings.llm_timeout_seconds,
        }
        if settings.llm_draft_revision_enable_thinking is not None:
            policy["extra_body"] = {
                "enable_thinking": settings.llm_draft_revision_enable_thinking,
            }
        return policy

    def _client(self):
        """延迟创建统一 LLMClient。"""
        if self._llm_client is None:
            self._llm_client = LLMClient()
        return self._llm_client

    def _snapshot(self, draft):
        """提取待修订 Draft 快照。"""
        return {"draft_ref": draft.id, "title": draft.recommended_title or draft.title, "body": draft.body_text or draft.body, "tags": draft.tag_list or draft.tags, "cta": draft.cta_text or draft.cta}

    def _review_snapshot(self, review):
        """提取可选 Review 快照。"""
        return None if review is None else {"review_result_ref": review.id, "issues": review.issues, "suggestions": review.suggestions, "summary": review.summary}

    def _evidence_refs(self, lineage: dict, extra: list[EvidenceRef]) -> list[EvidenceRef]:
        """合并并去重修订证据引用。"""
        refs = [EvidenceRef.model_validate(item) for item in lineage.get("evidence_refs", [])]
        unique = {}
        for item in [*refs, *extra]:
            unique[(item.kind, item.id)] = item
        return list(unique.values())
