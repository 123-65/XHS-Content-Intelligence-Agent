from pathlib import Path

import pytest
from pydantic import ValidationError

from app.agent.contract_registry import validate_contract_registries
from app.agent.intents import BUSINESS_INTENTS, CONTROL_INTENTS, INTENT_TO_ALLOWED_RUNTIME_ACTIONS, validate_runtime_action
from app.agent.schemas.execution import ArtifactType, RuntimeAction, WorkflowStatus
from app.agent.schemas.interaction import PendingInteractionType
from app.agent.schemas.planning import PlanStatus
from app.agent.schemas.semantic import Intent, TaskSemanticFrame
from app.agent.skills.definitions import SkillId
from app.agent.skills.registry import INTENT_TO_SKILL, SKILL_REGISTRY, get_skill
from app.agent.tools.definitions import ToolEffect, ToolError, ToolName, ToolResult
from app.agent.tools.registry import TOOL_REGISTRY, get_tool
from app.agent.workflows.definitions import WorkflowId
from app.agent.workflows.registry import WORKFLOW_REGISTRY, get_workflow, validate_workflow_tools


AGENT_ROOT = Path(__file__).resolve().parents[1] / "app" / "agent"


def test_frozen_contract_counts_and_registry_closure():
    """验证所有冻结数量以及 Registry 引用闭包。"""
    validate_contract_registries()
    assert len(Intent) == 12
    assert len(RuntimeAction) == 7
    assert len(SKILL_REGISTRY) == 5
    assert len(WORKFLOW_REGISTRY) == 5
    assert len(TOOL_REGISTRY) == 17
    assert len(ArtifactType) == 7
    assert len(PendingInteractionType) == 2
    assert len(WorkflowStatus) == 7
    assert len(PlanStatus) == 3


def test_business_intent_skill_and_workflow_mapping_is_exact():
    """验证五个 Business Intent 严格一一映射到 Skill 和 Workflow。"""
    expected = {
        Intent.RESEARCH: (SkillId.RESEARCH, WorkflowId.RESEARCH_V1),
        Intent.CONTENT_STRATEGY: (SkillId.CONTENT_STRATEGY, WorkflowId.CONTENT_STRATEGY_V1),
        Intent.CONTENT_CREATE: (SkillId.CONTENT_CREATION, WorkflowId.CONTENT_CREATION_V1),
        Intent.CONTENT_REFINE: (SkillId.CONTENT_REFINEMENT, WorkflowId.CONTENT_REFINEMENT_V1),
        Intent.POST_PUBLISH_REVIEW: (SkillId.POST_PUBLISH_REVIEW, WorkflowId.POST_PUBLISH_REVIEW_V1),
    }
    assert set(INTENT_TO_SKILL) == BUSINESS_INTENTS
    for intent, (skill_id, workflow_id) in expected.items():
        assert INTENT_TO_SKILL[intent] == skill_id
        assert get_skill(skill_id).workflow_id == workflow_id.value
        assert get_workflow(workflow_id).skill_id == skill_id
    assert not set(CONTROL_INTENTS) & set(INTENT_TO_SKILL)


def test_runtime_action_rules_are_frozen():
    """验证聊天、业务、查询、更新、取消与未知意图的动作边界。"""
    assert INTENT_TO_ALLOWED_RUNTIME_ACTIONS[Intent.GENERAL_CHAT] == {RuntimeAction.RESPOND}
    assert INTENT_TO_ALLOWED_RUNTIME_ACTIONS[Intent.QUERY_PROFILE] == {RuntimeAction.QUERY}
    assert INTENT_TO_ALLOWED_RUNTIME_ACTIONS[Intent.QUERY_HISTORY] == {RuntimeAction.QUERY}
    assert INTENT_TO_ALLOWED_RUNTIME_ACTIONS[Intent.CANCEL_TASK] == {RuntimeAction.CANCEL}
    assert INTENT_TO_ALLOWED_RUNTIME_ACTIONS[Intent.UNKNOWN] == {RuntimeAction.CLARIFY}
    validate_runtime_action(Intent.CONTENT_CREATE, RuntimeAction.EXECUTE_PLAN)
    with pytest.raises(ValueError):
        validate_runtime_action(Intent.UPDATE_STRATEGY, RuntimeAction.EXECUTE_PLAN)


