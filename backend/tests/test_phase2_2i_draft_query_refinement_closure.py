from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest

from app.agent.schemas.evidence import EvidenceRef as RetrievalEvidenceRef, EvidenceType
from app.agent.schemas.execution import ArtifactRef, ArtifactType
from app.agent.tools.access_scopes import EvidenceAccessScope
from app.agent.tools.artifact_contracts import AppendDraftVersionInput, CreateDraftVersionInput
from app.agent.tools.definitions import ToolName
from app.agent.tools.query_contracts import (
    ContentOpportunityArtifactView,
    DraftArtifactView,
    QueryArtifactInput,
    RetrieveResearchEvidenceInput,
)
from app.agent.tools.query_tools import EvidenceRecord, QueryArtifactTool, QueryToolDataFacade, RetrieveResearchEvidenceTool
from app.agent.tools.semantic_contracts import ReviseDraftInput, SemanticDraftResult, SemanticRevisedDraftResult
from app.agent.workflows.definitions import WorkflowId
from app.agent.workflows.implementation_registry import WORKFLOW_HANDLER_REGISTRY
from app.agent.workflows.registry import WORKFLOW_REGISTRY
from app.models.content_draft import ContentDraft
from app.models.content_draft_version import ContentDraftVersion
from app.repositories.content_strategy_repo import ContentStrategyRepository


NOW = datetime.now(UTC)


def _root(*, object_id=100, account_id=7, agent=True):
    return ContentDraft(
        id=object_id,
        experiment_id=None if agent else 9,
        account_id=account_id,
        strategy_artifact_id=501 if agent else None,
        opportunity_id=601 if agent else None,
        content_goal="解释工程误区" if agent else None,
        title="Root 旧标题",
        body="Root 旧正文",
        tags=["旧"],
        cta="旧 CTA",
        version=3,
        status="REVISED" if agent else "GENERATED",
        generation_context={},
        created_at=NOW - timedelta(days=2),
        updated_at=NOW,
    )


def _version(object_id, version, *, draft_id=100, parent=None, title=None, created_from="USER_REVISION"):
    return ContentDraftVersion(
        id=object_id,
        draft_id=draft_id,
        version=version,
        parent_version_id=parent,
        created_from=created_from,
        regenerate_scope=created_from,
        draft_snapshot={
            "draft_id": draft_id,
            "version": version,
            "title": title or f"V{version} 标题",
            "body": f"V{version} 正文",
            "tags": [f"v{version}"],
            "cta": f"V{version} CTA",
        },
        created_at=NOW,
    )


def _opportunity():
    return SimpleNamespace(
        id=601,
        report_id=11,
        strategy_artifact_id=501,
        source_opportunity_id=21,
        opportunity_title="Agent 项目避坑",
        suggested_angle="真实复盘",
        target_audience="新手用户",
        content_goal="解释工程误区",
        why_now="用户正在追问",
        evidence_refs=[{"kind": "competitor_note", "id": 31}],
        suggested_hook="三个常见误区",
        constraints=["明确样本边界"],
        created_at=NOW,
    )


class FakeDraftRepository:
    def __init__(self, roots, versions):
        self.roots = {item.id: item for item in roots}
        self.versions = versions

    def get_draft(self, draft_id):
        return self.roots.get(draft_id)

    def get_latest_version(self, draft_id):
        matches = [item for item in self.versions if item.draft_id == draft_id]
        return max(matches, key=lambda item: (item.version, item.id)) if matches else None

    def version_content(self, version):
        from app.schemas.draft import DraftContent

        return DraftContent.model_validate({key: version.draft_snapshot.get(key) for key in ("title", "body", "tags", "cta")})


