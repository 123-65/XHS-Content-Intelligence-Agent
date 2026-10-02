from datetime import datetime, timezone
from pathlib import Path

import pytest

from app.agent.schemas.execution import ArtifactRef, ArtifactType, WorkflowStatus
from app.agent.tools.artifact_contracts import CreateContentStrategyArtifactResult
from app.agent.tools.definitions import ToolError, ToolName, ToolResult
from app.agent.tools.execution_context import ToolExecutionContext
from app.agent.tools.query_contracts import ArtifactResult, GrowthContextResult
from app.agent.workflows.content_strategy import ContentStrategyWorkflow, ContentStrategyWorkflowInput
from app.agent.workflows.definitions import WorkflowId
from app.agent.workflows.implementation_registry import WORKFLOW_HANDLER_REGISTRY, build_workflow_handler
from app.agent.workflows.registry import WORKFLOW_REGISTRY
from app.schemas.content_strategy import GeneratedContentStrategy


NOW = datetime.now(timezone.utc)
RESEARCH_REF = ArtifactRef(type=ArtifactType.RESEARCH, id=31)
BACKEND_ROOT = Path(__file__).resolve().parents[1]


def _generated():
    ref = {"kind": "research_report", "id": 31}
    return GeneratedContentStrategy.model_validate(
        {
            "strategy_goal": "建立专业认知",
            "target_audience": "新手用户",
            "content_directions": [{"direction": "教程", "rationale": "需求明确", "evidence_refs": [ref]}],
            "rationale": "Research 支持该方向",
            "evidence_refs": [ref],
            "applicable_constraints": [],
            "opportunities": [
                {
                    "source_opportunity_id": 41,
                    "content_goal": "解释核心方法",
                    "why_now": "需求正在增长",
                    "suggested_hook": "三个常见误区",
                    "evidence_refs": [ref],
                    "constraints": [],
                }
            ],
        }
    )


class FakeRouter:
    def __init__(self, *, artifact_type=ArtifactType.RESEARCH, artifact_account=7, missing=False, semantic_failure=False, persistence_failure=False):
        self.calls = {name: 0 for name in ToolName}
        self.artifact_type = artifact_type
        self.artifact_account = artifact_account
        self.missing = missing
        self.semantic_failure = semantic_failure
        self.persistence_failure = persistence_failure
        self.persistence_input = None

    def build(self, name, context):
        router = self

        class Handler:
            def execute(self, data):
                router.calls[name] += 1
                if name == ToolName.QUERY_GROWTH_CONTEXT:
                    return ToolResult(
                        success=True,
                        data=GrowthContextResult(
                            strategy_memory=[{"ref": 1}], context_version="v1", observed_at=NOW
                        ),
                    )
                if name == ToolName.QUERY_ARTIFACT:
                    if router.missing:
                        return ToolResult(success=False, error=_error("CONTEXT_ERROR"))
                    return ToolResult(
                        success=True,
                        data=ArtifactResult(
                            artifact_ref=data.artifact_ref,
                            artifact_type=router.artifact_type,
                            version="v1",
                            content={"account_id": router.artifact_account, "summary": "研究结论"},
                        ),
                    )
                if name == ToolName.GENERATE_CONTENT_STRATEGY:
                    if router.semantic_failure:
                        return ToolResult(success=False, error=_error("SEMANTIC_ERROR"))
                    return ToolResult(success=True, data=_generated(), metadata={"provider": "test", "model": "test-v1"})
                if name == ToolName.CREATE_CONTENT_STRATEGY_ARTIFACT:
                    router.persistence_input = data
                    if router.persistence_failure:
                        return ToolResult(success=False, error=_error("PERSISTENCE_ERROR"))
                    return ToolResult(
                        success=True,
                        data=CreateContentStrategyArtifactResult(
                            artifact_ref=ArtifactRef(type=ArtifactType.CONTENT_STRATEGY, id=51),
                            research_artifact_ref=31,
                            generated_opportunity_refs=[61],
                        ),
                    )
                raise AssertionError(name)

        return Handler()


def _error(code, retryable=False):
    return ToolError(code=code, category="TEST", retryable=retryable, safe_message="失败")


def _input(ref=RESEARCH_REF):
    return ContentStrategyWorkflowInput(
        account_ref=7, research_artifact_ref=ref, strategy_goal="建立专业认知", constraints=["不预测指标"]
    )


def _context():
    return ToolExecutionContext(db=object())


def test_success_chain_returns_artifact_opportunities_and_lineage(monkeypatch):
    router = FakeRouter()
    monkeypatch.setattr("app.agent.workflows.content_strategy.build_tool_handler", router.build)

    result = ContentStrategyWorkflow().execute(_input(), _context())

    assert result.status == WorkflowStatus.SUCCESS
    assert result.strategy_artifact_ref == ArtifactRef(type=ArtifactType.CONTENT_STRATEGY, id=51)
    assert result.generated_opportunity_refs == [61]
    assert router.persistence_input.research_artifact_ref == RESEARCH_REF.id
    assert router.persistence_input.strategy_result.research_report_id == RESEARCH_REF.id
    assert router.persistence_input.strategy_result.account_id == 7