def test_workflow_tool_allowlists_are_exact():
    """验证五条 Workflow 的 Tool Allowlist 与冻结设计完全一致。"""
    expected = {
        WorkflowId.RESEARCH_V1: {
            ToolName.QUERY_GROWTH_CONTEXT,
            ToolName.QUERY_ARTIFACT,
            ToolName.RETRIEVE_RESEARCH_EVIDENCE,
            ToolName.COLLECT_XHS_NOTES,
            ToolName.COLLECT_XHS_ACCOUNTS,
            ToolName.ANALYZE_RESEARCH,
            ToolName.CREATE_RESEARCH_ARTIFACT,
        },
        WorkflowId.CONTENT_STRATEGY_V1: {
            ToolName.QUERY_GROWTH_CONTEXT,
            ToolName.QUERY_ARTIFACT,
            ToolName.GENERATE_CONTENT_STRATEGY,
            ToolName.CREATE_CONTENT_STRATEGY_ARTIFACT,
        },
        WorkflowId.CONTENT_CREATION_V1: {
            ToolName.QUERY_GROWTH_CONTEXT,
            ToolName.QUERY_ARTIFACT,
            ToolName.RETRIEVE_RESEARCH_EVIDENCE,
            ToolName.GENERATE_DRAFT,
            ToolName.REVIEW_DRAFT,
            ToolName.REVISE_DRAFT,
            ToolName.CREATE_DRAFT_VERSION,
        },
        WorkflowId.CONTENT_REFINEMENT_V1: {
            ToolName.QUERY_ARTIFACT,
            ToolName.QUERY_GROWTH_CONTEXT,
            ToolName.RETRIEVE_RESEARCH_EVIDENCE,
            ToolName.REVISE_DRAFT,
            ToolName.CREATE_DRAFT_VERSION,
        },
        WorkflowId.POST_PUBLISH_REVIEW_V1: {
            ToolName.QUERY_ARTIFACT,
            ToolName.QUERY_GROWTH_CONTEXT,
            ToolName.QUERY_POST_PUBLISH_METRICS,
            ToolName.COLLECT_XHS_NOTES,
            ToolName.ANALYZE_POST_PUBLISH_REVIEW,
            ToolName.CREATE_POST_PUBLISH_REVIEW_ARTIFACT,
            ToolName.CREATE_STRATEGY_CANDIDATE,
        },
    }
    for workflow_id, tools in expected.items():
        assert set(WORKFLOW_REGISTRY[workflow_id].allowed_tools) == tools


def test_tool_effects_are_exact_and_safe():
    """验证十七个 Tool 的 Effect，且不存在用户状态更新、外写和删除。"""
    read_tools = {
        ToolName.QUERY_GROWTH_CONTEXT,
        ToolName.QUERY_ARTIFACT,
        ToolName.RETRIEVE_RESEARCH_EVIDENCE,
        ToolName.QUERY_POST_PUBLISH_METRICS,
    }
    collect_tools = {ToolName.COLLECT_XHS_NOTES, ToolName.COLLECT_XHS_ACCOUNTS}
    pure_tools = {
        ToolName.ANALYZE_RESEARCH,
        ToolName.GENERATE_CONTENT_STRATEGY,
        ToolName.GENERATE_DRAFT,
        ToolName.REVIEW_DRAFT,
        ToolName.REVISE_DRAFT,
        ToolName.ANALYZE_POST_PUBLISH_REVIEW,
    }
    derived_tools = set(ToolName) - read_tools - collect_tools - pure_tools
    for tool_id in read_tools:
        assert TOOL_REGISTRY[tool_id].effect == ToolEffect.READ_INTERNAL
    for tool_id in collect_tools:
        assert TOOL_REGISTRY[tool_id].effect == ToolEffect.COLLECT_PUBLIC
    for tool_id in pure_tools:
        assert TOOL_REGISTRY[tool_id].effect == ToolEffect.PURE
    for tool_id in derived_tools:
        assert TOOL_REGISTRY[tool_id].effect == ToolEffect.CREATE_DERIVED
    forbidden = {ToolEffect.UPDATE_USER_STATE, ToolEffect.EXTERNAL_WRITE, ToolEffect.DESTRUCTIVE}
    assert not forbidden & {definition.effect for definition in TOOL_REGISTRY.values()}


