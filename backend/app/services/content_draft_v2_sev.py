from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session

from app.context.context_builder import ContextManager
from app.context.context_slots import ContextRole, ContextSlot, ContextSlotName
from app.context.context_usage_logger import ContextUsageLogger
from app.llm.client import LLMClient
from app.llm.errors import LLMError
from app.models.content_draft import ContentDraft
from app.prompts.manager import PromptManager, RenderedPrompt
from app.repositories.content_draft_v2_repo import ContentDraftV2Repository
from app.services.confirmation_sev import ConfirmationService
from app.schemas.content_draft_v2 import (
    ContentDraftV2Create,
    ContentDraftV2Response,
    ContentDraftVersionCreate,
    ContentDraftVersionResponse,
    DraftGenerateV2Result,
    DraftGenerationContextCreate,
    DraftGenerationContextResponse,
    GenerateDraftV2Request,
    PromptRunLogCreate,
    RegenerateDraftRequest,
)


# 风险约束：必须以 SYSTEM 角色注入提示词，约束模型不得输出违规承诺
RISK_CONSTRAINTS = [
    "不允许保 offer",
    "不允许保证涨粉",
    "不允许保证成交",
    "不允许夸大收益",
    "不允许强诱导评论",
    "不允许虚构用户经历",
]

# 风险短语 → 对应违规类别，用于生成后的关键词扫描
RISK_PHRASES = {
    "保 offer": "不允许保 offer",
    "保证涨粉": "不允许保证涨粉",
    "保证成交": "不允许保证成交",
    "稳赚": "不允许夸大收益",
    "月入": "不允许夸大收益",
    "必须评论": "不允许强诱导评论",
    "评论区扣": "不允许强诱导评论",
    "真实学员案例": "不允许虚构用户经历",
}  

# 局部重生成时的字段范围映射
SCOPED_FIELDS = {
    "title": {"title_candidates", "recommended_title", "title"},
    "cover": {"cover_text", "cover_subtitle"},
    "body": {"body_text", "body"},
    "image_script": {"image_script", "image_scripts"},
    "tags": {"tag_list", "keyword_list", "tags"},
    "cta": {"cta_text", "cta"},
}


