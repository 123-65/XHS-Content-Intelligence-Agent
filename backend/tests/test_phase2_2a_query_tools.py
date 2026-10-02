from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from app.agent.schemas.evidence import EvidenceRef, EvidenceType
from app.agent.schemas.execution import ArtifactRef, ArtifactType
from app.agent.tools.definitions import ToolEffect, ToolName
from app.agent.tools.execution_context import ToolExecutionContext
from app.agent.tools.implementation_registry import TOOL_HANDLER_REGISTRY, build_tool_handler
from app.agent.tools.query_contracts import (
    GrowthContextSection,
    QueryArtifactInput,
    QueryGrowthContextInput,
    QueryPostPublishMetricsInput,
    RetrieveResearchEvidenceInput,
)
from app.agent.tools.query_tools import (
    ArtifactRecord,
    EvidenceAccessScope,
    EvidenceRecord,
    QueryArtifactTool,
    QueryGrowthContextTool,
    QueryPostPublishMetricsTool,
    QueryToolFailure,
    RetrieveResearchEvidenceTool,
)
from app.agent.tools.registry import TOOL_REGISTRY
from app.agent.workflows.definitions import WorkflowId
from app.agent.workflows.registry import WORKFLOW_REGISTRY


AGENT_ROOT = Path(__file__).resolve().parents[1] / "app" / "agent"


class FakeQueryFacade:
    """为四个只读 Tool 提供可控的 Canonical Data Layer 测试桩。"""

    def __init__(self):
        """准备账号、Artifact、Evidence 与指标快照。"""
        now = datetime.now(UTC)
        self.now = now
        self.account = SimpleNamespace(
            id=7,
            account_name="求职 Agent",
            platform="xhs",
            positioning="Agent 项目求职",
            persona=None,
            business_model=None,
            main_product=None,
            monetization_goal=None,
            target_audience="应届开发者",
            primary_goal="lead",
            account_stage="STARTUP",
            updated_at=now,
        )
        self.memory = SimpleNamespace(id=9, memory_type="CONTENT_DIRECTION", summary="多写实操", pattern="实操清单", confidence=0.8, updated_at=now)
        self.note = SimpleNamespace(id=31, account_id=7, draft_id=72, publish_url="https://www.xiaohongshu.com/explore/31")
        self.public = SimpleNamespace(id=41, collected_at=now, view_count=1000, like_count=120, collect_count=43, comment_count=8, share_count=5, follow_count=3, profile_visit_count=22)
        self.private = SimpleNamespace(id=51, collected_at=now, raw_snapshot={"provided_fields": ["dm_count"], "values": {"dm_count": 4}})

    def get_account(self, account_ref):
        """读取测试账号。"""
        return self.account if account_ref == 7 else None

    def list_strategy_memories(self, account_ref):
        """读取测试策略记忆。"""
        return [self.memory] if account_ref == 7 else []

    def get_artifact(self, account_ref, artifact_ref):
        """读取测试 Artifact，并模拟权限错误。"""
        if account_ref == 8:
            raise QueryToolFailure("PERMISSION_ERROR", "PERMISSION", "当前账号无权读取该资源。")
        if artifact_ref == ArtifactRef(type=ArtifactType.DRAFT, id=72):
            return ArtifactRecord(content={"title": "Draft", "body": "正文"}, version="v3", created_at=self.now)
        return None

    def get_evidence(self, account_ref, evidence_ref):
        """读取测试 Evidence，并模拟权限错误。"""
        if account_ref == 8:
            raise QueryToolFailure("PERMISSION_ERROR", "PERMISSION", "当前账号无权读取该资源。")
        if evidence_ref == EvidenceRef(type=EvidenceType.NOTE, id=3):
            return EvidenceRecord(content="A" * 300, structured_facts={"likes": 10}, provenance="XHS_MCP", source_ref="https://xhs/note/3", observed_at=self.now)
        return None

    def get_published_note(self, note_ref):
        """读取测试 Published Note。"""
        return self.note if note_ref == 31 else None

    def list_public_metrics(self, note_ref):
        """读取测试公开指标。"""
        return [self.public] if note_ref == 31 else []

    def list_private_metrics(self, note_ref):
        """读取测试私域指标。"""
        return [self.private] if note_ref == 31 else []

    def resolve_published_lineage(self, note):
        """模拟没有历史 Version binding 的兼容 Published Note。"""
        return ({"binding_ref": None, "draft_ref": note.draft_id, "version_number": None, "publish_package_ref": None}, None)


