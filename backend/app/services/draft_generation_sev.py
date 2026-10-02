import json

from sqlalchemy.orm import Session

from app.core.config import settings
from app.llm.client import LLMClient
from app.repositories.draft_repo import DraftRepository
from app.schemas.draft import DraftContent, DraftGenerationInput, GeneratedDraft


class DraftGenerationService:
    """CAP-DRAFT-GENERATION 的唯一正式 Owner。"""

    def __init__(self, db: Session, llm_client: LLMClient | None = None, repository: DraftRepository | None = None):
        """初始化 Draft 生成服务。"""
        self.repo = repository or DraftRepository(db)
        self._llm_client = llm_client

    def generate(self, data: DraftGenerationInput) -> GeneratedDraft:
        """生成并持久化兼容业务 Draft。"""
        account = self.repo.get_account(data.account_id)
        if not account:
            raise ValueError("账号配置不存在")
        opportunity = self.repo.get_opportunity(data.opportunity.source_opportunity_id)
        if not opportunity or opportunity.id != data.opportunity.source_opportunity_id:
            raise ValueError("Content Opportunity 不存在")
        if opportunity.opportunity_title != data.opportunity.topic:
            raise ValueError("Content Opportunity identity 不匹配")
        experiment_id = self.repo.resolve_legacy_experiment_id(data.account_id, opportunity.id)
        if experiment_id is None:
            raise ValueError("旧 Draft 表约束需要已有 Opportunity lineage，不允许隐式创建 Experiment")

        client = self._client()
        llm_result = client.generate_structured(
            prompt=self._prompt(account, data),
            schema_model=DraftContent,
            system_prompt=(
                "你是小红书内容初稿生成器。严格保持 Content Opportunity 的 topic、goal 和 evidence 边界；"
                "不得重新做 Research，不得创造样本事实，不得执行发布、Review 或 Memory 操作。"
            ),
            prompt_key="draft_generation",
            prompt_version="v1",
            timeout_seconds=settings.llm_draft_generation_timeout_seconds,
        )
        content = DraftContent.model_validate(llm_result.data)
        evidence_refs = self._unique_refs(
            [data.research_artifact_ref, *data.evidence_refs, *data.opportunity.evidence_refs]
        )
        context = {
            "created_from": "GENERATED",
            "strategy_ref": data.strategy_ref,
            "opportunity_ref": opportunity.id,
            "content_goal": data.opportunity.content_goal,
            "research_artifact_ref": data.research_artifact_ref.model_dump(),
            "evidence_refs": [item.model_dump() for item in evidence_refs],
            "user_constraints": data.user_constraints,
        }
        draft = self.repo.create_draft(
            experiment_id=experiment_id,
            content=content,
            version=1,
            status="GENERATED",
            context=context,
            llm_result=llm_result,
        )
        self.repo.create_version(draft, created_from="GENERATED", parent_draft_ref=None, applied_changes=[])
        return GeneratedDraft(
            draft_ref=draft.id,
            version=draft.version,
            title=content.title,
            body=content.body,
            tags=content.tags,
            cta=content.cta,
            content_goal=data.opportunity.content_goal,
            opportunity_ref=opportunity.id,
            strategy_ref=data.strategy_ref,
            evidence_refs=evidence_refs,
            generation_metadata={"provider": client.provider, "model": client.model, "created_from": "GENERATED"},
        )

    def generate_semantic(self, payload: dict) -> DraftContent:
        """基于已准备上下文生成纯语义 DraftContent，不查询或写入数据库。"""
        result = self._client().generate_structured(
            prompt="请严格保持 strategy、opportunity 和 content_goal 身份生成 DraftContent。\n" + json.dumps(payload, ensure_ascii=False),
            schema_model=DraftContent,
            system_prompt="只生成 DraftContent；不得重新 Research、改变选题、保存版本、发布或写入 Memory。",
            prompt_key="draft_generation_semantic",
            prompt_version="v1",
            timeout_seconds=settings.llm_draft_generation_timeout_seconds,
        )
        return DraftContent.model_validate(result.data)

    def _client(self):
        """延迟创建统一 LLMClient。"""
        if self._llm_client is None:
            self._llm_client = LLMClient()
        return self._llm_client

    def _prompt(self, account, data: DraftGenerationInput) -> str:
        """构造兼容业务入口的 Draft 提示。"""
        payload = {
            "account_context": {
                "positioning": account.positioning,
                "target_audience": account.target_audience,
                "tone_preference": account.tone_preference,
                "forbidden_topics": account.forbidden_topics,
            },
            "strategy_ref": data.strategy_ref,
            "opportunity": data.opportunity.model_dump(),
            "research_artifact_ref": data.research_artifact_ref.model_dump(),
            "evidence_refs": [item.model_dump() for item in data.evidence_refs],
            "user_constraints": data.user_constraints,
            "optional_previous_context": data.optional_previous_context,
        }
        return "请仅生成 DraftContent JSON。\n" + json.dumps(payload, ensure_ascii=False)

    def _unique_refs(self, refs):
        """按类型与标识对 EvidenceRef 去重。"""
        unique = {}
        for item in refs:
            unique[(item.kind, item.id)] = item
        return list(unique.values())
