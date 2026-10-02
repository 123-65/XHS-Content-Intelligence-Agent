from datetime import UTC, datetime

from app.agent.schemas.evidence import EvidenceRef as RetrievalEvidenceRef, EvidenceType
from app.agent.schemas.execution import ArtifactRef, ArtifactType
from app.agent.tools.definitions import ToolEffect, ToolName
from app.agent.tools.query_contracts import (
    ContentOpportunityArtifactView,
    ContentStrategyArtifactView,
    EvidenceBundle,
    EvidenceItem,
    GrowthContextResult,
    QueryArtifactInput,
)
from app.agent.tools.query_tools import QueryArtifactTool, QueryToolDataFacade
from app.agent.tools.registry import TOOL_REGISTRY
from app.agent.tools.semantic_contracts import GenerateDraftInput
from app.models.content_opportunity import ContentOpportunity
from app.models.content_strategy_artifact import ContentStrategyArtifact
from app.repositories.content_strategy_repo import ContentStrategyRepository


NOW = datetime.now(UTC)


def _strategy(object_id=501, account_id=7):
    return ContentStrategyArtifact(
        id=object_id,
        account_id=account_id,
        research_artifact_id=11,
        strategy_goal="建立真实项目心智",
        target_audience="应届开发者",
        content_directions=[
            {
                "direction": "项目避坑",
                "rationale": "样本有明确需求",
                "evidence_refs": [{"kind": "research_report", "id": 11}],
            }
        ],
        rationale="基于 Research 样本。",
        evidence_refs=[{"kind": "research_report", "id": 11}],
        applicable_constraints=["不承诺结果"],
        provider="test",
        model="test-v1",
        created_at=NOW,
    )


def _opportunity(object_id, strategy_id, source_id, evidence_id=31):
    return ContentOpportunity(
        id=object_id,
        report_id=11,
        strategy_artifact_id=strategy_id,
        source_opportunity_id=source_id,
        opportunity_title="Agent 项目避坑",
        suggested_angle="真实复盘",
        target_audience="应届开发者",
        content_pillar="项目避坑",
        comment_demand_type="PROJECT",
        evidence_summary="评论追问项目落地",
        replicability_score=82,
        risk_level="MEDIUM",
        risk_points=["不承诺结果"],
        opportunity_score=76,
        content_goal="说清工程误区",
        why_now="样本出现相关追问",
        suggested_hook="别先堆十个 Agent",
        evidence_refs=[{"kind": "competitor_note", "id": evidence_id}],
        constraints=["明确样本边界"],
        created_at=NOW,
    )


class FakeStrategyRepository:
    def __init__(self):
        self.strategies = {501: _strategy(), 502: _strategy(502)}
        self.opportunities = {
            601: _opportunity(601, 501, 21),
            602: _opportunity(602, 501, 22, 32),
            701: _opportunity(701, 502, 23, 33),
            21: _opportunity(21, None, None),
        }
        self.mapper = ContentStrategyRepository(None)

    def get_strategy_artifact(self, artifact_id):
        return self.strategies.get(artifact_id)

    def list_strategy_opportunities(self, artifact_id):
        return sorted(
            (item for item in self.opportunities.values() if item.strategy_artifact_id == artifact_id),
            key=lambda item: item.id,
        )

    def get_strategy_opportunity(self, opportunity_id):
        item = self.opportunities.get(opportunity_id)
        return item if item is not None and item.strategy_artifact_id is not None else None

    def to_opportunity_result(self, item):
        return self.mapper.to_opportunity_result(item)


def _facade():
    facade = object.__new__(QueryToolDataFacade)
    facade.strategy = FakeStrategyRepository()
    facade.research = type("FakeResearchRepository", (), {
        "get_by_id": staticmethod(lambda artifact_id: type("Research", (), {
            "id": 11, "account_id": 7, "competitor_note_ids": [31], "competitor_account_ids": []
        })() if artifact_id == 11 else None)
    })()
    facade.research_evidence = type("FakeEvidenceRepository", (), {
        "list_comments_for_notes": staticmethod(lambda account_id, note_ids: [])
    })()
    return facade


def test_research_query_exposes_canonical_opportunity_ids_for_strategy_lineage():
    """Strategy generation must receive DB identities, never invent ordinal refs."""
    facade = _facade()
    facade.research = type(
        "FakeResearchRepository",
        (),
        {
            "get_by_id": staticmethod(
                lambda artifact_id: type(
                    "Research",
                    (),
                    {
                        "id": 11,
                        "account_id": 7,
                        "name": "研究",
                        "summary": "研究结论",
                        "content_insights": [],
                        "suggestions": [],
                        "status": "SUCCESS",
                        "created_at": NOW,
                    },
                )()
                if artifact_id == 11
                else None
            )
        },
    )()
    source = _opportunity(3923, None, None)
    facade.strategy.list_opportunities = lambda report_id, limit: [source] if report_id == 11 else []

    result = QueryArtifactTool(facade=facade).execute(
        QueryArtifactInput(
            account_ref=7,
            artifact_ref=ArtifactRef(type=ArtifactType.RESEARCH, id=11),
            expected_type=ArtifactType.RESEARCH,
        )
    )

    assert result.success is True
    assert result.data.content["content_opportunities"] == [
        {
            "source_opportunity_id": 3923,
            "topic": "Agent 项目避坑",
            "angle": "真实复盘",
            "target_audience": "应届开发者",
            "content_pillar": "项目避坑",
            "evidence_summary": "评论追问项目落地",
            "risk_points": ["不承诺结果"],
        }
    ]