class ContentDraftV2Service:
    """编排提示词渲染、LLM 调用与草稿落库的服务。"""

    def __init__(self, db: Session):
        """初始化 V2 草稿服务。"""
        self.repo = ContentDraftV2Repository(db)
        self.prompt_manager = PromptManager(db)

    def generate_draft(
        self,
        data: GenerateDraftV2Request,
        agent_run_id: int | None = None,
        agent_step_id: int | None = None,
    ) -> ContentDraftV2Response:
        """基于已批准的内容实验生成草稿。"""
        experiment = self._get_experiment_or_raise(data.experiment_id)
        self._ensure_experiment_approved(experiment)

        account = self._get_account_or_raise(experiment.account_id)
        opportunity = self.repo.get_opportunity(experiment.content_opportunity_id)
        context_payload = self._build_context(account, experiment, opportunity, data.user_requirement)
        prompt = self._render_prompt(context_payload, "all")
        built_context = self._build_llm_context(prompt, context_payload, "all")
        llm_result = self._call_llm(prompt, built_context)
        prompt_log = self._save_prompt_log(prompt, built_context, llm_result)
        self._save_context_snapshot(built_context, prompt_log.id, llm_result, agent_run_id, agent_step_id)

        self._ensure_risk_safe(llm_result.data)
        generation_context = self.repo.create_generation_context(context_payload)
        draft = self.repo.create_draft(self._build_draft_create(experiment.id, llm_result, context_payload))
        self.repo.update_context_draft(generation_context, draft.id)
        self.repo.create_version(
            ContentDraftVersionCreate(
                draft_id=draft.id,
                version=draft.version,
                regenerate_scope="all",
                draft_snapshot=self._draft_snapshot(draft),
                prompt_run_log_id=prompt_log.id,
            )
        )
        self.repo.update_experiment_status(experiment, "DRAFTING")
        return self.get_draft(draft.id)

    def get_draft(self, draft_id: int) -> ContentDraftV2Response:
        """返回草稿详情，包含生成上下文和版本列表。"""
        draft = self._get_draft_or_raise(draft_id)
        return self._build_response(draft)

    def regenerate_draft(self, draft_id: int, data: RegenerateDraftRequest) -> ContentDraftV2Response:
        """按指定 scope 局部或整体重生成草稿。"""
        draft = self._get_draft_or_raise(draft_id)
        experiment = self._get_experiment_or_raise(draft.experiment_id)
        account = self._get_account_or_raise(experiment.account_id)
        opportunity = self.repo.get_opportunity(experiment.content_opportunity_id)
        context_payload = self._build_context(account, experiment, opportunity, data.user_requirement, draft)
        prompt = self._render_prompt(context_payload, data.scope)
        built_context = self._build_llm_context(prompt, context_payload, data.scope)
        llm_result = self._call_llm(prompt, built_context)
        prompt_log = self._save_prompt_log(prompt, built_context, llm_result)
        self._save_context_snapshot(built_context, prompt_log.id, llm_result)

        self._ensure_risk_safe(llm_result.data)
        updated_draft = self.repo.update_draft(draft, self._merged_fields(draft, llm_result.data, data.scope))
        self.repo.create_version(
            ContentDraftVersionCreate(
                draft_id=updated_draft.id,
                version=updated_draft.version,
                regenerate_scope=data.scope,
                draft_snapshot=self._draft_snapshot(updated_draft),
                prompt_run_log_id=prompt_log.id,
            )
        )
        # 草稿更新后，之前针对旧版本的发布确认全部失效
        ConfirmationService(self.repo.db).invalidate_publish_confirmations_for_draft(
            updated_draft.id,
            updated_draft.version,
            "draft regenerated",
        )
        return self.get_draft(updated_draft.id)

    def create_version(self, draft_id: int) -> ContentDraftVersionResponse:
        """为当前草稿创建一个手动版本快照。"""
        draft = self._get_draft_or_raise(draft_id)
        version = self.repo.create_version(
            ContentDraftVersionCreate(
                draft_id=draft.id,
                version=draft.version,
                regenerate_scope="manual_snapshot",
                draft_snapshot=self._draft_snapshot(draft),
            )
        )
        return ContentDraftVersionResponse.model_validate(version)

    def _render_prompt(self, context_payload: DraftGenerationContextCreate, scope: str) -> RenderedPrompt:
        """渲染草稿生成提示词。"""
        return self.prompt_manager.render(
            "app.prompts.xhs_draft_v2",
            {"context": context_payload.model_dump(), "regenerate_scope": scope},
            DraftGenerateV2Result.model_json_schema(),
        )

    def _build_llm_context(self, prompt: RenderedPrompt, context_payload: DraftGenerationContextCreate, scope: str):
        """按显式插槽构建受治理的 LLM 上下文。"""
        task_name = "draft_generation" if scope == "all" else "draft_regeneration"
        context = context_payload.model_dump()
        manager = ContextManager(task_name=task_name)
        manager.extend(
            [
                ContextSlot(
                    ContextSlotName.SYSTEM_RULES,
                    prompt.system_prompt,
                    role=ContextRole.SYSTEM,
                    priority=100,
                    source_type="prompt_template",
                    metadata={"source_version": prompt.prompt_version},
                ),
                ContextSlot(
                    ContextSlotName.RISK_CONSTRAINTS,
                    context_payload.risk_constraints,
                    role=ContextRole.SYSTEM,
                    priority=95,
                    source_type="risk_constraints",
                ),
                ContextSlot(
                    ContextSlotName.TASK_INSTRUCTION,
                    {
                        "prompt_name": prompt.prompt_name,
                        "prompt_version": prompt.prompt_version,
                        "regenerate_scope": scope,
                        "instruction": "生成符合输出 schema 的完整 JSON 草稿，不生成图片文件。",
                    },
                    priority=90,
                    source_type="prompt_template",
                    metadata={"source_version": prompt.prompt_version},
                ),
                ContextSlot(ContextSlotName.ACCOUNT_PROFILE, context_payload.account_snapshot, priority=85, source_type="account_profile"),
                ContextSlot(
                    ContextSlotName.WORKFLOW_STATE,
                    {
                        "account_id": context_payload.account_id,
                        "experiment_id": context_payload.experiment_id,
                        "content_opportunity_id": context_payload.content_opportunity_id,
                        "experiment": context_payload.experiment_snapshot,
                        "opportunity": context_payload.opportunity_snapshot,
                    },
                    priority=80,
                    source_type="content_experiment_v2",
                ),
                ContextSlot(ContextSlotName.USER_INPUT, context_payload.user_requirement or "", priority=75, source_type="manual_input"),
                ContextSlot(
                    ContextSlotName.OUTPUT_SCHEMA,
                    DraftGenerateV2Result.model_json_schema(),
                    priority=70,
                    token_limit=1200,
                    source_type="schema_model",
                    metadata={"source_version": "DraftGenerateV2Result"},
                ),
                ContextSlot(
                    ContextSlotName.STRATEGY_MEMORY,
                    context.get("strategy_memory_snapshot") or {},
                    priority=60,
                    token_limit=1000,
                    source_type="strategy_memory",
                    metadata={"data_status": "NOT_PROVIDED" if not context.get("strategy_memory_snapshot") else "PARTIAL"},
                ),
            ]
        )
        return manager.build()

    def _call_llm(self, prompt: RenderedPrompt, built_context):
        """调用 LLM 并校验结构化草稿输出。"""
        try:
            return LLMClient().generate_structured_with_context(
                context=built_context,
                schema_model=DraftGenerateV2Result,
                prompt_key=prompt.prompt_name,
                prompt_version=prompt.prompt_version,
            )
        except LLMError as exc:
            self._save_failed_prompt_log(prompt, built_context, exc)
            raise

    def _save_prompt_log(self, prompt: RenderedPrompt, built_context, llm_result) -> object:
        """记录成功的提示词运行日志。"""
        return self.repo.create_prompt_run_log(
            PromptRunLogCreate(
                prompt_template_id=prompt.template.id,
                prompt_name=prompt.prompt_name,
                prompt_version=prompt.prompt_version,
                input_payload=self._prompt_log_input_payload(prompt, built_context),
                input_summary=self._prompt_io_summary(built_context.user_prompt),
                rendered_prompt=built_context.user_prompt,
                output_text=llm_result.text,
                output_json=llm_result.data.model_dump(),
                output_summary=self._prompt_io_summary(llm_result.text),
                model=llm_result.model,
                provider=llm_result.provider,
                prompt_key=prompt.prompt_name,
                prompt_tokens=llm_result.usage.prompt_tokens,
                completion_tokens=llm_result.usage.completion_tokens,
                total_tokens=llm_result.usage.total_tokens,
                input_token_count=llm_result.usage.prompt_tokens,
                output_token_count=llm_result.usage.completion_tokens,
                estimated_cost=Decimal(str(llm_result.estimated_cost)),
                latency_ms=llm_result.latency_ms,
                is_mock=llm_result.is_mock,
                fallback_used=llm_result.fallback_used,
                fallback_from=llm_result.fallback_from,
                raw_response_id=llm_result.raw_response_id,
                status="SUCCESS",
                error_message=llm_result.error_message,
            )
        )

    def _save_failed_prompt_log(self, prompt: RenderedPrompt, built_context, exc: Exception) -> None:
        """记录失败的提示词运行日志。"""
        self.repo.create_prompt_run_log(
            PromptRunLogCreate(
                prompt_template_id=prompt.template.id,
                prompt_name=prompt.prompt_name,
                prompt_version=prompt.prompt_version,
                input_payload=self._prompt_log_input_payload(prompt, built_context),
                input_summary=self._prompt_io_summary(built_context.user_prompt),
                rendered_prompt=built_context.user_prompt,
                model="unknown",
                provider="unknown",
                prompt_key=prompt.prompt_name,
                status="FAILED",
                error_message=str(exc),
            )
        )

    def _prompt_io_summary(self, text: str | None) -> dict:
        """为可观测性构建有界的提示词/输出摘要。"""
        value = text or ""
        return {"length": len(value), "preview": value[:500], "truncated": len(value) > 500}

    def _prompt_log_input_payload(self, prompt: RenderedPrompt, built_context) -> dict:
        """附加上下文元数据，但不保存超长的原始提示词。"""
        return {
            **prompt.input_payload,
            "_context": {
                "task_name": built_context.task_name,
                "token_budget": built_context.token_budget,
                "total_tokens": built_context.total_tokens,
                "injected_slot_names": built_context.injected_slot_names,
                "truncation_summary": built_context.truncation_summary,
                "sanitizer_summary": built_context.sanitizer_summary,
                "memory_usage_summary": built_context.memory_usage_summary,
                "slot_budget_summary": [
                    slot.metadata.get("budget_meta")
                    for slot in built_context.slots
                    if slot.metadata.get("budget_meta")
                ],
            },
        }

    def _save_context_snapshot(
        self,
        built_context,
        prompt_run_log_id: int,
        llm_result,
        agent_run_id: int | None = None,
        agent_step_id: int | None = None,
    ) -> None:
        """持久化受治理的上下文快照，供开发者排查问题。"""
        ContextUsageLogger(self.repo.db).record_snapshot(
            built_context,
            agent_run_id=agent_run_id,
            agent_step_id=agent_step_id,
            prompt_run_log_id=prompt_run_log_id,
            model=llm_result.model,
            provider=llm_result.provider,
        )

    def _build_draft_create(self, experiment_id: int, llm_result, context_payload: DraftGenerationContextCreate) -> ContentDraftV2Create:
        """从 LLM 结果构建草稿创建入参。"""
        result = llm_result.data
        image_script = [item.model_dump() for item in result.image_script]
        return ContentDraftV2Create(
            experiment_id=experiment_id,
            title=result.recommended_title,
            body=result.body_text,
            tags=result.tag_list,
            cover_text=result.cover_text,
            image_scripts=image_script,
            cta=result.cta_text,
            title_candidates=result.title_candidates,
            recommended_title=result.recommended_title,
            cover_subtitle=result.cover_subtitle,
            body_text=result.body_text,
            image_script=image_script,
            tag_list=result.tag_list,
            keyword_list=result.keyword_list,
            cta_text=result.cta_text,
            generation_context=context_payload.model_dump(),
            prompt_tokens=llm_result.usage.prompt_tokens,
            completion_tokens=llm_result.usage.completion_tokens,
            total_tokens=llm_result.usage.total_tokens,
            estimated_cost=Decimal(str(llm_result.estimated_cost)),
            raw_response_id=llm_result.raw_response_id,
        )

    def _merged_fields(self, draft: ContentDraft, result: DraftGenerateV2Result, scope: str) -> dict:
        """按指定 scope 合并重生成后的字段。"""
        all_fields = {
            "title_candidates": result.title_candidates,
            "recommended_title": result.recommended_title,
            "title": result.recommended_title,
            "cover_text": result.cover_text,
            "cover_subtitle": result.cover_subtitle,
            "body_text": result.body_text,
            "body": result.body_text,
            "image_script": [item.model_dump() for item in result.image_script],
            "image_scripts": [item.model_dump() for item in result.image_script],
            "tag_list": result.tag_list,
            "keyword_list": result.keyword_list,
            "tags": result.tag_list,
            "cta_text": result.cta_text,
            "cta": result.cta_text,
        }
        selected = set(all_fields) if scope == "all" else SCOPED_FIELDS[scope]
        return {field: value for field, value in all_fields.items() if field in selected} | {"version": draft.version + 1}

    def _build_context(self, account, experiment, opportunity, user_requirement: str | None, draft: ContentDraft | None = None) -> DraftGenerationContextCreate:
        """构建发送给提示词的上下文快照。"""
        strategy_memory: dict[str, Any] = {"status": "NOT_IMPLEMENTED_IN_ROUND_6"}
        if draft:
            strategy_memory["previous_draft"] = self._draft_snapshot(draft)

        return DraftGenerationContextCreate(
            account_id=account.id,
            experiment_id=experiment.id,
            content_opportunity_id=experiment.content_opportunity_id,
            account_snapshot={
                "account_name": account.account_name,
                "content_domain": account.content_domain,
                "positioning": account.positioning,
                "target_audience": account.target_audience,
                "persona": account.persona,
                "monetization_goal": account.monetization_goal,
                "risk_preference": account.risk_preference,
                "account_stage": account.account_stage,
            },
            experiment_snapshot={
                "experiment_name": experiment.experiment_name,
                "hypothesis": experiment.hypothesis,
                "content_pillar": experiment.content_pillar,
                "content_format": experiment.content_format,
                "main_variable": experiment.main_variable,
                "control_variables": experiment.control_variables,
                "primary_metric": experiment.primary_metric,
                "secondary_metrics": experiment.secondary_metrics,
                "success_criteria": experiment.success_criteria,
                "failure_criteria": experiment.failure_criteria,
                "fallback_strategy": experiment.fallback_strategy,
                "risk_level": experiment.risk_level,
            },
            opportunity_snapshot=self._opportunity_snapshot(opportunity),
            strategy_memory_snapshot=strategy_memory,
            risk_constraints=RISK_CONSTRAINTS,
            user_requirement=user_requirement,
        )

    def _opportunity_snapshot(self, opportunity) -> dict:
        """构建关联内容机会的快照。"""
        return {
            "opportunity_title": getattr(opportunity, "opportunity_title", None),
            "suggested_angle": getattr(opportunity, "suggested_angle", None),
            "evidence_summary": getattr(opportunity, "evidence_summary", None),
            "replicability_score": getattr(opportunity, "replicability_score", None),
            "risk_level": getattr(opportunity, "risk_level", None),
            "opportunity_score": getattr(opportunity, "opportunity_score", None),
        }

    def _ensure_experiment_approved(self, experiment) -> None:
        """确保只有已批准的内容实验才能生成草稿。"""
        if experiment.status != "APPROVED":
            raise ValueError("Only APPROVED content experiments can generate drafts")

    def _ensure_risk_safe(self, result: DraftGenerateV2Result) -> None:
        """对生成草稿的字段做基础风险短语扫描。"""
        text = " ".join(
            [
                *result.title_candidates,
                result.recommended_title,
                result.cover_text,
                result.cover_subtitle or "",
                result.body_text,
                " ".join(item.content for item in result.image_script),
                " ".join(result.tag_list),
                " ".join(result.keyword_list),
                result.cta_text or "",
            ]
        ).lower()
        violations = {rule for phrase, rule in RISK_PHRASES.items() if phrase.lower() in text}
        if violations:
            raise ValueError(f"Draft failed baseline risk check: {', '.join(sorted(violations))}")

    def _draft_snapshot(self, draft: ContentDraft) -> dict:
        """为草稿版本创建可序列化的快照。"""
        return {
            "title_candidates": draft.title_candidates,
            "recommended_title": draft.recommended_title,
            "cover_text": draft.cover_text,
            "cover_subtitle": draft.cover_subtitle,
            "body_text": draft.body_text,
            "image_script": draft.image_script,
            "tag_list": draft.tag_list,
            "keyword_list": draft.keyword_list,
            "cta_text": draft.cta_text,
            "version": draft.version,
            "status": draft.status,
        }

    def _build_response(self, draft: ContentDraft) -> ContentDraftV2Response:
        """构建草稿详情响应。"""
        context = self.repo.get_generation_context(draft.id)
        versions = self.repo.list_versions(draft.id)
        return ContentDraftV2Response.model_validate(
            {
                **draft.__dict__,
                "generation_context_record": DraftGenerationContextResponse.model_validate(context) if context else None,
                "versions": [ContentDraftVersionResponse.model_validate(item) for item in versions],
            }
        )

    def _get_experiment_or_raise(self, experiment_id: int):
        """获取内容实验，不存在则抛业务异常。"""
        experiment = self.repo.get_experiment(experiment_id)
        if not experiment:
            raise ValueError("Content experiment does not exist")
        return experiment

    def _get_account_or_raise(self, account_id: int):
        """获取账号画像，不存在则抛业务异常。"""
        account = self.repo.get_account(account_id)
        if not account:
            raise ValueError("Account profile does not exist")
        return account

    def _get_draft_or_raise(self, draft_id: int) -> ContentDraft:
        """获取内容草稿，不存在则抛业务异常。"""
        draft = self.repo.get_draft(draft_id)
        if not draft:
            raise ValueError("Content draft does not exist")
        return draft
