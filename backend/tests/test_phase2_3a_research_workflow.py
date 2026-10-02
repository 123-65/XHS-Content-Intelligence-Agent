from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

from app.agent.schemas.evidence import EvidenceRef, EvidenceType
from app.agent.schemas.execution import ArtifactRef, ArtifactType, WorkflowStatus
from app.agent.tools.access_scopes import EvidenceAccessScope
from app.agent.tools.definitions import ToolError, ToolName, ToolResult
from app.agent.tools.execution_context import ToolExecutionContext
from app.agent.tools.query_contracts import EvidenceBundle, EvidenceItem, GrowthContextResult
from app.agent.tools.xhs_contracts import (
    AccountCollectionPurpose,
    CollectXhsAccountsResult,
    CollectXhsNotesResult,
    CollectedAccountResult,
    CollectedNoteResult,
    CollectionAuthorizationSource,
    NoteCollectionPurpose,
)
from app.agent.workflows.definitions import WorkflowId
from app.agent.workflows.implementation_registry import WORKFLOW_HANDLER_REGISTRY, build_workflow_handler
from app.agent.workflows.registry import WORKFLOW_REGISTRY
from app.agent.workflows.research import ResearchWorkflow, ResearchWorkflowInput, ResearchWorkflowState


NOW = datetime.now(timezone.utc)
BACKEND_ROOT = Path(__file__).resolve().parents[1]


def _semantic():
    return {
        "persona": {"positioning": "教程", "expertise": [], "target_audience": ["新手"], "value_proposition": "实用", "tone_and_style": [], "confidence": .8, "evidence": []},
        "content_pillars": [], "audience_demands": [], "high_performing_patterns": [],
        "content_style": {"structure": [], "tone": [], "hooks": [], "visual_patterns": [], "evidence_note_ids": []},
        "follow_recommendation": {"why_follow": "观察", "what_to_learn": [], "what_not_to_copy": [], "confidence": .5, "evidence": []},
        "content_opportunities": [], "conversion_signals": [], "risk_points": [], "data_gaps": [],
    }


def _item(ref, account=7):
    if ref.type == EvidenceType.NOTE:
        facts = {"account_id": account, "competitor_account_id": None, "author_name": None, "title": f"标题{ref.id}", "body": "正文", "tags": [], "like_count": 1, "collect_count": 1, "comment_count": 1, "source_type": "TEST", "provider_name": "test", "ocr_used": False, "ocr_texts": []}
    elif ref.type == EvidenceType.COMMENT:
        facts = {"account_id": account, "competitor_note_id": 1, "like_count": 1, "source_type": "TEST", "provider_name": "test"}
    else:
        facts = {"account_id": account, "nickname": "账号", "bio": None, "follower_count": None, "note_count": None, "source_type": "TEST", "provider_name": "test"}
    return EvidenceItem(evidence_ref=ref, evidence_type=ref.type, content="正文", structured_facts=facts, provenance="TEST")