def _query(artifact_type, object_id, account=7):
    return QueryArtifactTool(facade=_facade()).execute(
        QueryArtifactInput(
            account_ref=account,
            artifact_ref=ArtifactRef(type=artifact_type, id=object_id),
            expected_type=artifact_type,
        )
    )


def test_content_strategy_query_returns_complete_typed_view_and_only_owned_opportunities():
    result = _query(ArtifactType.CONTENT_STRATEGY, 501)
    assert result.success is True
    assert result.data.artifact_type == ArtifactType.CONTENT_STRATEGY
    view = ContentStrategyArtifactView.model_validate(result.data.content)
    assert view.account_ref == 7
    assert view.research_artifact_ref == 11
    assert view.strategy_goal == "建立真实项目心智"
    assert view.target_audience == "应届开发者"
    assert view.generated_opportunity_refs == [601, 602]
    assert 701 not in view.generated_opportunity_refs and 21 not in view.generated_opportunity_refs
    assert result.data.lineage_refs == [ArtifactRef(type=ArtifactType.RESEARCH, id=11)]


def test_content_strategy_not_found_and_account_mismatch_fail():
    assert _query(ArtifactType.CONTENT_STRATEGY, 999).error.code == "CONTEXT_ERROR"
    assert _query(ArtifactType.CONTENT_STRATEGY, 501, account=8).error.code == "PERMISSION_ERROR"


def test_strategy_generated_opportunity_query_returns_content_and_both_lineages():
    result = _query(ArtifactType.CONTENT_OPPORTUNITY, 601)
    assert result.success is True
    assert result.data.artifact_type == ArtifactType.CONTENT_OPPORTUNITY
    view = ContentOpportunityArtifactView.model_validate(result.data.content)
    assert (view.account_ref, view.strategy_artifact_ref, view.research_artifact_ref) == (7, 501, 11)
    assert view.source_opportunity_ref == 21
    assert view.opportunity.source_opportunity_id == 21
    assert view.opportunity.topic == "Agent 项目避坑"
    assert view.opportunity.angle == "真实复盘"
    assert view.opportunity.content_goal == "说清工程误区"
    assert view.opportunity.why_now == "样本出现相关追问"
    assert view.opportunity.suggested_hook == "别先堆十个 Agent"
    assert view.opportunity.evidence_refs[0].model_dump() == {"kind": "competitor_note", "id": 31}
    assert view.retrievable_evidence_refs == [RetrievalEvidenceRef(type=EvidenceType.NOTE, id=31)]
    assert view.opportunity.constraints == ["明确样本边界"]
    assert result.data.lineage_refs == [
        ArtifactRef(type=ArtifactType.CONTENT_STRATEGY, id=501),
        ArtifactRef(type=ArtifactType.RESEARCH, id=11),
    ]


def test_research_opportunity_and_missing_opportunity_are_not_artifacts():
    assert _query(ArtifactType.CONTENT_OPPORTUNITY, 21).error.code == "CONTEXT_ERROR"
    assert _query(ArtifactType.CONTENT_OPPORTUNITY, 999).error.code == "CONTEXT_ERROR"


def test_content_creation_contract_closure_constructs_generate_draft_input():
    strategy_result = _query(ArtifactType.CONTENT_STRATEGY, 501)
    strategy = ContentStrategyArtifactView.model_validate(strategy_result.data.content)
    selected_ref = strategy.generated_opportunity_refs[0]
    opportunity_result = _query(ArtifactType.CONTENT_OPPORTUNITY, selected_ref)
    opportunity_view = ContentOpportunityArtifactView.model_validate(opportunity_result.data.content)
    source_evidence = opportunity_view.opportunity.evidence_refs[0]
    retrieval_ref = RetrievalEvidenceRef(type=EvidenceType.NOTE, id=source_evidence.id)
    evidence = EvidenceBundle(
        items=[
            EvidenceItem(
                evidence_ref=retrieval_ref,
                evidence_type=EvidenceType.NOTE,
                content="真实笔记正文",
                provenance="TEST",
            )
        ],
        purpose=opportunity_view.opportunity.content_goal,
    )
    context = GrowthContextResult(
        account={"id": 7},
        customer_model={"target_audience": "应届开发者"},
        context_version="v1",
        observed_at=NOW,
    )

    draft_input = GenerateDraftInput(
        account_context=context.model_dump(mode="json"),
        strategy=strategy.model_dump(mode="json"),
        strategy_ref=f"CONTENT_STRATEGY:{strategy_result.data.artifact_ref.id}",
        opportunity=opportunity_view.opportunity,
        evidence_bundle=evidence,
        user_constraints=opportunity_view.opportunity.constraints,
    )

    assert draft_input.strategy_ref == "CONTENT_STRATEGY:501"
    assert draft_input.strategy["account_ref"] == context.account["id"] == 7
    assert draft_input.opportunity.source_opportunity_id == opportunity_view.source_opportunity_ref == 21
    assert draft_input.opportunity.content_goal == "说清工程误区"
    assert draft_input.opportunity.evidence_refs[0].id == draft_input.evidence_bundle.items[0].evidence_ref.id == 31
    assert draft_input.account_context["customer_model"]["target_audience"] == draft_input.opportunity.target_audience


def test_tool_registry_and_architecture_remain_frozen():
    assert len(TOOL_REGISTRY) == 17
    assert TOOL_REGISTRY[ToolName.QUERY_ARTIFACT].effect == ToolEffect.READ_INTERNAL
