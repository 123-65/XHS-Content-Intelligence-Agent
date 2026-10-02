from types import MappingProxyType

from app.agent.schemas.semantic import Intent
from app.agent.skills.definitions import SkillDefinition, SkillId


SKILL_REGISTRY = MappingProxyType(
    {
        SkillId.RESEARCH: SkillDefinition(
            id=SkillId.RESEARCH,
            description="对用户授权材料执行可追溯研究分析。",
            input_requirements=("account_context", "authorized_research_scope"),
            output_type="RESEARCH",
            workflow_id="RESEARCH_V1",
        ),
        SkillId.CONTENT_STRATEGY: SkillDefinition(
            id=SkillId.CONTENT_STRATEGY,
            description="基于上下文与研究产物形成内容策略。",
            input_requirements=("growth_context", "research_artifact"),
            output_type="CONTENT_STRATEGY",
            workflow_id="CONTENT_STRATEGY_V1",
        ),
        SkillId.CONTENT_CREATION: SkillDefinition(
            id=SkillId.CONTENT_CREATION,
            description="基于已选机会和策略创建新 Draft。",
            input_requirements=("growth_context", "content_opportunity"),
            output_type="DRAFT",
            workflow_id="CONTENT_CREATION_V1",
        ),
        SkillId.CONTENT_REFINEMENT: SkillDefinition(
            id=SkillId.CONTENT_REFINEMENT,
            description="按明确反馈修改已有 Draft。",
            input_requirements=("draft_artifact", "revision_request"),
            output_type="DRAFT",
            workflow_id="CONTENT_REFINEMENT_V1",
        ),
        SkillId.POST_PUBLISH_REVIEW: SkillDefinition(
            id=SkillId.POST_PUBLISH_REVIEW,
            description="基于已绑定笔记和指标形成发布后复盘。",
            input_requirements=("published_note", "post_publish_metrics"),
            output_type="POST_PUBLISH_REVIEW",
            workflow_id="POST_PUBLISH_REVIEW_V1",
        ),
    }
)

INTENT_TO_SKILL = MappingProxyType(
    {
        Intent.RESEARCH: SkillId.RESEARCH,
        Intent.CONTENT_STRATEGY: SkillId.CONTENT_STRATEGY,
        Intent.CONTENT_CREATE: SkillId.CONTENT_CREATION,
        Intent.CONTENT_REFINE: SkillId.CONTENT_REFINEMENT,
        Intent.POST_PUBLISH_REVIEW: SkillId.POST_PUBLISH_REVIEW,
    }
)


def get_skill(skill_id: SkillId | str) -> SkillDefinition:
    """读取冻结 Skill；未知标识必须明确拒绝。"""
    try:
        normalized = SkillId(skill_id)
        return SKILL_REGISTRY[normalized]
    except (ValueError, KeyError) as exc:
        raise ValueError(f"Unknown Skill ID: {skill_id}") from exc