class FakeToolRouter:
    def __init__(self, *, grounding_failure=False, artifact_failure=False, partial=False, profile_has_notes=True):
        self.calls = {name: 0 for name in ToolName}
        self.grounding_failure = grounding_failure
        self.artifact_failure = artifact_failure
        self.partial = partial
        self.profile_has_notes = profile_has_notes

    def build(self, name, context):
        router = self
        class Handler:
            def execute(self, data):
                router.calls[name] += 1
                if name == ToolName.QUERY_GROWTH_CONTEXT:
                    return ToolResult(success=True, data=GrowthContextResult(context_version="v1", observed_at=NOW))
                if name == ToolName.QUERY_ARTIFACT:
                    return ToolResult(success=True, data=SimpleNamespace(model_dump=lambda **_: {"artifact_ref": str(data.artifact_ref)}))
                if name == ToolName.COLLECT_XHS_ACCOUNTS:
                    account_ref = EvidenceRef(type=EvidenceType.ACCOUNT, id=80)
                    note_ref = EvidenceRef(type=EvidenceType.NOTE, id=81)
                    item = CollectedAccountResult(
                        source_url=data.profile_urls[0],
                        account_ref=80,
                        external_account_ref="external-80",
                        evidence_refs=[account_ref, *([note_ref] if router.profile_has_notes else [])],
                        attached_note_refs=[81] if router.profile_has_notes else [],
                        collected_at=NOW,
                        authorized_by=CollectionAuthorizationSource.USER_PROVIDED,
                        collection_purpose=AccountCollectionPurpose.RESEARCH_INPUT,
                    )
                    return ToolResult(success=True, data=CollectXhsAccountsResult(requested_count=len(data.profile_urls), collected_count=1, failed_count=0, items=[item], failed_items=[], warnings=[]), warnings=[])
                if name == ToolName.COLLECT_XHS_NOTES:
                    ref = EvidenceRef(type=EvidenceType.NOTE, id=90)
                    item = CollectedNoteResult(source_url=data.note_urls[0], note_ref=90, evidence_refs=[ref], collected_at=NOW, authorized_by=CollectionAuthorizationSource.USER_PROVIDED, collection_purpose=NoteCollectionPurpose.RESEARCH_INPUT, comments_collected=0)
                    failed = [SimpleNamespace()] if router.partial else []
                    value = CollectXhsNotesResult(requested_count=1 + len(failed), collected_count=1, failed_count=len(failed), items=[item], failed_items=[], warnings=["PARTIAL_XHS_COLLECTION"] if router.partial else [])
                    return ToolResult(success=True, data=value, warnings=value.warnings)
                if name == ToolName.RETRIEVE_RESEARCH_EVIDENCE:
                    return ToolResult(success=True, data=EvidenceBundle(items=[_item(ref) for ref in data.evidence_refs], purpose=data.purpose))
                if name == ToolName.ANALYZE_RESEARCH:
                    if router.grounding_failure:
                        return ToolResult(success=False, error=ToolError(code="GROUNDING_FAILED", category="GROUNDING", retryable=False, safe_message="失败"))
                    from app.analysis.competitor.schemas import CompetitorSemanticResult
                    return ToolResult(success=True, data=CompetitorSemanticResult.model_validate(_semantic()))
                if name == ToolName.CREATE_RESEARCH_ARTIFACT:
                    if router.artifact_failure:
                        return ToolResult(success=False, error=ToolError(code="PERSISTENCE_ERROR", category="PERSISTENCE", retryable=True, safe_message="失败"))
                    return ToolResult(success=True, data=SimpleNamespace(artifact_ref=ArtifactRef(type=ArtifactType.RESEARCH, id=501)))
                raise AssertionError(name)
        return Handler()


def _context(refs=()):
    return ToolExecutionContext(db=object(), evidence_access_scope=EvidenceAccessScope(authorized_refs=frozenset(refs)), collection_access_scope=SimpleNamespace())


def test_existing_sufficient_evidence_reaches_success(monkeypatch):
    refs = [*(EvidenceRef(type=EvidenceType.NOTE, id=i) for i in range(1, 4)), *(EvidenceRef(type=EvidenceType.COMMENT, id=i) for i in range(11, 14))]
    router = FakeToolRouter()
    monkeypatch.setattr("app.agent.workflows.research.build_tool_handler", router.build)
    result = ResearchWorkflow().execute(ResearchWorkflowInput(account_ref=7, research_goal="研究", evidence_refs=refs), _context(refs))
    assert result.status == WorkflowStatus.SUCCESS and result.research_artifact_ref.id == 501


def test_collection_grant_retrieval_and_partial_success(monkeypatch):
    router = FakeToolRouter(partial=True)
    monkeypatch.setattr("app.agent.workflows.research.build_tool_handler", router.build)
    result = ResearchWorkflow().execute(ResearchWorkflowInput(account_ref=7, research_goal="研究", note_urls=["https://www.xiaohongshu.com/explore/90"]), _context())
    assert result.status == WorkflowStatus.PARTIAL_SUCCESS
    assert "PARTIAL_XHS_COLLECTION" in result.warnings
    assert result.state.run_local_evidence_refs[0].id == 90


