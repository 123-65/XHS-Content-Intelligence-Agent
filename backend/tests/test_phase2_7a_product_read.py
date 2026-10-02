from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from app.core.database import SessionLocal
from app.models.account import AccountProfile
from app.models.agent_conversation import AgentConversationMessage
from app.models.competitors_analysis import CompetitorAnalysisReport
from app.models.content_draft import ContentDraft
from app.models.content_draft_version import ContentDraftVersion
from app.models.content_experiment import ContentExperiment
from app.models.content_opportunity import ContentOpportunity
from app.models.content_strategy_artifact import ContentStrategyArtifact
from app.models.public_metric_snapshot import PublicMetricSnapshot
from app.models.published_note import PublishedNote
from app.models.review_report import ReviewReport
from app.models.strategy_candidate import StrategyCandidate
from app.schemas.agent_conversation import ConversationCreate
from app.services.agent_conversation_sev import AgentConversationService
from app.services.product_read_sev import ProductReadError, ProductReadService
from app.api.product_read import _service
from app.main import app
from fastapi.testclient import TestClient


NOW = datetime.now(UTC).replace(tzinfo=None)


def obj(**values):
    return SimpleNamespace(**values)


def service_with_fakes():
    service = ProductReadService.__new__(ProductReadService)
    research_report = obj(
        id=10, account_id=7, name="Research", keyword="Agent", summary="真实研究", status="SUCCESS",
        persona_patterns=[{"name": "工程师"}], content_pillars=[{"name": "避坑"}], content_insights=["先验证"],
        suggestions=["小步迭代"], source_type="COMPETITOR", target_metric="engagement", note_count=8,
        comment_count=21, competitor_note_ids=[1, 2], note_snapshot_ids=[], competitor_account_ids=[3],
        risk_points=["样本有限"], error_message=None, created_at=NOW, updated_at=NOW,
    )
    research_opportunity = obj(
        id=20, strategy_artifact_id=None, opportunity_title="Agent 避坑", suggested_angle="真实复盘",
        target_audience="开发者", evidence_summary="评论追问", opportunity_score=88, risk_level="LOW",
    )
    service.research = obj(get_report=lambda ref: research_report if ref == 10 else None, list_opportunities=lambda ref: [research_opportunity])

    strategy = obj(
        id=30, account_id=7, research_artifact_id=10, strategy_goal="建立信任", target_audience="开发者",
        content_directions=[{"direction": "复盘"}], rationale="来自真实样本", evidence_refs=[{"kind": "research_report", "id": 10}],
        applicable_constraints=["不夸大"], created_at=NOW,
    )
    generated = obj(
        id=31, source_opportunity_id=20, opportunity_title="Agent 避坑", suggested_angle="真实复盘",
        target_audience="开发者", content_goal="解释误区", why_now="需求增长", suggested_hook="别先堆 Agent",
        evidence_refs=[{"kind": "content_opportunity", "id": 20}], constraints=["不夸大"],
    )
    service.strategies = obj(get_strategy_artifact=lambda ref: strategy if ref == 30 else None, list_strategy_opportunities=lambda ref: [generated])

    draft = obj(
        id=40, account_id=7, strategy_artifact_id=30, opportunity_id=31, content_goal="解释误区", status="GENERATED",
        version=2, title="旧标题", recommended_title="新标题", body="旧正文", body_text="新正文", tags=["old"], tag_list=["Agent"],
        cta=None, cta_text="留言", created_at=NOW, updated_at=NOW,
    )
    versions = [
        obj(id=41, draft_id=40, version=1, parent_version_id=None, created_from="GENERATED", draft_snapshot={"title": "V1", "body": "B1", "tags": []}, created_at=NOW),
        obj(id=42, draft_id=40, version=2, parent_version_id=41, created_from="USER_REVISION", draft_snapshot={"title": "V2", "body": "B2", "tags": ["Agent"], "cta": "留言"}, created_at=NOW),
    ]
    review = obj(id=43, status="SUCCESS", passed=True, score=90, risk_level="LOW", summary="通过", created_at=NOW)
    service.drafts = obj(
        get_draft=lambda ref: draft if ref == 40 else None, list_versions=lambda ref: versions,
        list_reviews=lambda ref: [review], get_version_by_number=lambda ref, version: versions[version - 1],
    )

    note = obj(id=50, account_id=7, draft_id=40, publish_url="https://xhs.example/note", platform="xhs", status="PUBLISHED", published_at=NOW, created_at=NOW)
    public = obj(id=51, snapshot_window="D1", view_count=100, like_count=10, collect_count=5, comment_count=2, share_count=1, follow_count=0, profile_visit_count=3, source_type="XHS_MCP", collected_at=NOW)
    post_review = obj(id=52, status="SUCCESS", result_status="GOOD", summary="表现稳定", data_facts=[{"likes": 10}], inferences=[{"result": "有效"}], created_at=NOW)
    candidate = obj(id=53, statement="继续测试", scope="教程", supporting_refs=[], contradicting_refs=[], confidence_context="单篇", status="PROPOSED")
    service.publications = obj(
        get_note=lambda ref: note if ref == 50 else None,
        resolve_published_binding=lambda value: {"version_number": 2},
        list_public_metrics=lambda ref: [public], list_private_metrics=lambda ref: [],
        get_post_publish_review=lambda ref: post_review, list_strategy_candidates=lambda ref: [candidate],
    )
    return service