def test_missing_research_waits_then_resume_skips_growth_context(monkeypatch):
    router = FakeRouter()
    monkeypatch.setattr("app.agent.workflows.content_strategy.build_tool_handler", router.build)
    workflow = ContentStrategyWorkflow()

    first = workflow.execute(_input(None), _context())
    assert first.status == WorkflowStatus.WAITING_USER
    assert first.error is None and first.strategy_artifact_ref is None
    assert first.pending_interaction.required_fields == ["research_artifact_ref"]
    assert router.calls[ToolName.GENERATE_CONTENT_STRATEGY] == 0
    assert router.calls[ToolName.CREATE_CONTENT_STRATEGY_ARTIFACT] == 0

    resumed = workflow.resume(first.state, _input(), _context())
    assert resumed.status == WorkflowStatus.SUCCESS
    assert router.calls[ToolName.QUERY_GROWTH_CONTEXT] == 1
    assert router.calls[ToolName.GENERATE_CONTENT_STRATEGY] == 1


@pytest.mark.parametrize(
    "router,ref",
    [
        (FakeRouter(artifact_type=ArtifactType.CONTENT_STRATEGY), RESEARCH_REF),
        (FakeRouter(artifact_account=8), RESEARCH_REF),
        (FakeRouter(missing=True), RESEARCH_REF),
        (FakeRouter(), ArtifactRef(type=ArtifactType.CONTENT_STRATEGY, id=31)),
    ],
)
def test_invalid_explicit_research_fails_without_generation(monkeypatch, router, ref):
    monkeypatch.setattr("app.agent.workflows.content_strategy.build_tool_handler", router.build)
    result = ContentStrategyWorkflow().execute(_input(ref), _context())
    assert result.status == WorkflowStatus.FAILED
    assert router.calls[ToolName.GENERATE_CONTENT_STRATEGY] == 0


def test_semantic_and_persistence_failures_do_not_fabricate_artifact(monkeypatch):
    for router in (FakeRouter(semantic_failure=True), FakeRouter(persistence_failure=True)):
        monkeypatch.setattr("app.agent.workflows.content_strategy.build_tool_handler", router.build)
        result = ContentStrategyWorkflow().execute(_input(), _context())
        assert result.status == WorkflowStatus.FAILED
        assert result.strategy_artifact_ref is None
        if router.semantic_failure:
            assert router.calls[ToolName.CREATE_CONTENT_STRATEGY_ARTIFACT] == 0


def test_resume_with_artifact_is_idempotent_and_research_identity_is_fixed(monkeypatch):
    router = FakeRouter()
    monkeypatch.setattr("app.agent.workflows.content_strategy.build_tool_handler", router.build)
    workflow = ContentStrategyWorkflow()
    completed = workflow.execute(_input(), _context())

    again = workflow.resume(completed.state, _input(), _context())
    assert again.status == WorkflowStatus.SUCCESS
    assert router.calls[ToolName.GENERATE_CONTENT_STRATEGY] == 1
    assert router.calls[ToolName.CREATE_CONTENT_STRATEGY_ARTIFACT] == 1

    changed = workflow.resume(
        completed.state,
        _input(ArtifactRef(type=ArtifactType.RESEARCH, id=32)),
        _context(),
    )
    assert changed.status == WorkflowStatus.FAILED
    assert router.calls[ToolName.CREATE_CONTENT_STRATEGY_ARTIFACT] == 1


def test_query_retry_is_one_extra_attempt_and_semantic_is_not_retried(monkeypatch):
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

    monkeypatch.setattr("app.agent.workflows.content_strategy.build_tool_handler", build)
    result = ContentStrategyWorkflow().execute(_input(), _context())
    assert result.status == WorkflowStatus.SUCCESS
    assert router.calls[ToolName.QUERY_GROWTH_CONTEXT] == 2


def test_registry_and_architecture_boundaries():
    assert len(WORKFLOW_REGISTRY) == 5
    assert set(WORKFLOW_HANDLER_REGISTRY) == {
        WorkflowId.RESEARCH_V1,
        WorkflowId.CONTENT_STRATEGY_V1,
        WorkflowId.CONTENT_CREATION_V1,
        WorkflowId.CONTENT_REFINEMENT_V1,
        WorkflowId.POST_PUBLISH_REVIEW_V1,
    }
    assert isinstance(build_workflow_handler(WorkflowId.CONTENT_STRATEGY_V1), ContentStrategyWorkflow)

    source = (BACKEND_ROOT / "app" / "agent" / "workflows" / "content_strategy.py").read_text(encoding="utf-8")
    forbidden = (
        "app.repositories",
        "sqlalchemy",
        "app.llm",
        "fastapi",
        "HTTPException",
        "ResearchWorkflow(",
        "QueryArtifactTool(",
        "GenerateContentStrategyTool(",
        "collect_xhs_",
        "retrieve_research_evidence",
    )
    assert not [token for token in forbidden if token in source]
    assert "build_tool_handler" in source
