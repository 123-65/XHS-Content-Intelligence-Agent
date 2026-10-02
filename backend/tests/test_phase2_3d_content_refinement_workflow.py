from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.agent.schemas.evidence import EvidenceRef, EvidenceType
from app.agent.schemas.execution import ArtifactRef, ArtifactType, WorkflowStatus
from app.agent.tools.access_scopes import EvidenceAccessScope
from app.agent.tools.artifact_contracts import CreateDraftVersionResult
from app.agent.tools.definitions import ToolError, ToolName, ToolResult
from app.agent.tools.execution_context import ToolExecutionContext
from app.agent.tools.query_contracts import ArtifactResult, EvidenceBundle, EvidenceItem
from app.agent.tools.semantic_contracts import SemanticRevisedDraftResult
from app.agent.workflows.content_refinement import ContentRefinementWorkflow, ContentRefinementWorkflowInput
from app.agent.workflows.evidence_partition import partition_opportunity_evidence
from app.agent.workflows.definitions import WorkflowId
from app.agent.workflows.implementation_registry import WORKFLOW_HANDLER_REGISTRY, build_workflow_handler
from app.agent.workflows.registry import WORKFLOW_REGISTRY


NOW = datetime.now(UTC)
EVIDENCE_REF = EvidenceRef(type=EvidenceType.NOTE, id=31)
BACKEND_ROOT = Path(__file__).resolve().parents[1]


def _error(code="TEST_ERROR", retryable=False):
    return ToolError(code=code, category="TEST", retryable=retryable, safe_message="失败")


def _draft(version=1, account=7, with_lineage=True):
    return {
        "account_ref": account,
        "strategy_artifact_ref": 501,
        "opportunity_ref": 601,
        "content_goal": "解释工程误区",
        "latest_draft_version_ref": 200 + version if with_lineage else None,
        "latest_version": version if with_lineage else None,
        "latest_content": {"title": f"V{version} 标题", "body": f"V{version} 正文", "tags": [f"v{version}"], "cta": "收藏"} if with_lineage else None,
        "latest_created_from": "GENERATED" if version == 1 else "USER_REVISION",
        "latest_parent_draft_ref": None if version == 1 else 199 + version,
        "status": "GENERATED" if version == 1 else "REVISED",
        "created_at": NOW.isoformat(),
        "updated_at": NOW.isoformat(),
    }


def _opportunity(strategy=501, goal="解释工程误区"):
    return {
        "account_ref": 7,
        "strategy_artifact_ref": strategy,
        "research_artifact_ref": 11,
        "source_opportunity_ref": 21,
        "opportunity": {
            "source_opportunity_id": 21,
            "topic": "Agent 项目避坑",
            "angle": "真实复盘",
            "target_audience": "新手用户",
            "content_goal": goal,
            "why_now": "用户正在追问",
            "evidence_refs": [
                {"kind": "research_report", "id": 11},
                {"kind": "content_opportunity", "id": 21},
                {"kind": "competitor_note", "id": 31},
            ],
            "suggested_hook": "三个常见误区",
            "constraints": ["明确样本边界"],
        },
        "retrievable_evidence_refs": [{"type": "NOTE", "id": 31}],
    }


class FakeRouter:
    def __init__(self, *, version=1, account=7, with_lineage=True, draft_failure=False, strategy=501, goal="解释工程误区", retrieval_failure=False, revision_failure=False, persistence_failure=False):
        self.calls = {name: 0 for name in ToolName}
        self.version = version
        self.account = account
        self.with_lineage = with_lineage
        self.draft_failure = draft_failure
        self.strategy = strategy
        self.goal = goal
        self.retrieval_failure = retrieval_failure
        self.revision_failure = revision_failure
        self.persistence_failure = persistence_failure
        self.revision_input = None
        self.persistence_input = None
        self.retrieval_input = None

    def build(self, name, context):
        router = self

        class Handler:
            def execute(self, data):
                router.calls[name] += 1
                if name == ToolName.QUERY_ARTIFACT:
                    if data.artifact_ref.type == ArtifactType.DRAFT:
                        if router.draft_failure:
                            return ToolResult(success=False, error=_error("CONTEXT_ERROR"))
                        return ToolResult(success=True, data=ArtifactResult(
                            artifact_ref=data.artifact_ref, artifact_type=ArtifactType.DRAFT,
                            version=f"v{router.version}", content=_draft(router.version, router.account, router.with_lineage),
                        ))
                    return ToolResult(success=True, data=ArtifactResult(
                        artifact_ref=data.artifact_ref, artifact_type=ArtifactType.CONTENT_OPPORTUNITY,
                        version="v1", content=_opportunity(router.strategy, router.goal),
                    ))
                if name == ToolName.RETRIEVE_RESEARCH_EVIDENCE:
                    router.retrieval_input = data
                    if router.retrieval_failure:
                        return ToolResult(success=False, error=_error("CONTEXT_ERROR"))
                    return ToolResult(success=True, data=EvidenceBundle(
                        items=[EvidenceItem(evidence_ref=EVIDENCE_REF, evidence_type=EvidenceType.NOTE, content="真实正文", provenance="TEST")],
                        purpose=data.purpose,
                    ))
                if name == ToolName.REVISE_DRAFT:
                    router.revision_input = data
                    if router.revision_failure:
                        return ToolResult(success=False, error=_error("SEMANTIC_ERROR"))
                    return ToolResult(success=True, data=SemanticRevisedDraftResult(
                        title=f"V{router.version + 1} 标题", body="修订正文", tags=["修订"], cta="收藏",
                        applied_changes=["按用户反馈修改"], strategy_ref=data.source_draft.strategy_ref,
                        opportunity_ref=data.source_draft.opportunity_ref, content_goal=data.source_draft.content_goal,
                    ))
                if name == ToolName.CREATE_DRAFT_VERSION:
                    router.persistence_input = data.root
                    if router.persistence_failure:
                        return ToolResult(success=False, error=_error("PERSISTENCE_ERROR"))
                    return ToolResult(success=True, data=CreateDraftVersionResult(
                        draft_ref=data.root.draft_ref,
                        draft_version_ref=300 + router.version,
                        version=router.version + 1,
                        parent_draft_ref=data.root.parent_draft_ref,
                        created_from="USER_REVISION",
                    ))
                raise AssertionError(name)

        return Handler()