def test_typed_product_details_project_real_persisted_fields():
    service = service_with_fakes()
    research = service.research_detail(10, 7)
    strategy = service.strategy_detail(30, 7)
    draft = service.draft_detail(40, 7)
    publication = service.publication_detail(50, 7)

    assert research.summary == "真实研究" and research.opportunities[0].ref == 20
    assert strategy.research_ref == 10 and strategy.opportunities[0].ref == 31
    assert strategy.opportunities[0].content_goal == "解释误区"
    assert draft.latest_version_ref == 42 and draft.current_content.title == "V2"
    assert [(item.version, item.parent_version_ref) for item in draft.versions] == [(1, None), (2, 41)]
    assert draft.versions[0].content.title == "V1"
    assert publication.published_draft_version_ref == 42
    assert publication.public_metrics[0].values["view_count"] == 100
    assert publication.post_publish_review.ref == 52 and publication.strategy_candidates[0].ref == 53


def test_product_read_service_reads_complete_postgres_lineage():
    with SessionLocal() as db:
        account = AccountProfile(account_name="Read API Real", positioning="test", target_audience="test")
        db.add(account); db.flush()
        report = CompetitorAnalysisReport(account_id=account.id, name="Real Research", keyword="Agent", summary="真实落库研究", note_count=3, comment_count=9)
        db.add(report); db.flush()
        source = ContentOpportunity(report_id=report.id, opportunity_title="工程复盘", suggested_angle="真实经验", content_pillar="工程", comment_demand_type="QUESTION", evidence_summary="真实评论", opportunity_score=80)
        db.add(source); db.flush()
        strategy = ContentStrategyArtifact(account_id=account.id, research_artifact_id=report.id, strategy_goal="建立信任", target_audience="开发者", content_directions=[], rationale="真实依据", evidence_refs=[], applicable_constraints=[] , provider="test", model="test")
        db.add(strategy); db.flush()
        opportunity = ContentOpportunity(report_id=report.id, strategy_artifact_id=strategy.id, source_opportunity_id=source.id, opportunity_title="工程复盘", suggested_angle="真实经验", content_pillar="工程", comment_demand_type="QUESTION", evidence_summary="真实评论", opportunity_score=80, content_goal="解释误区", why_now="需求明确", suggested_hook="别先堆功能", evidence_refs=[], constraints=[])
        db.add(opportunity); db.flush()
        experiment = ContentExperiment(account_id=account.id, analysis_report_id=report.id, content_opportunity_id=source.id, experiment_name="read", hypothesis="read", target_metric="engagement")
        db.add(experiment); db.flush()
        draft = ContentDraft(account_id=account.id, experiment_id=experiment.id, strategy_artifact_id=strategy.id, opportunity_id=opportunity.id, content_goal="解释误区", title="V1", body="正文", tags=["Agent"], version=1)
        db.add(draft); db.flush()
        version = ContentDraftVersion(draft_id=draft.id, version=1, created_from="GENERATED", draft_snapshot={"title": "V1", "body": "正文", "tags": ["Agent"], "cta": None})
        db.add(version); db.flush()
        note = PublishedNote(account_id=account.id, experiment_id=experiment.id, draft_id=draft.id, publish_url="https://www.xiaohongshu.com/explore/read-api", raw_snapshot={"draft_version_ref": f"draft:{draft.id}:v1"})
        db.add(note); db.flush()
        metric = PublicMetricSnapshot(published_note_id=note.id, snapshot_window="D1", view_count=123, like_count=12)
        db.add(metric); db.flush()
        review = ReviewReport(draft_id=draft.id, account_id=account.id, experiment_id=experiment.id, published_note_id=note.id, review_type="POST_PUBLISH_REVIEW_V1", summary="真实复盘")
        db.add(review); db.flush()
        candidate = StrategyCandidate(review_report_id=review.id, account_id=account.id, source_candidate_index=0, statement="继续测试", scope="教程", supporting_refs=[], contradicting_refs=[], confidence_context="单篇", status="PROPOSED")
        db.add(candidate); db.commit()

        service = ProductReadService(db)
        assert service.research_detail(report.id, account.id).summary == "真实落库研究"
        assert service.strategy_detail(strategy.id, account.id).opportunities[0].ref == opportunity.id
        assert service.draft_detail(draft.id, account.id).latest_version_ref == version.id
        publication = service.publication_detail(note.id, account.id)
        assert publication.public_metrics[0].values["view_count"] == 123
        assert publication.private_metrics_status == "UNKNOWN"
        assert publication.post_publish_review.ref == review.id
        assert publication.strategy_candidates[0].ref == candidate.id