class FakeStrategyRepository:
    def __init__(self, *, strategy_id=501, goal="解释工程误区"):
        self.strategy = SimpleNamespace(id=strategy_id, account_id=7, research_artifact_id=11)
        self.opportunity = _opportunity()
        self.opportunity.strategy_artifact_id = strategy_id
        self.opportunity.content_goal = goal
        self.mapper = ContentStrategyRepository(None)

    def get_strategy_opportunity(self, opportunity_id):
        return self.opportunity if opportunity_id == self.opportunity.id else None

    def get_strategy_artifact(self, artifact_id):
        return self.strategy if artifact_id == self.strategy.id else None

    def to_opportunity_result(self, item):
        return self.mapper.to_opportunity_result(item)


def _facade(*, roots=None, versions=None, strategy_id=501, goal="解释工程误区"):
    facade = object.__new__(QueryToolDataFacade)
    facade.drafts = FakeDraftRepository(roots or [_root()], versions if versions is not None else [
        _version(201, 1, parent=None, created_from="GENERATED"),
        _version(202, 2, parent=201),
        _version(203, 3, parent=202),
    ])
    facade.strategy = FakeStrategyRepository(strategy_id=strategy_id, goal=goal)
    facade.research = SimpleNamespace(get_by_id=lambda report_id: SimpleNamespace(
        id=11,
        account_id=7,
        competitor_note_ids=[31],
        competitor_account_ids=[],
    ) if report_id == 11 else None)
    facade.research_evidence = SimpleNamespace(list_comments_for_notes=lambda account_id, note_ids: [])
    return facade


def _query(facade, artifact_type, object_id, account=7):
    return QueryArtifactTool(facade=facade).execute(QueryArtifactInput(
        account_ref=account,
        artifact_ref=ArtifactRef(type=artifact_type, id=object_id),
        expected_type=artifact_type,
    ))


def test_new_agent_draft_returns_root_identity_and_true_latest_snapshot():
    result = _query(_facade(), ArtifactType.DRAFT, 100)
    assert result.success is True and result.data.artifact_type == ArtifactType.DRAFT
    view = DraftArtifactView.model_validate(result.data.content)
    assert view.account_ref == 7
    assert (view.strategy_artifact_ref, view.opportunity_ref, view.content_goal) == (501, 601, "解释工程误区")
    assert (view.latest_draft_version_ref, view.latest_version) == (203, 3)
    assert view.latest_content.title == "V3 标题" and view.latest_content.body == "V3 正文"
    assert view.latest_content.title != "Root 旧标题"
    assert (view.latest_parent_draft_ref, view.latest_created_from) == (202, "USER_REVISION")
    assert result.data.lineage_refs == [
        ArtifactRef(type=ArtifactType.CONTENT_STRATEGY, id=501),
        ArtifactRef(type=ArtifactType.CONTENT_OPPORTUNITY, id=601),
    ]


def test_new_agent_draft_with_null_experiment_uses_root_account_ownership():
    assert _query(_facade(), ArtifactType.DRAFT, 100).success is True
    forbidden = _query(_facade(), ArtifactType.DRAFT, 100, account=8)
    assert forbidden.error.code == "PERMISSION_ERROR"
    missing = _query(_facade(), ArtifactType.DRAFT, 999)
    assert missing.error.code == "CONTEXT_ERROR"


def test_legacy_draft_with_and_without_version_remains_readable_without_fake_ref():
    legacy = _root(object_id=110, agent=False)
    with_version = _query(_facade(roots=[legacy], versions=[_version(301, 1, draft_id=110, created_from=None)]), ArtifactType.DRAFT, 110)
    view = DraftArtifactView.model_validate(with_version.data.content)
    assert view.latest_draft_version_ref == 301 and view.latest_content.title == "V1 标题"
    assert view.strategy_artifact_ref is None and view.opportunity_ref is None

    without_version = _query(_facade(roots=[legacy], versions=[]), ArtifactType.DRAFT, 110)
    empty = DraftArtifactView.model_validate(without_version.data.content)
    assert empty.latest_draft_version_ref is None
    assert empty.latest_version is None and empty.latest_content is None