def test_contract_patch_adds_evidence_retrieval_without_new_tool():
    """验证 2.1.1 只扩展 Draft Allowlist，Core Tool 数仍为十七。"""
    assert len(TOOL_REGISTRY) == 17
    assert ToolName.RETRIEVE_RESEARCH_EVIDENCE in WORKFLOW_REGISTRY[WorkflowId.CONTENT_CREATION_V1].allowed_tools


def test_query_growth_context_success_missing_and_not_found():
    """验证增长上下文类型化返回、可选字段 UNKNOWN 和账号不存在错误。"""
    facade = FakeQueryFacade()
    tool = QueryGrowthContextTool(facade=facade)
    result = tool.execute(QueryGrowthContextInput(account_ref=7, requested_sections=list(GrowthContextSection)))
    assert result.success is True
    assert result.error is None
    assert result.data.customer_model["target_audience"] == "应届开发者"
    assert GrowthContextSection.BUSINESS_PROFILE in result.data.missing_sections
    assert result.data.business_profile is None
    assert result.data.strategy_memory[0]["ref"] == 9

    missing = tool.execute(QueryGrowthContextInput(account_ref=999, requested_sections=[GrowthContextSection.ACCOUNT_PROFILE]))
    assert missing.success is False
    assert missing.data is None
    assert missing.error.code == "CONTEXT_ERROR"


def test_query_artifact_success_not_found_permission_and_type_mismatch():
    """验证 Artifact 读取、找不到、权限错误和类型不匹配。"""
    tool = QueryArtifactTool(facade=FakeQueryFacade())
    found = tool.execute(QueryArtifactInput(account_ref=7, artifact_ref=ArtifactRef(type=ArtifactType.DRAFT, id=72), expected_type=ArtifactType.DRAFT))
    assert found.success is True
    assert found.data.version == "v3"
    not_found = tool.execute(QueryArtifactInput(account_ref=7, artifact_ref=ArtifactRef(type=ArtifactType.RESEARCH, id=999)))
    assert not_found.error.code == "CONTEXT_ERROR"
    forbidden = tool.execute(QueryArtifactInput(account_ref=8, artifact_ref=ArtifactRef(type=ArtifactType.DRAFT, id=72)))
    assert forbidden.error.code == "PERMISSION_ERROR"
    with pytest.raises(ValidationError):
        QueryArtifactInput(account_ref=7, artifact_ref=ArtifactRef(type=ArtifactType.DRAFT, id=72), expected_type=ArtifactType.RESEARCH)


def test_retrieve_evidence_success_not_found_permission_whitelist_and_limits():
    """验证 Evidence 白名单、权限、找不到及内容长度边界。"""
    facade = FakeQueryFacade()
    note_ref = EvidenceRef(type=EvidenceType.NOTE, id=3)
    tool = RetrieveResearchEvidenceTool(facade=facade, access_scope=EvidenceAccessScope(authorized_refs=frozenset({note_ref})))
    data = RetrieveResearchEvidenceInput(account_ref=7, evidence_refs=[note_ref], purpose="生成草稿", max_content_chars=100)
    result = tool.execute(data)
    assert result.success is True
    assert len(result.data.items[0].content) == 100
    assert result.data.truncated is True

    unauthorized_ref = EvidenceRef(type=EvidenceType.NOTE, id=4)
    unauthorized = tool.execute(data.model_copy(update={"evidence_refs": [unauthorized_ref]}))
    assert unauthorized.error.code == "VALIDATION_ERROR"
    missing_tool = RetrieveResearchEvidenceTool(facade=facade, access_scope=EvidenceAccessScope(authorized_refs=frozenset({unauthorized_ref})))
    missing = missing_tool.execute(data.model_copy(update={"evidence_refs": [unauthorized_ref]}))
    assert missing.error.code == "CONTEXT_ERROR"
    forbidden = tool.execute(data.model_copy(update={"account_ref": 8}))
    assert forbidden.error.code == "PERMISSION_ERROR"


