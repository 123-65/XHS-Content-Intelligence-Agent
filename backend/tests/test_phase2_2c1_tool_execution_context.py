from pathlib import Path

import pytest

from app.agent.schemas.evidence import EvidenceRef, EvidenceType
from app.agent.tools.access_scopes import EvidenceAccessScope
from app.agent.tools.definitions import ToolEffect, ToolName
from app.agent.tools.execution_context import ToolExecutionContext
from app.agent.tools.implementation_registry import TOOL_HANDLER_REGISTRY, build_tool_handler
from app.agent.tools.registry import TOOL_REGISTRY
from app.agent.tools.xhs_contracts import CollectionAccessScope, CollectionAuthorizationSource


TOOLS_ROOT = Path(__file__).resolve().parents[1] / "app" / "agent" / "tools"
FAKE_DB = object()


def _evidence_scope() -> EvidenceAccessScope:
    """构造由服务器端预先确认的证据授权范围。"""
    return EvidenceAccessScope(authorized_refs=frozenset({EvidenceRef(type=EvidenceType.NOTE, id=11)}))


def _collection_scope() -> CollectionAccessScope:
    """构造由服务器端预先确认的采集授权范围。"""
    return CollectionAccessScope(
        workspace_account_ref=1,
        authorization_source=CollectionAuthorizationSource.USER_PROVIDED,
        allowed_note_urls=("https://www.xiaohongshu.com/explore/note-1",),
        allowed_profile_urls=("https://www.xiaohongshu.com/user/profile/user-1",),
    )


@pytest.mark.parametrize(
    "tool_name",
    [ToolName.QUERY_GROWTH_CONTEXT, ToolName.QUERY_ARTIFACT, ToolName.QUERY_POST_PUBLISH_METRICS],
)
def test_regular_query_tools_build_with_database_context(tool_name):
    """验证普通 Query Tool 只需可信数据库会话即可构建。"""
    handler = build_tool_handler(tool_name, ToolExecutionContext(db=FAKE_DB))
    assert handler.name == tool_name.value


def test_evidence_query_requires_scope_during_construction():
    """验证 Evidence Tool 只接受上下文中已存在的 Scope，缺失时立即拒绝。"""
    scope = _evidence_scope()
    handler = build_tool_handler(
        ToolName.RETRIEVE_RESEARCH_EVIDENCE,
        ToolExecutionContext(db=FAKE_DB, evidence_access_scope=scope),
    )
    assert handler.access_scope is scope
    with pytest.raises(ValueError, match="EvidenceAccessScope"):
        build_tool_handler(ToolName.RETRIEVE_RESEARCH_EVIDENCE, ToolExecutionContext(db=FAKE_DB))


@pytest.mark.parametrize("tool_name", [ToolName.COLLECT_XHS_NOTES, ToolName.COLLECT_XHS_ACCOUNTS])
def test_collection_tools_require_scope_during_construction(tool_name):
    """验证 Collection Tool 原样接收可信 Scope，缺失时在 Collector 执行前拒绝。"""
    scope = _collection_scope()
    handler = build_tool_handler(tool_name, ToolExecutionContext(db=FAKE_DB, collection_access_scope=scope))
    assert handler.access_scope is scope
    with pytest.raises(ValueError, match="CollectionAccessScope"):
        build_tool_handler(tool_name, ToolExecutionContext(db=FAKE_DB))


@pytest.mark.parametrize(
    "tool_name",
    [
        ToolName.ANALYZE_RESEARCH,
        ToolName.GENERATE_CONTENT_STRATEGY,
        ToolName.GENERATE_DRAFT,
        ToolName.REVIEW_DRAFT,
        ToolName.REVISE_DRAFT,
        ToolName.ANALYZE_POST_PUBLISH_REVIEW,
    ],
)
def test_semantic_tools_build_from_the_same_entrypoint(tool_name):
    """验证六个 Semantic Tool 使用同一构建入口且不需授权 Scope。"""
    assert build_tool_handler(tool_name, ToolExecutionContext(db=None)).name == tool_name.value


def test_artifact_uses_database_context_and_unknown_tools_remain_rejected():
    """验证 Artifact Tool 使用同一构建入口，未知 Tool 仍不能动态注册。"""
    context = ToolExecutionContext(db=FAKE_DB)
    assert build_tool_handler(ToolName.CREATE_RESEARCH_ARTIFACT, context).name == "create_research_artifact"
    with pytest.raises(ValueError, match="尚未实现"):
        build_tool_handler("unknown_tool", context)


def test_registry_counts_and_categories_remain_frozen():
    """验证最终 Tool Layer 的合同、实现数量与 Effect 分类完整闭合。"""
    assert len(TOOL_REGISTRY) == 17
    assert len(TOOL_HANDLER_REGISTRY) == 17
    assert sum(item.effect == ToolEffect.READ_INTERNAL for item in TOOL_REGISTRY.values()) == 4
    assert sum(item.effect == ToolEffect.COLLECT_PUBLIC for item in TOOL_REGISTRY.values()) == 2
    assert sum(item.effect == ToolEffect.PURE for item in TOOL_REGISTRY.values()) == 6
    assert sum(item.effect == ToolEffect.CREATE_DERIVED for item in TOOL_REGISTRY.values()) == 5


def test_tool_inputs_cannot_contain_or_construct_execution_context():
    """验证用户或 LLM 可提交的 Tool Input 无法携带或构造可信执行上下文。"""
    forbidden_fields = {"execution_context", "evidence_access_scope", "collection_access_scope"}
    for filename in ("query_contracts.py", "xhs_contracts.py", "semantic_contracts.py"):
        source = (TOOLS_ROOT / filename).read_text(encoding="utf-8")
        assert "ToolExecutionContext" not in source
        assert "ToolExecutionContext(" not in source
    for definition in TOOL_REGISTRY.values():
        assert forbidden_fields.isdisjoint(definition.input_model.model_fields)


def test_tool_layer_has_no_runtime_workflow_http_or_dynamic_registration_dependency():
    """验证 Tool 层不反向依赖 Runtime、Workflow、HTTP 或动态注册机制。"""
    checked = ("execution_context.py", "implementation_registry.py", "query_tools.py", "xhs_tools.py", "semantic_tools.py")
    forbidden = ("app.agent.runtime", "app.agent.workflows", "fastapi", "HTTPException", "register_tool(", "runtime plugin")
    for filename in checked:
        source = (TOOLS_ROOT / filename).read_text(encoding="utf-8")
        assert not [token for token in forbidden if token in source], filename


def test_execution_context_contains_only_frozen_server_dependencies():
    """验证执行上下文不携带 Conversation、Planner 或 Workflow State。"""
    assert ToolExecutionContext.__dataclass_params__.frozen is True
    assert set(ToolExecutionContext.__dataclass_fields__) == {
        "db",
        "evidence_access_scope",
        "collection_access_scope",
        "runtime_identity",
    }