def test_refinement_contract_closure_for_revise_and_append():
    facade = _facade()
    draft_result = _query(facade, ArtifactType.DRAFT, 100)
    draft = DraftArtifactView.model_validate(draft_result.data.content)
    opportunity_result = _query(facade, ArtifactType.CONTENT_OPPORTUNITY, draft.opportunity_ref)
    opportunity = ContentOpportunityArtifactView.model_validate(opportunity_result.data.content)
    assert opportunity.strategy_artifact_ref == draft.strategy_artifact_ref
    assert opportunity.opportunity.content_goal == draft.content_goal

    retrieval_ref = RetrievalEvidenceRef(type=EvidenceType.NOTE, id=opportunity.opportunity.evidence_refs[0].id)
    evidence_facade = SimpleNamespace(get_evidence=lambda account, ref: EvidenceRecord(
        content="真实笔记正文", structured_facts={"account_id": 7}, provenance="TEST", source_ref=None, observed_at=NOW
    ))
    evidence_result = RetrieveResearchEvidenceTool(
        facade=evidence_facade,
        access_scope=EvidenceAccessScope(authorized_refs=frozenset({retrieval_ref})),
    ).execute(RetrieveResearchEvidenceInput(account_ref=7, evidence_refs=[retrieval_ref], purpose=draft.content_goal))
    assert evidence_result.success is True

    source = SemanticDraftResult(
        **draft.latest_content.model_dump(),
        strategy_ref=f"CONTENT_STRATEGY:{draft.strategy_artifact_ref}",
        opportunity_ref=draft.opportunity_ref,
        content_goal=draft.content_goal,
    )
    revise_input = ReviseDraftInput(
        source_draft=source,
        revision_source="USER_FEEDBACK",
        user_instruction="把开头改得更直接",
        preserved_constraints=opportunity.opportunity.constraints,
        evidence_bundle=evidence_result.data,
        context_refs=[draft_result.data.artifact_ref, opportunity_result.data.artifact_ref],
    )
    assert revise_input.source_draft.title == "V3 标题"
    assert revise_input.user_instruction == "把开头改得更直接"
    assert revise_input.evidence_bundle.items[0].content == "真实笔记正文"

    revised = SemanticRevisedDraftResult(
        title="V4 标题", body="V4 正文", tags=["v4"], cta="V4 CTA",
        applied_changes=["重写开头"], strategy_ref=source.strategy_ref,
        opportunity_ref=source.opportunity_ref, content_goal=source.content_goal,
    )
    append = CreateDraftVersionInput(root=AppendDraftVersionInput(
        action="APPEND",
        draft_ref=draft_result.data.artifact_ref.id,
        parent_draft_ref=draft.latest_draft_version_ref,
        created_from="USER_REVISION",
        content=revised,
        applied_changes=revised.applied_changes,
    ))
    assert append.root.draft_ref == 100
    assert append.root.parent_draft_ref == 203
    assert append.root.created_from == "USER_REVISION"
    assert append.root.content.title == "V4 标题"


@pytest.mark.parametrize(("strategy_id", "goal"), [(502, "解释工程误区"), (501, "另一个目标")])
def test_identity_mismatch_is_detectable_by_closure(strategy_id, goal):
    facade = _facade(strategy_id=strategy_id, goal=goal)
    draft = DraftArtifactView.model_validate(_query(facade, ArtifactType.DRAFT, 100).data.content)
    opportunity = ContentOpportunityArtifactView.model_validate(_query(facade, ArtifactType.CONTENT_OPPORTUNITY, 601).data.content)
    assert (
        opportunity.strategy_artifact_ref != draft.strategy_artifact_ref
        or opportunity.opportunity.content_goal != draft.content_goal
    )


def test_refinement_allowlist_uses_existing_retrieval_tool_without_handler_registration():
    allowed = set(WORKFLOW_REGISTRY[WorkflowId.CONTENT_REFINEMENT_V1].allowed_tools)
    assert ToolName.RETRIEVE_RESEARCH_EVIDENCE in allowed
    assert len(WORKFLOW_HANDLER_REGISTRY) == 5
    assert WorkflowId.CONTENT_REFINEMENT_V1 in WORKFLOW_HANDLER_REGISTRY
