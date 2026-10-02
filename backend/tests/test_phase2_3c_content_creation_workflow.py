from datetime import UTC, datetime
from pathlib import Path

from app.agent.schemas.evidence import EvidenceRef, EvidenceType
from app.agent.schemas.execution import ArtifactRef, ArtifactType, WorkflowStatus
from app.agent.tools.access_scopes import EvidenceAccessScope
from app.agent.tools.artifact_contracts import CreateDraftVersionResult
from app.agent.tools.definitions import ToolError, ToolName, ToolResult
from app.agent.tools.execution_context import ToolExecutionContext
from app.agent.tools.query_contracts import (
    ArtifactResult,
    ContentOpportunityArtifactView,
    EvidenceBundle,
    EvidenceItem,
    GrowthContextResult,
)
from app.agent.tools.semantic_contracts import SemanticDraftResult
from app.agent.workflows.content_creation import ContentCreationWorkflow, ContentCreationWorkflowInput
from app.agent.workflows.evidence_partition import partition_opportunity_evidence
from app.agent.workflows.definitions import WorkflowId
from app.agent.workflows.implementation_registry import WORKFLOW_HANDLER_REGISTRY, build_workflow_handler
from app.agent.workflows.registry import WORKFLOW_REGISTRY
from app.schemas.draft import DraftReviewLLMResult
from app.schemas.content_strategy import EvidenceRef as StrategyEvidenceRef


NOW = datetime.now(UTC)
STRATEGY_REF = ArtifactRef(type=ArtifactType.CONTENT_STRATEGY, id=501)
EVIDENCE_REF = EvidenceRef(type=EvidenceType.NOTE, id=31)
BACKEND_ROOT = Path(__file__).resolve().parents[1]


def _error(code="TEST_ERROR", retryable=False):
    return ToolError(code=code, category="TEST", retryable=retryable, safe_message="失败")


def _strategy(opportunity_refs=(601,)):
    return {
        "account_ref": 7,
        "research_artifact_ref": 11,
        "strategy_goal": "建立专业认知",
        "target_audience": "新手用户",
        "content_directions": [
            {"direction": "教程", "rationale": "需求明确", "evidence_refs": [{"kind": "research_report", "id": 11}]}
        ],
        "rationale": "Research 支持",
        "evidence_refs": [{"kind": "research_report", "id": 11}],
        "applicable_constraints": ["不承诺结果"],
        "generated_opportunity_refs": list(opportunity_refs),
    }