def _input(*, draft=100, feedback="把开头写得更直接", base=None, **extra):
    return ContentRefinementWorkflowInput(
        account_ref=7, draft_ref=draft, user_feedback=feedback,
        base_draft_version_ref=base, constraints=["不夸大"], **extra,
    )


def _context(authorized=True):
    refs = frozenset({EVIDENCE_REF}) if authorized else frozenset()
    return ToolExecutionContext(db=object(), evidence_access_scope=EvidenceAccessScope(authorized_refs=refs))


def _run(monkeypatch, router, data=None, context=None):
    monkeypatch.setattr("app.agent.workflows.content_refinement.build_tool_handler", router.build)
    return ContentRefinementWorkflow().execute(data or _input(), context or _context())


@pytest.mark.parametrize(("current", "expected"), [(1, 2), (2, 3), (8, 9)])
def test_version_progression_keeps_root_parent_and_server_provenance(monkeypatch, current, expected):
    router = FakeRouter(version=current)
    result = _run(monkeypatch, router, _input(base=200 + current))
    assert result.status == WorkflowStatus.SUCCESS
    assert result.draft_ref == 100 and result.version == expected
    assert result.parent_draft_ref == 200 + current
    assert result.created_from == "USER_REVISION"
    assert router.persistence_input.action == "APPEND"
    assert router.persistence_input.draft_ref == 100
    assert router.persistence_input.parent_draft_ref == 200 + current
    assert router.persistence_input.created_from == "USER_REVISION"
    assert router.revision_input.source_draft.strategy_ref == "CONTENT_STRATEGY:501"
    assert router.revision_input.source_draft.opportunity_ref == 601
    assert router.revision_input.source_draft.content_goal == "解释工程误区"
    assert router.revision_input.opportunity.source_opportunity_id == 21
    assert router.revision_input.context_refs[1] == ArtifactRef(type=ArtifactType.CONTENT_OPPORTUNITY, id=601)
    assert router.retrieval_input.evidence_refs == [EVIDENCE_REF]
    assert [ref.model_dump(mode="json") for ref in router.revision_input.grounding_refs] == [
        {"kind": "research_report", "id": 11},
        {"kind": "content_opportunity", "id": 21},
    ]


def test_missing_draft_or_feedback_waits_without_revision(monkeypatch):
    for data in (_input(draft=None), _input(feedback="   ")):
        router = FakeRouter()
        result = _run(monkeypatch, router, data)
        assert result.status == WorkflowStatus.WAITING_USER and result.error is None
        assert result.pending_interaction is not None
        assert router.calls[ToolName.REVISE_DRAFT] == 0
        assert router.calls[ToolName.CREATE_DRAFT_VERSION] == 0


def test_invalid_account_and_missing_version_lineage_fail(monkeypatch):
    missing = _run(monkeypatch, FakeRouter(draft_failure=True))
    assert missing.status == WorkflowStatus.FAILED
    account = _run(monkeypatch, FakeRouter(account=8))
    assert account.status == WorkflowStatus.FAILED
    lineage = _run(monkeypatch, FakeRouter(with_lineage=False))
    assert lineage.status == WorkflowStatus.FAILED
    assert lineage.error.code == "DRAFT_VERSION_LINEAGE_MISSING"


def test_base_version_conflict_stops_before_revision(monkeypatch):
    router = FakeRouter(version=3)
    result = _run(monkeypatch, router, _input(base=202))
    assert result.status == WorkflowStatus.FAILED
    assert result.error.code == "DRAFT_VERSION_CONFLICT"
    assert router.calls[ToolName.REVISE_DRAFT] == 0
    assert router.calls[ToolName.CREATE_DRAFT_VERSION] == 0


def test_opportunity_identity_mismatches_fail(monkeypatch):
    for router in (FakeRouter(strategy=502), FakeRouter(goal="另一个目标")):
        result = _run(monkeypatch, router)
        assert result.status == WorkflowStatus.FAILED
        assert router.calls[ToolName.REVISE_DRAFT] == 0