def test_private_metrics_unknown_is_not_fabricated_as_zero():
    publication = service_with_fakes().publication_detail(50, 7)
    assert publication.private_metrics_status == "UNKNOWN"
    assert publication.private_metrics == []
    assert "private_metrics" not in publication.model_dump()["public_metrics"][0]["values"]


def test_typed_http_endpoints_and_cross_account_status():
    fake = service_with_fakes()
    app.dependency_overrides[_service] = lambda: fake
    try:
        client = TestClient(app)
        paths = (
            "/api/artifacts/research/10", "/api/artifacts/strategy/30",
            "/api/artifacts/draft/40", "/api/publications/50",
        )
        assert [client.get(path, params={"account_ref": 7}).status_code for path in paths] == [200, 200, 200, 200]
        rejected = client.get(paths[0], params={"account_ref": 8})
        assert rejected.status_code == 403
        assert rejected.json()["detail"]["code"] == "RESEARCH_ACCOUNT_MISMATCH"
    finally:
        app.dependency_overrides.clear()


@pytest.mark.parametrize(("method", "ref"), [("research_detail", 10), ("strategy_detail", 30), ("draft_detail", 40), ("publication_detail", 50)])
def test_every_detail_rejects_cross_account_access(method, ref):
    with pytest.raises(ProductReadError, match="不属于当前 Account") as rejected:
        getattr(service_with_fakes(), method)(ref, 8)
    assert rejected.value.code.endswith("ACCOUNT_MISMATCH")


