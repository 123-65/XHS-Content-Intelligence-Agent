from app.agent.intents import BUSINESS_INTENTS, INTENT_TO_ALLOWED_RUNTIME_ACTIONS
from app.agent.schemas.semantic import Intent
from app.agent.skills.registry import INTENT_TO_SKILL, SKILL_REGISTRY
from app.agent.tools.registry import TOOL_REGISTRY
from app.agent.workflows.definitions import WorkflowId
from app.agent.workflows.registry import WORKFLOW_REGISTRY


def validate_contract_registries() -> None:
    """整体校验冻结 Registry 的数量、映射闭包与引用完整性。"""
    if len(Intent) != 12:
        raise ValueError("Intent Count 必须为 12")
    if len(INTENT_TO_ALLOWED_RUNTIME_ACTIONS) != len(Intent):
        raise ValueError("每个 Intent 都必须声明 Runtime Action Rules")
    if set(INTENT_TO_SKILL) != BUSINESS_INTENTS:
        raise ValueError("Business Intent 必须全部且仅映射一个 Skill")
    if len(SKILL_REGISTRY) != 5:
        raise ValueError("Business Skill Count 必须为 5")
    if len(WORKFLOW_REGISTRY) != 5:
        raise ValueError("Workflow Count 必须为 5")
    if len(TOOL_REGISTRY) != 17:
        raise ValueError("Core Tool Count 必须为 17")
    for skill_id, skill in SKILL_REGISTRY.items():
        try:
            workflow = WORKFLOW_REGISTRY[WorkflowId(skill.workflow_id)]
        except (ValueError, KeyError) as exc:
            raise ValueError(f"Skill without Workflow: {skill_id}") from exc
        if workflow.skill_id != skill_id:
            raise ValueError(f"Skill 与 Workflow 反向映射不一致: {skill_id}")
    for workflow in WORKFLOW_REGISTRY.values():
        if not workflow.allowed_tools:
            raise ValueError(f"Workflow without Tool Allowlist: {workflow.id}")
        unknown = set(workflow.allowed_tools) - set(TOOL_REGISTRY)
        if unknown:
            raise ValueError(f"Workflow 引用了未知 Tool: {unknown}")
