"""五个冻结业务 Skill 的静态合同包。"""

from app.agent.skills.definitions import SkillDefinition, SkillId
from app.agent.skills.registry import INTENT_TO_SKILL, SKILL_REGISTRY, get_skill

__all__ = ["INTENT_TO_SKILL", "SKILL_REGISTRY", "SkillDefinition", "SkillId", "get_skill"]