def test_cross_research_evidence_and_retrieval_failures_stop_revision(monkeypatch):
    opportunity = _opportunity()
    opportunity["opportunity"]["evidence_refs"].append({"kind": "competitor_note", "id": 32})
    from app.agent.tools.query_contracts import ContentOpportunityArtifactView
    with pytest.raises(ValueError, match="当前 Research 之外"):
        partition_opportunity_evidence(ContentOpportunityArtifactView.model_validate(opportunity))
    retrieval_router = FakeRouter(retrieval_failure=True)
    retrieval = _run(monkeypatch, retrieval_router)
    assert retrieval.status == WorkflowStatus.FAILED
    assert retrieval_router.calls[ToolName.REVISE_DRAFT] == 0


def test_revision_and_persistence_failures_do_not_fabricate_version(monkeypatch):
    revision_router = FakeRouter(revision_failure=True)
    revision = _run(monkeypatch, revision_router)
    assert revision.status == WorkflowStatus.FAILED and revision.draft_version_ref is None
    assert revision_router.calls[ToolName.CREATE_DRAFT_VERSION] == 0
    persistence_router = FakeRouter(persistence_failure=True)
    persistence = _run(monkeypatch, persistence_router)
    assert persistence.status == WorkflowStatus.FAILED and persistence.draft_version_ref is None


def test_resume_completed_is_idempotent(monkeypatch):
    router = FakeRouter()
    monkeypatch.setattr("app.agent.workflows.content_refinement.build_tool_handler", router.build)
    workflow = ContentRefinementWorkflow()
    completed = workflow.execute(_input(), _context())
    again = workflow.resume(completed.state, _input(), _context())
    assert again.status == WorkflowStatus.SUCCESS
    assert router.calls[ToolName.REVISE_DRAFT] == 1
    assert router.calls[ToolName.CREATE_DRAFT_VERSION] == 1
    assert router.calls[ToolName.QUERY_ARTIFACT] == 2


def test_stale_resume_requeries_draft_and_rejects_branch(monkeypatch):
    router = FakeRouter(version=2)
    monkeypatch.setattr("app.agent.workflows.content_refinement.build_tool_handler", router.build)
    workflow = ContentRefinementWorkflow()
    waiting = workflow.execute(_input(feedback=""), _context())
    assert waiting.status == WorkflowStatus.WAITING_USER and waiting.state.latest_draft_version_ref == 202
    router.version = 3
    stale = workflow.resume(waiting.state, _input(feedback="明确修改开头"), _context())
    assert stale.status == WorkflowStatus.FAILED and stale.error.code == "DRAFT_VERSION_CONFLICT"
    assert router.calls[ToolName.REVISE_DRAFT] == 0
    assert router.calls[ToolName.CREATE_DRAFT_VERSION] == 0


def test_created_from_is_not_user_input_and_forbidden_tools_never_run(monkeypatch):
    with pytest.raises(ValidationError):
        ContentRefinementWorkflowInput.model_validate({
            "account_ref": 7, "draft_ref": 100, "user_feedback": "修改", "created_from": "REVIEW_REVISION"
        })
    router = FakeRouter()
    assert _run(monkeypatch, router).status == WorkflowStatus.SUCCESS
    for name in (ToolName.QUERY_GROWTH_CONTEXT, ToolName.GENERATE_DRAFT, ToolName.REVIEW_DRAFT):
        assert router.calls[name] == 0


def test_registry_retry_and_architecture_boundaries(monkeypatch):
    assert len(WORKFLOW_REGISTRY) == 5 and len(WORKFLOW_HANDLER_REGISTRY) == 5
    assert isinstance(build_workflow_handler(WorkflowId.CONTENT_REFINEMENT_V1), ContentRefinementWorkflow)

    router = FakeRouter()
    base_build = router.build

    def build(name, context):
        handler = base_build(name, context)
        if name != ToolName.QUERY_ARTIFACT:
            return handler
        original = handler.execute

        def execute(data):
            if router.calls[name] == 0:
                router.calls[name] += 1
                return ToolResult(success=False, error=_error("TEMPORARY", retryable=True))
            return original(data)

        handler.execute = execute
        return handler

    monkeypatch.setattr("app.agent.workflows.content_refinement.build_tool_handler", build)
    assert ContentRefinementWorkflow().execute(_input(), _context()).status == WorkflowStatus.SUCCESS
    assert router.calls[ToolName.QUERY_ARTIFACT] == 3

    source = (BACKEND_ROOT / "app" / "agent" / "workflows" / "content_refinement.py").read_text(encoding="utf-8")
    forbidden = (
        "app.repositories", "sqlalchemy", "app.llm", "fastapi", "HTTPException",
        "ResearchWorkflow(", "ContentStrategyWorkflow(", "ContentCreationWorkflow(",
        "collect_xhs_", "analyze_research", "generate_content_strategy", "generate_draft", "review_draft",
    )
    assert not [token for token in forbidden if token in source]
    assert "build_tool_handler" in source