def test_evidence_input_cannot_self_authorize():
    """验证不可信 Tool Input 已无法声明自己的证据白名单。"""
    note_ref = EvidenceRef(type=EvidenceType.NOTE, id=3)
    with pytest.raises(ValidationError):
        RetrieveResearchEvidenceInput(
            account_ref=7,
            evidence_refs=[note_ref],
            authorized_evidence_refs=[note_ref],
            purpose="生成草稿",
        )
    denied = RetrieveResearchEvidenceTool(facade=FakeQueryFacade()).execute(
        RetrieveResearchEvidenceInput(account_ref=7, evidence_refs=[note_ref], purpose="生成草稿")
    )
    assert denied.error.code == "VALIDATION_ERROR"


def test_query_metrics_preserves_unknown_private_values_and_does_not_refresh():
    """验证指标只读查询及未提供私域字段不被转换为零。"""
    facade = FakeQueryFacade()
    tool = QueryPostPublishMetricsTool(facade=facade)
    data = QueryPostPublishMetricsInput(account_ref=7, published_note_ref=31, window_start=facade.now - timedelta(days=1), window_end=facade.now + timedelta(days=1), include_private=True)
    result = tool.execute(data)
    assert result.success is True
    assert result.data.public_metric_snapshot_ref == 41
    assert result.data.private_metric_snapshot_ref == 51
    assert result.data.public_metrics["likes"].value == 120
    assert result.data.private_metrics["dm_count"].value == 4
    assert result.data.private_metrics["deal_count"].value is None
    assert result.data.private_metrics["deal_count"].provenance == "UNKNOWN"
    assert "deal_count" in result.data.missing_metrics

    facade.private = None
    facade.list_private_metrics = lambda note_ref: []
    without_private = tool.execute(data)
    assert without_private.data.private_metrics["dm_count"].value is None
    assert without_private.data.private_metrics["dm_count"].provenance == "UNKNOWN"


def test_query_metrics_not_found_permission_and_window_errors():
    """验证指标查询的资源、权限和时间窗口错误。"""
    facade = FakeQueryFacade()
    tool = QueryPostPublishMetricsTool(facade=facade)
    base = {"account_ref": 7, "published_note_ref": 31, "window_start": facade.now - timedelta(days=1), "window_end": facade.now + timedelta(days=1)}
    missing_note = tool.execute(QueryPostPublishMetricsInput(**{**base, "published_note_ref": 999}))
    assert missing_note.error.code == "CONTEXT_ERROR"
    forbidden = tool.execute(QueryPostPublishMetricsInput(**{**base, "account_ref": 8}))
    assert forbidden.error.code == "PERMISSION_ERROR"
    empty_window = tool.execute(QueryPostPublishMetricsInput(**{**base, "window_start": facade.now - timedelta(days=3), "window_end": facade.now - timedelta(days=2)}))
    assert empty_window.success is True
    assert empty_window.data.public_metrics_status == "UNKNOWN"
    assert empty_window.data.public_metrics == {}
    assert empty_window.data.public_metric_snapshot_ref is None
    assert empty_window.data.private_metric_snapshot_ref is None
    assert "public_metrics" in empty_window.data.missing_metrics


def test_static_implementation_registry_keeps_four_query_tools():
    """验证 Implementation Registry 始终保留四个已完成 Query Tool。"""
    assert {
        ToolName.QUERY_GROWTH_CONTEXT,
        ToolName.QUERY_ARTIFACT,
        ToolName.RETRIEVE_RESEARCH_EVIDENCE,
        ToolName.QUERY_POST_PUBLISH_METRICS,
    }.issubset(TOOL_HANDLER_REGISTRY)
    query_names = {name for name in TOOL_HANDLER_REGISTRY if TOOL_REGISTRY[name].effect == ToolEffect.READ_INTERNAL}
    assert len(query_names) == 4
    with pytest.raises(ValueError):
        build_tool_handler(ToolName.CREATE_DRAFT_VERSION, ToolExecutionContext(db=None))


def test_query_tool_architecture_boundaries():
    """验证 Query Tool 不依赖 LLM、Provider、Workflow、HTTP 或其他 Tool 实现。"""
    source = (AGENT_ROOT / "tools" / "query_tools.py").read_text(encoding="utf-8")
    forbidden = (
        "app.llm",
        "app.collectors",
        "app.agent.workflows",
        "fastapi",
        "HTTPException",
        "XiaohongshuMcpProvider",
        "collect_public_note_metrics",
        ".execute(",
    )
    assert [token for token in forbidden if token in source] == []