def list_service_with_fakes():
    service = ProductReadService.__new__(ProductReadService)
    account = obj(id=7)
    other = obj(id=8)
    research = [
        obj(id=index, account_id=7, name=f"Research {index}", keyword="Agent", status="SUCCESS", created_at=NOW, updated_at=NOW)
        for index in range(1, 26)
    ]
    strategies = [obj(id=30, account_id=7, research_artifact_id=1, strategy_goal="Goal", target_audience="Audience", created_at=NOW)]
    drafts = [obj(id=40, account_id=7, title="Draft", recommended_title="Draft V2", version=2, status="GENERATED", updated_at=NOW)]
    note = obj(id=50, account_id=7, draft_id=40, draft_version_id=42, status="PUBLISHED", published_at=NOW)
    draft = drafts[0]
    version = obj(id=42, version=2)
    review = obj(id=60, account_id=7, published_note_id=50, status="SUCCESS", result_status="GOOD", created_at=NOW)

    def page(items, account_id, offset, limit):
        scoped = items if account_id == 7 else []
        return scoped[offset:offset + limit], len(scoped)

    service.research = obj(
        get_account=lambda ref: account if ref == 7 else other if ref == 8 else None,
        list_reports_by_account=lambda account_id, offset, limit: page(research, account_id, offset, limit),
    )
    service.strategies = obj(list_strategies_by_account=lambda account_id, offset, limit: page(strategies, account_id, offset, limit))
    service.drafts = obj(list_drafts_by_account=lambda account_id, offset, limit: page(drafts, account_id, offset, limit))
    service.publications = obj(
        list_notes_by_account=lambda account_id, offset, limit: page([(note, draft, version)], account_id, offset, limit),
        list_reviews_by_account=lambda account_id, offset, limit: page([review], account_id, offset, limit),
    )
    return service


def test_asset_indexes_are_account_scoped_paginated_and_empty_safe():
    service = list_service_with_fakes()

    first = service.list_research(7, page_no=1, page_size=10)
    third = service.list_research(7, page_no=3, page_size=10)
    assert (first.total, first.pages, len(first.items)) == (25, 3, 10)
    assert [item.ref for item in third.items] == [21, 22, 23, 24, 25]
    assert service.list_strategies(7, 1, 20).items[0].research_ref == 1
    assert service.list_drafts(7, 1, 20).items[0].ref == 40
    assert service.list_publications(7, 1, 20).items[0].draft_version_ref == 42
    assert service.list_reviews(7, 1, 20).items[0].published_note_ref == 50

    for method in ("list_research", "list_strategies", "list_drafts", "list_publications", "list_reviews"):
        page_result = getattr(service, method)(8, 1, 20)
        assert page_result.total == 0 and page_result.items == []


def test_asset_indexes_reject_unknown_account_and_oversized_page():
    service = list_service_with_fakes()
    with pytest.raises(ProductReadError) as rejected:
        service.list_drafts(999, 1, 20)
    assert rejected.value.code == "ACCOUNT_NOT_FOUND"

    app.dependency_overrides[_service] = lambda: service
    try:
        response = TestClient(app).get(
            "/api/artifacts/draft",
            params={"account_ref": 7, "page_size": 101},
        )
        assert response.status_code == 422
    finally:
        app.dependency_overrides.clear()


def test_conversation_100_message_keyset_pages_are_stable_after_insert():
    with SessionLocal() as db:
        account = AccountProfile(account_name="Pagination", positioning="test", target_audience="test")
        db.add(account)
        db.commit()
        db.refresh(account)
        service = AgentConversationService(db)
        conversation = service.create_conversation(ConversationCreate(account_id=account.id))
        db.add_all([
            AgentConversationMessage(
                conversation_id=conversation.id, role="USER", content=f"message-{index:03d}",
                message_type="TEXT", metadata_payload={}, created_at=NOW,
            )
            for index in range(1, 101)
        ])
        db.commit()

        first = service.list_message_page(conversation.id, limit=40)
        assert [item.content for item in first.items] == [f"message-{index:03d}" for index in range(61, 101)]
        db.add(AgentConversationMessage(conversation_id=conversation.id, role="USER", content="new-message", message_type="TEXT", metadata_payload={}, created_at=NOW))
        db.commit()
        second = service.list_message_page(conversation.id, limit=40, before_id=first.next_cursor)
        third = service.list_message_page(conversation.id, limit=40, before_id=second.next_cursor)

        combined = [*third.items, *second.items, *first.items]
        assert len(combined) == 100
        assert len({item.id for item in combined}) == 100
        assert [item.content for item in combined] == [f"message-{index:03d}" for index in range(1, 101)]
        assert (first.has_more, second.has_more, third.has_more) == (True, True, False)
        assert (len(first.items), len(second.items), len(third.items)) == (40, 40, 20)