def _opportunity(strategy_id=501):
    return {
        "account_ref": 7,
        "strategy_artifact_ref": strategy_id,
        "research_artifact_ref": 11,
        "source_opportunity_ref": 21,
        "opportunity": {
            "source_opportunity_id": 21,
            "topic": "Agent 项目避坑",
            "angle": "真实复盘",
            "target_audience": "新手用户",
            "content_goal": "解释工程误区",
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


def _review():
    return DraftReviewLLMResult(
        overall_status="PASS",
        strategy_alignment="一致",
        evidence_grounding="充分",
        style_consistency="一致",
        revision_required=False,
        summary="通过",
    )


class FakeRouter:
    def __init__(
        self,
        *,
        opportunity_refs=(601,),
        strategy_account=7,
        opportunity_strategy=501,
        opportunity_failure=False,
        retrieval_failure=False,
        generation_failure=False,
        persistence_failure=False,
        review_failure=False,
        opportunity_payload=None,
    ):
        self.calls = {name: 0 for name in ToolName}
        self.opportunity_refs = opportunity_refs
        self.strategy_account = strategy_account
        self.opportunity_strategy = opportunity_strategy
        self.opportunity_failure = opportunity_failure
        self.retrieval_failure = retrieval_failure
        self.generation_failure = generation_failure
        self.persistence_failure = persistence_failure
        self.review_failure = review_failure
        self.opportunity_payload = opportunity_payload
        self.persistence_input = None
        self.generation_input = None
        self.retrieval_input = None
        self.review_input = None

    def build(self, name, context):
        router = self

        class Handler:
            def execute(self, data):
                router.calls[name] += 1
                if name == ToolName.QUERY_GROWTH_CONTEXT:
                    return ToolResult(success=True, data=GrowthContextResult(account={"id": 7}, context_version="v1", observed_at=NOW))
                if name == ToolName.QUERY_ARTIFACT:
                    if data.artifact_ref.type == ArtifactType.CONTENT_STRATEGY:
                        payload = _strategy(router.opportunity_refs)
                        payload["account_ref"] = router.strategy_account
                        return ToolResult(success=True, data=ArtifactResult(
                            artifact_ref=data.artifact_ref, artifact_type=ArtifactType.CONTENT_STRATEGY,
                            version="v1", content=payload,
                        ))
                    if router.opportunity_failure:
                        return ToolResult(success=False, error=_error("CONTEXT_ERROR"))
                    return ToolResult(success=True, data=ArtifactResult(
                        artifact_ref=data.artifact_ref, artifact_type=ArtifactType.CONTENT_OPPORTUNITY,
                        version="v1", content=router.opportunity_payload or _opportunity(router.opportunity_strategy),
                    ))
                if name == ToolName.RETRIEVE_RESEARCH_EVIDENCE:
                    router.retrieval_input = data
                    if router.retrieval_failure:
                        return ToolResult(success=False, error=_error("CONTEXT_ERROR"))
                    return ToolResult(success=True, data=EvidenceBundle(
                        items=[EvidenceItem(evidence_ref=EVIDENCE_REF, evidence_type=EvidenceType.NOTE, content="真实正文", provenance="TEST")],
                        purpose=data.purpose,
                    ))
                if name == ToolName.GENERATE_DRAFT:
                    router.generation_input = data
                    if router.generation_failure:
                        return ToolResult(success=False, error=_error("SEMANTIC_ERROR"))
                    return ToolResult(success=True, data=SemanticDraftResult(
                        title="标题", body="正文", tags=["Agent"], cta="收藏",
                        strategy_ref=data.strategy_ref,
                        opportunity_ref=data.opportunity.source_opportunity_id,
                        content_goal=data.opportunity.content_goal,
                    ))
                if name == ToolName.CREATE_DRAFT_VERSION:
                    router.persistence_input = data.root
                    if router.persistence_failure:
                        return ToolResult(success=False, error=_error("PERSISTENCE_ERROR"))
                    return ToolResult(success=True, data=CreateDraftVersionResult(
                        draft_ref=801, draft_version_ref=901, version=1,
                        parent_draft_ref=None, created_from="GENERATED",
                    ))
                if name == ToolName.REVIEW_DRAFT:
                    router.review_input = data
                    if router.review_failure:
                        return ToolResult(success=False, error=_error("REVIEW_ERROR"))
                    return ToolResult(success=True, data=_review())
                raise AssertionError(name)

        return Handler()


def _input(strategy=STRATEGY_REF, opportunity=None):
    return ContentCreationWorkflowInput(
        account_ref=7,
        strategy_artifact_ref=strategy,
        opportunity_ref=opportunity,
        constraints=["不夸大"],
        style_constraints=["简洁"],
    )


def _context(authorized=True):
    refs = frozenset({EVIDENCE_REF}) if authorized else frozenset()
    return ToolExecutionContext(db=object(), evidence_access_scope=EvidenceAccessScope(authorized_refs=refs))


def _run(monkeypatch, router, data=None, context=None):
    monkeypatch.setattr("app.agent.workflows.content_creation.build_tool_handler", router.build)
    return ContentCreationWorkflow().execute(data or _input(), context or _context())


def test_standard_success_chain_and_v1_identity(monkeypatch):
    router = FakeRouter()
    result = _run(monkeypatch, router)
    assert result.status == WorkflowStatus.SUCCESS
    assert (result.draft_ref, result.draft_version_ref, result.version) == (801, 901, 1)
    assert result.review_result.overall_status == "PASS"
    assert router.persistence_input.action == "CREATE_V1"
    assert router.persistence_input.account_ref == 7
    assert router.persistence_input.strategy_artifact_ref == 501
    assert router.persistence_input.opportunity_ref == 601
    assert router.persistence_input.content_goal == "解释工程误区"
    assert router.generation_input.evidence_bundle.items[0].content == "真实正文"
    assert router.retrieval_input.evidence_refs == [EVIDENCE_REF]
    assert [ref.model_dump(mode="json") for ref in result.state.grounding_refs] == [
        {"kind": "research_report", "id": 11},
        {"kind": "content_opportunity", "id": 21},
    ]
    assert router.review_input.grounding_refs == result.state.grounding_refs
    assert router.generation_input.opportunity.source_opportunity_id == 21
    assert result.opportunity_ref == 601
    assert router.calls[ToolName.REVISE_DRAFT] == 0


def test_missing_strategy_waits_without_draft(monkeypatch):
    router = FakeRouter()
    result = _run(monkeypatch, router, _input(strategy=None))
    assert result.status == WorkflowStatus.WAITING_USER and result.error is None
    assert result.pending_interaction.required_fields == ["strategy_artifact_ref"]
    assert result.draft_ref is None and router.calls[ToolName.GENERATE_DRAFT] == 0


def test_unique_opportunity_auto_selects_and_multiple_waits(monkeypatch):
    unique_router = FakeRouter(opportunity_refs=(601,))
    unique = _run(monkeypatch, unique_router)
    assert unique.status == WorkflowStatus.SUCCESS and unique.opportunity_ref == 601

    multiple_router = FakeRouter(opportunity_refs=(601, 602))
    multiple = _run(monkeypatch, multiple_router)
    assert multiple.status == WorkflowStatus.WAITING_USER
    assert multiple.pending_interaction.required_fields == ["opportunity_ref"]
    assert multiple.draft_ref is None and multiple_router.calls[ToolName.GENERATE_DRAFT] == 0


def test_invalid_strategy_and_opportunity_lineage_fail(monkeypatch):
    account_mismatch = _run(monkeypatch, FakeRouter(strategy_account=8))
    assert account_mismatch.status == WorkflowStatus.FAILED

    wrong_strategy = _run(monkeypatch, FakeRouter(opportunity_strategy=502), _input(opportunity=601))
    assert wrong_strategy.status == WorkflowStatus.FAILED

    research_or_missing = _run(monkeypatch, FakeRouter(opportunity_failure=True), _input(opportunity=21))
    assert research_or_missing.status == WorkflowStatus.FAILED


def test_cross_research_evidence_and_retrieval_fail_before_generation(monkeypatch):
    cross_research = _opportunity()
    cross_research["opportunity"]["evidence_refs"].append({"kind": "competitor_note", "id": 32})
    unauthorized_router = FakeRouter(opportunity_payload=cross_research)
    unauthorized = _run(monkeypatch, unauthorized_router)
    assert unauthorized.status == WorkflowStatus.FAILED
    assert unauthorized.error.code == "VALIDATION_ERROR"
    assert unauthorized_router.calls[ToolName.RETRIEVE_RESEARCH_EVIDENCE] == 0
    assert unauthorized_router.calls[ToolName.GENERATE_DRAFT] == 0

    retrieval_router = FakeRouter(retrieval_failure=True)
    retrieval = _run(monkeypatch, retrieval_router)
    assert retrieval.status == WorkflowStatus.FAILED
    assert retrieval_router.calls[ToolName.GENERATE_DRAFT] == 0


def test_unknown_domain_ref_fails_instead_of_being_silently_skipped():
    opportunity = ContentOpportunityArtifactView.model_validate(_opportunity())
    opportunity.opportunity.evidence_refs.append(
        StrategyEvidenceRef.model_construct(kind="future_unknown", id=99)
    )

    try:
        partition_opportunity_evidence(opportunity)
    except ValueError as exc:
        assert "未定义分类" in str(exc)
    else:
        raise AssertionError("unknown ref must fail fast")


def test_complete_business_context_without_retrievable_research_evidence_fails():
    payload = _opportunity()
    payload["opportunity"]["evidence_refs"] = payload["opportunity"]["evidence_refs"][:2]
    payload["retrievable_evidence_refs"] = []
    opportunity = ContentOpportunityArtifactView.model_validate(payload)

    try:
        partition_opportunity_evidence(opportunity)
    except ValueError as exc:
        assert "没有可检索的事实 Evidence" in str(exc)
    else:
        raise AssertionError("GenerateDraftInput requires a non-empty EvidenceBundle")


def test_generation_and_persistence_fail_without_fake_refs(monkeypatch):
    generation_router = FakeRouter(generation_failure=True)
    generation = _run(monkeypatch, generation_router)
    assert generation.status == WorkflowStatus.FAILED and generation.draft_ref is None
    assert generation_router.calls[ToolName.CREATE_DRAFT_VERSION] == 0

    persistence_router = FakeRouter(persistence_failure=True)
    persistence = _run(monkeypatch, persistence_router)
    assert persistence.status == WorkflowStatus.FAILED
    assert persistence.draft_ref is None and persistence.draft_version_ref is None


def test_review_failure_is_partial_and_preserves_draft(monkeypatch):
    router = FakeRouter(review_failure=True)
    result = _run(monkeypatch, router)
    assert result.status == WorkflowStatus.PARTIAL_SUCCESS
    assert (result.draft_ref, result.draft_version_ref, result.version) == (801, 901, 1)
    assert result.review_result is None
    assert "DRAFT_REVIEW_FAILED" in result.warnings
    assert router.calls[ToolName.REVISE_DRAFT] == 0


def test_resume_selection_skips_context_strategy_and_completed_draft(monkeypatch):
    router = FakeRouter(opportunity_refs=(601, 602))
    monkeypatch.setattr("app.agent.workflows.content_creation.build_tool_handler", router.build)
    workflow = ContentCreationWorkflow()
    waiting = workflow.execute(_input(), _context())
    resumed = workflow.resume(waiting.state, _input(opportunity=602), _context())
    assert resumed.status == WorkflowStatus.SUCCESS
    assert router.calls[ToolName.QUERY_GROWTH_CONTEXT] == 1
    assert router.calls[ToolName.QUERY_ARTIFACT] == 2

    again = workflow.resume(resumed.state, _input(opportunity=602), _context())
    assert again.status == WorkflowStatus.SUCCESS
    assert router.calls[ToolName.GENERATE_DRAFT] == 1
    assert router.calls[ToolName.CREATE_DRAFT_VERSION] == 1


def test_existing_v1_resumes_review_only(monkeypatch):
    router = FakeRouter(review_failure=True)
    monkeypatch.setattr("app.agent.workflows.content_creation.build_tool_handler", router.build)
    workflow = ContentCreationWorkflow()
    partial = workflow.execute(_input(), _context())
    router.review_failure = False
    resumed = workflow.resume(partial.state, _input(), _context())
    assert resumed.status == WorkflowStatus.SUCCESS
    assert router.calls[ToolName.GENERATE_DRAFT] == 1
    assert router.calls[ToolName.CREATE_DRAFT_VERSION] == 1
    assert router.calls[ToolName.REVIEW_DRAFT] == 2


def test_registry_retry_and_architecture_boundaries(monkeypatch):
    assert len(WORKFLOW_REGISTRY) == 5
    assert set(WORKFLOW_HANDLER_REGISTRY) == {
        WorkflowId.RESEARCH_V1,
        WorkflowId.CONTENT_STRATEGY_V1,
        WorkflowId.CONTENT_CREATION_V1,
        WorkflowId.CONTENT_REFINEMENT_V1,
        WorkflowId.POST_PUBLISH_REVIEW_V1,
    }
    assert isinstance(build_workflow_handler(WorkflowId.CONTENT_CREATION_V1), ContentCreationWorkflow)

    router = FakeRouter()
    base_build = router.build

    def build(name, context):
        handler = base_build(name, context)
        if name != ToolName.QUERY_GROWTH_CONTEXT:
            return handler
        original = handler.execute

        def execute(data):
            if router.calls[name] == 0:
                router.calls[name] += 1
                return ToolResult(success=False, error=_error("TEMPORARY", retryable=True))
            return original(data)

        handler.execute = execute
        return handler

    monkeypatch.setattr("app.agent.workflows.content_creation.build_tool_handler", build)
    assert ContentCreationWorkflow().execute(_input(), _context()).status == WorkflowStatus.SUCCESS
    assert router.calls[ToolName.QUERY_GROWTH_CONTEXT] == 2

    source = (BACKEND_ROOT / "app" / "agent" / "workflows" / "content_creation.py").read_text(encoding="utf-8")
    forbidden = (
        "app.repositories", "sqlalchemy", "app.llm", "fastapi", "HTTPException",
        "ResearchWorkflow(", "ContentStrategyWorkflow(", "collect_xhs_", "analyze_research",
        "generate_content_strategy", "ReviseDraftTool(", "revise_draft",
    )
    assert not [token for token in forbidden if token in source]
    assert "build_tool_handler" in source
