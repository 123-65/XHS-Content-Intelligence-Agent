from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

from app.agent.schemas.execution import ArtifactRef, ArtifactType
from app.agent.tools.artifact_contracts import CreatePostPublishReviewArtifactInput, CreateStrategyCandidateInput
from app.agent.tools.query_contracts import QueryPostPublishMetricsInput
from app.agent.tools.query_tools import QueryPostPublishMetricsTool
from app.agent.tools.semantic_contracts import AnalyzePostPublishReviewInput
from app.agent.tools.xhs_contracts import (
    CollectionAccessScope,
    CollectionAuthorizationSource,
    CollectXhsNotesInput,
    NoteCollectionPurpose,
)
from app.schemas.publication import PostPublishReviewLLMResult


NOW = datetime.now(UTC)
URL_A = "https://www.xiaohongshu.com/explore/abc"
URL_B = "https://www.xiaohongshu.com/explore/other"


class MetricsFacade:
    def __init__(self, publish_url=URL_A):
        self.note = SimpleNamespace(id=500, account_id=7, draft_id=100, publish_url=publish_url)
        self.public = SimpleNamespace(
            collected_at=NOW,
            view_count=100,
            like_count=20,
            collect_count=5,
            comment_count=3,
            share_count=1,
            follow_count=2,
            profile_visit_count=4,
            raw_snapshot={"metrics": {
                "view_count": 100, "like_count": 20, "collect_count": 5,
                "comment_count": 3, "share_count": 1,
                "follow_count": 2, "profile_visit_count": 4,
            }},
        )
        self.version = SimpleNamespace(id=201)

    def get_published_note(self, note_ref):
        return self.note if note_ref == 500 else None

    def resolve_published_lineage(self, note):
        return ({
            "binding_ref": "draft:100:v1", "draft_ref": 100,
            "version_number": 1, "publish_package_ref": 50,
        }, self.version)

    def list_public_metrics(self, note_ref):
        return [self.public]

    def list_private_metrics(self, note_ref):
        return []


def _query(publish_url=URL_A):
    facade = MetricsFacade(publish_url)
    result = QueryPostPublishMetricsTool(facade=facade).execute(QueryPostPublishMetricsInput(
        account_ref=7,
        published_note_ref=500,
        window_start=NOW - timedelta(days=1),
        window_end=NOW + timedelta(days=1),
    ))
    assert result.success is True
    return result.data


def _authorized(metrics, scope):
    return (
        metrics.publish_url is not None
        and scope.published_note_ref == metrics.published_note_ref
        and metrics.publish_url in scope.allowed_note_urls
    )


def test_persisted_published_url_is_returned_and_builds_refresh_input():
    metrics = _query()
    assert metrics.published_note_ref == 500
    assert metrics.publish_url == URL_A
    scope = CollectionAccessScope(
        workspace_account_ref=7,
        authorization_source=CollectionAuthorizationSource.BOUND_PUBLISHED_NOTE,
        allowed_note_urls=(URL_A,),
        published_note_ref=500,
    )
    assert _authorized(metrics, scope) is True
    request = CollectXhsNotesInput(
        account_ref=metrics.account_ref,
        note_urls=[metrics.publish_url],
        collection_purpose=NoteCollectionPurpose.REFRESH_BOUND_PUBLISHED_NOTE,
    )
    assert request.note_urls == [URL_A]
    assert request.collection_purpose == NoteCollectionPurpose.REFRESH_BOUND_PUBLISHED_NOTE


def test_wrong_scope_url_is_not_substituted_or_authorized():
    metrics = _query()
    scope = CollectionAccessScope(
        workspace_account_ref=7,
        authorization_source=CollectionAuthorizationSource.BOUND_PUBLISHED_NOTE,
        allowed_note_urls=(URL_B,),
        published_note_ref=500,
    )
    assert _authorized(metrics, scope) is False
    assert metrics.publish_url == URL_A
    assert metrics.publish_url not in scope.allowed_note_urls


def test_wrong_published_note_scope_is_not_authorized_even_for_same_url():
    metrics = _query()
    scope = CollectionAccessScope(
        workspace_account_ref=7,
        authorization_source=CollectionAuthorizationSource.BOUND_PUBLISHED_NOTE,
        allowed_note_urls=(URL_A,),
        published_note_ref=600,
    )
    assert _authorized(metrics, scope) is False
    assert scope.published_note_ref != metrics.published_note_ref


def test_legacy_missing_url_remains_none_without_affecting_metrics():
    metrics = _query(None)
    assert metrics.publish_url is None
    assert metrics.public_metrics["likes"].value == 20
    assert metrics.published_draft_version_ref == 201


def test_final_post_review_contract_chain_remains_closed():
    metrics = _query()
    published_ref = {"kind": "published_note", "id": metrics.published_note_ref}
    analyze = AnalyzePostPublishReviewInput(
        published_note={"published_note_ref": 500, "publish_url": metrics.publish_url, "evidence_refs": [published_ref]},
        published_draft={"title": "真正发布的版本", "body": "正文", "tags": [], "cta": None},
        content_strategy={"strategy_artifact_ref": 501},
        opportunity={"opportunity_ref": 601, "content_goal": "解释工程误区"},
        metrics=metrics,
    )
    semantic = PostPublishReviewLLMResult(
        observed_results=["点赞 20"], public_performance_analysis="已观察",
        strategy_alignment="一致", what_worked=[], what_did_not_work=[], uncertainties=[],
        evidence_refs=[published_ref], strategy_candidates=[{
            "candidate_index": 0, "statement": "继续测试", "scope": "教程",
            "supporting_refs": [published_ref], "contradicting_refs": [],
            "confidence_context": "单篇样本", "status": "PROPOSED",
        }],
    )
    artifact = CreatePostPublishReviewArtifactInput(
        account_ref=7, published_note_ref=500, draft_ref=100, strategy_ref=501,
        opportunity_ref=601, review_result=semantic, evidence_refs=[published_ref],
    )
    candidate = CreateStrategyCandidateInput(
        account_ref=7, post_publish_review_ref=900, candidate=semantic.strategy_candidates[0],
    )
    assert analyze.published_note["publish_url"] == URL_A
    assert artifact.review_result.strategy_candidates[0].status == "PROPOSED"
    assert candidate.candidate.status == "PROPOSED"