def test_profile_with_user_profile_recent_note_reaches_artifact_without_asking_for_note_url(monkeypatch):
    router = FakeToolRouter()
    monkeypatch.setattr("app.agent.workflows.research.build_tool_handler", router.build)
    result = ResearchWorkflow().execute(ResearchWorkflowInput(account_ref=7, research_goal="研究", profile_urls=["https://www.xiaohongshu.com/user/profile/1"]), _context())
    assert result.status == WorkflowStatus.PARTIAL_SUCCESS
    assert result.pending_interaction is None
    assert {ref.type for ref in result.state.run_local_evidence_refs} == {EvidenceType.ACCOUNT, EvidenceType.NOTE}
    assert any(ref.type == EvidenceType.NOTE and ref.id == 81 for ref in result.state.run_local_evidence_refs)
    assert result.research_artifact_ref.id == 501
    assert router.calls[ToolName.CREATE_RESEARCH_ARTIFACT] == 1


def test_profile_without_any_recent_note_still_requests_genuinely_missing_analysis_material(monkeypatch):
    router = FakeToolRouter(profile_has_notes=False)
    monkeypatch.setattr("app.agent.workflows.research.build_tool_handler", router.build)
    result = ResearchWorkflow().execute(ResearchWorkflowInput(account_ref=7, research_goal="研究", profile_urls=["https://www.xiaohongshu.com/user/profile/1"]), _context())
    assert result.status == WorkflowStatus.WAITING_USER
    assert result.pending_interaction is not None
    assert result.research_artifact_ref is None


def test_resume_skips_context_and_creates_artifact_once(monkeypatch):
    router = FakeToolRouter()
    monkeypatch.setattr("app.agent.workflows.research.build_tool_handler", router.build)
    workflow = ResearchWorkflow()
    first = workflow.execute(ResearchWorkflowInput(account_ref=7, research_goal="研究"), _context())
    resumed = workflow.resume(first.state, ResearchWorkflowInput(account_ref=7, research_goal="研究", note_urls=["https://www.xiaohongshu.com/explore/90"]), _context())
    again = workflow.resume(resumed.state, ResearchWorkflowInput(account_ref=7, research_goal="研究"), _context())
    assert router.calls[ToolName.QUERY_GROWTH_CONTEXT] == 1
    assert router.calls[ToolName.COLLECT_XHS_NOTES] == 1
    assert router.calls[ToolName.CREATE_RESEARCH_ARTIFACT] == 1
    assert again.research_artifact_ref.id == 501


def test_unauthorized_history_grounding_and_artifact_failures(monkeypatch):
    ref = EvidenceRef(type=EvidenceType.NOTE, id=1)
    router = FakeToolRouter()
    monkeypatch.setattr("app.agent.workflows.research.build_tool_handler", router.build)
    unauthorized = ResearchWorkflow().execute(ResearchWorkflowInput(account_ref=7, research_goal="研究", evidence_refs=[ref]), _context())
    assert unauthorized.status == WorkflowStatus.FAILED
    for kwargs in ({"grounding_failure": True}, {"artifact_failure": True}):
        router = FakeToolRouter(**kwargs)
        monkeypatch.setattr("app.agent.workflows.research.build_tool_handler", router.build)
        failed = ResearchWorkflow().execute(ResearchWorkflowInput(account_ref=7, research_goal="研究", evidence_refs=[ref]), _context([ref]))
        assert failed.status == WorkflowStatus.FAILED and failed.research_artifact_ref is None
        if kwargs.get("grounding_failure"):
            assert router.calls[ToolName.CREATE_RESEARCH_ARTIFACT] == 0


def test_registry_and_architecture_boundaries():
    assert len(WORKFLOW_REGISTRY) == 5 and set(WORKFLOW_HANDLER_REGISTRY) == {
        WorkflowId.RESEARCH_V1,
        WorkflowId.CONTENT_STRATEGY_V1,
        WorkflowId.CONTENT_CREATION_V1,
        WorkflowId.CONTENT_REFINEMENT_V1,
        WorkflowId.POST_PUBLISH_REVIEW_V1,
    }
    assert isinstance(build_workflow_handler(WorkflowId.RESEARCH_V1), ResearchWorkflow)
    source = (BACKEND_ROOT / "app" / "agent" / "workflows" / "research.py").read_text(encoding="utf-8")
    forbidden = ("app.repositories", "sqlalchemy", "Provider", "app.llm", "fastapi", "HTTPException", "QueryGrowthContextTool(", "CollectXhsNotesTool(")
    assert not [token for token in forbidden if token in source]
    assert "build_tool_handler" in source and "RunLocalEvidenceGrant.from_successful_collection_result" in source