def test_unknown_ids_and_unauthorized_tool_are_rejected():
    """验证未知 Skill、Workflow、Tool 以及越权 Tool 都被代码拒绝。"""
    with pytest.raises(ValueError):
        get_skill("viral_analysis")
    with pytest.raises(ValueError):
        get_workflow("FULL_GROWTH_WORKFLOW")
    with pytest.raises(ValueError):
        get_tool("save_strategy_memory")
    with pytest.raises(ValueError):
        validate_workflow_tools(WorkflowId.POST_PUBLISH_REVIEW_V1, [ToolName.GENERATE_DRAFT])
    with pytest.raises(ValueError):
        validate_workflow_tools(WorkflowId.RESEARCH_V1, ["unknown_tool"])


def test_tool_result_never_returns_fake_data_on_failure():
    """验证失败 ToolResult 必须携带安全错误且不能携带伪业务数据。"""
    error = ToolError(code="PROVIDER_TIMEOUT", category="PROVIDER", retryable=True, user_action="稍后重试", safe_message="公开数据源暂时不可用。")
    failed = ToolResult[dict](success=False, error=error)
    assert failed.data is None
    with pytest.raises(ValidationError):
        ToolResult[dict](success=False, data={"fake": "success"}, error=error)


def test_semantic_frame_rejects_router_generated_database_fields():
    """验证 Router 语义合同只保存自然语言引用，不接受数据库 ID 扩展字段。"""
    frame = TaskSemanticFrame(primary_intent=Intent.CONTENT_REFINE, references=["刚才那个草稿"], confidence=0.9)
    assert [item.raw_text for item in frame.references] == ["刚才那个草稿"]
    with pytest.raises(ValidationError):
        TaskSemanticFrame(primary_intent=Intent.CONTENT_REFINE, references=["刚才那个草稿"], confidence=0.9, draft_id=123)


def test_contract_packages_have_no_runtime_implementation_dependencies():
    """验证合同包不绑定 Service、Repository、Provider、LLM、Handler 或动态 Registry。"""
    contract_paths = [
        AGENT_ROOT / "intents.py",
        AGENT_ROOT / "contract_registry.py",
        *list((AGENT_ROOT / "schemas").glob("*.py")),
        *list((AGENT_ROOT / "skills").glob("*.py")),
        AGENT_ROOT / "workflows" / "__init__.py",
        AGENT_ROOT / "workflows" / "definitions.py",
        AGENT_ROOT / "workflows" / "registry.py",
        AGENT_ROOT / "tools" / "definitions.py",
        AGENT_ROOT / "tools" / "query_contracts.py",
        AGENT_ROOT / "tools" / "registry.py",
    ]
    forbidden = (
        "app.services",
        "app.repositories",
        "app.models",
        "app.llm",
        "app.collectors",
        "handler=",
        "MCPToolRegistry",
        "FallbackToolRegistry",
        "Dynamic Tool",
        "def execute(",
        "def run(",
    )
    offenders = []
    for path in contract_paths:
        text = path.read_text(encoding="utf-8")
        if any(token in text for token in forbidden):
            offenders.append(path.name)
    assert offenders == []
