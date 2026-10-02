from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest

from app.agent.schemas.execution import ArtifactRef, ArtifactType
from app.agent.tools.artifact_contracts import CreatePostPublishReviewArtifactInput, CreateStrategyCandidateInput
from app.agent.tools.query_contracts import DraftArtifactView, QueryArtifactInput, QueryPostPublishMetricsInput
from app.agent.tools.query_tools import QueryArtifactTool, QueryPostPublishMetricsTool, QueryToolDataFacade
from app.agent.tools.semantic_contracts import AnalyzePostPublishReviewInput
from app.agent.tools.xhs_contracts import CollectionAccessScope, CollectionAuthorizationSource, CollectXhsNotesInput, NoteCollectionPurpose
from app.agent.tools.xhs_tools import CollectXhsNotesTool
from app.models.content_draft import ContentDraft
from app.models.content_draft_version import ContentDraftVersion
from app.repositories.publication_repo import PublicationRepository
from app.schemas.publication import PostPublishReviewLLMResult
from app.services.published_note_refresh_sev import PublishedNoteRefreshService


NOW = datetime.now(UTC)
URL = "https://www.xiaohongshu.com/explore/bound-note"


def _version(object_id, number, title):
    return ContentDraftVersion(
        id=object_id, draft_id=100, version=number,
        parent_version_id=object_id - 1 if number > 1 else None,
        created_from="GENERATED" if number == 1 else "USER_REVISION",
        regenerate_scope="test",
        draft_snapshot={"title": title, "body": f"V{number} 正文", "tags": [f"v{number}"], "cta": "收藏"},
        created_at=NOW,
    )


class DraftRepo:
    def __init__(self):
        self.root = ContentDraft(
            id=100, experiment_id=None, account_id=7, strategy_artifact_id=501,
            opportunity_id=601, content_goal="解释工程误区", title="Root", body="Root",
            tags=[], version=3, status="REVISED", generation_context={}, created_at=NOW, updated_at=NOW,
        )
        self.versions = {201: _version(201, 1, "真正发布的版本"), 202: _version(202, 2, "V2"), 203: _version(203, 3, "后来修改的版本")}

    def get_draft(self, draft_id):
        return self.root if draft_id == 100 else None

    def get_latest_version(self, draft_id):
        return self.versions[203]

    def get_version(self, version_id):
        return self.versions.get(version_id)

    def get_version_by_number(self, draft_id, number):
        return next((item for item in self.versions.values() if item.draft_id == draft_id and item.version == number), None)

    def version_content(self, version):
        from app.schemas.draft import DraftContent
        return DraftContent.model_validate({key: version.draft_snapshot.get(key) for key in ("title", "body", "tags", "cta")})


class PublicationRepo:
    def __init__(self, *, binding="draft:100:v1", package_binding="draft:100:v1"):
        self.note = SimpleNamespace(id=500, account_id=7, draft_id=100, publish_url=URL, raw_snapshot={"publish_package_id": 50, **({"draft_version_ref": binding} if binding else {})})
        self.package = SimpleNamespace(id=50, draft_id=100, stats={"draft_version_ref": package_binding})
        self.parser = PublicationRepository(None)

    def get_note(self, note_id):
        return self.note if note_id == 500 else None

    def get_package(self, package_id):
        return self.package if package_id == 50 else None

    def resolve_published_binding(self, note):
        self.parser.get_package = self.get_package
        return self.parser.resolve_published_binding(note)


class ReviewFacade(QueryToolDataFacade):
    def __init__(self, *, binding="draft:100:v1", package_binding="draft:100:v1"):
        self.drafts = DraftRepo()
        self.publication = PublicationRepo(binding=binding, package_binding=package_binding)
        self.public = [self._snapshot(10, NOW - timedelta(hours=1))]
        self.private = []

    def _snapshot(self, likes, observed):
        return SimpleNamespace(
            id=len(self.public) + 1 if hasattr(self, "public") else 1,
            collected_at=observed, view_count=0, like_count=likes, collect_count=5,
            comment_count=3, share_count=1, follow_count=0, profile_visit_count=0,
            raw_snapshot={"metrics": {"like_count": likes, "collect_count": 5, "comment_count": 3, "share_count": 1}},
        )

    def list_public_metrics(self, note_ref):
        return self.public

    def list_private_metrics(self, note_ref):
        return self.private


def _metrics(facade):
    return QueryPostPublishMetricsTool(facade=facade).execute(QueryPostPublishMetricsInput(
        account_ref=7, published_note_ref=500,
        window_start=NOW - timedelta(days=1), window_end=NOW + timedelta(days=1),
    ))


def test_binding_parses_to_real_version_id_and_legacy_does_not_guess():
    facade = ReviewFacade()
    result = _metrics(facade)
    assert result.success is True
    assert (result.data.account_ref, result.data.draft_ref) == (7, 100)
    assert result.data.published_draft_binding_ref == "draft:100:v1"
    assert result.data.published_draft_version_number == 1
    assert result.data.published_draft_version_ref == 201
    assert result.data.publish_package_ref == 50 and result.data.published_lineage_complete is True

    legacy = _metrics(ReviewFacade(binding="", package_binding=""))
    assert legacy.success is True
    assert legacy.data.published_draft_version_ref is None
    assert legacy.data.published_lineage_complete is False


@pytest.mark.parametrize(("binding", "package_binding", "code"), [
    ("draft:999:v1", "draft:999:v1", "PUBLISHED_VERSION_LINEAGE_MISMATCH"),
    ("draft:100:v1", "draft:100:v2", "PUBLISHED_VERSION_LINEAGE_MISMATCH"),
    ("bad-format", "bad-format", "INVALID_PUBLISHED_DRAFT_BINDING"),
])
def test_invalid_or_conflicting_binding_is_rejected(binding, package_binding, code):
    result = _metrics(ReviewFacade(binding=binding, package_binding=package_binding))
    assert result.success is False and result.error.code == code


def test_exact_published_v1_read_while_latest_is_v3():
    facade = ReviewFacade()
    metrics = _metrics(facade).data
    exact = QueryArtifactTool(facade=facade).execute(QueryArtifactInput(
        account_ref=7, artifact_ref=ArtifactRef(type=ArtifactType.DRAFT, id=metrics.draft_ref),
        expected_type=ArtifactType.DRAFT, draft_version_ref=metrics.published_draft_version_ref,
    ))
    view = DraftArtifactView.model_validate(exact.data.content)
    assert view.latest_draft_version_ref == 203
    assert view.latest_content.title == "后来修改的版本"
    assert view.resolved_draft_version_ref == 201
    assert view.resolved_content.title == "真正发布的版本"
    assert (view.strategy_artifact_ref, view.opportunity_ref, view.content_goal) == (501, 601, "解释工程误区")

    latest = QueryArtifactTool(facade=facade).execute(QueryArtifactInput(
        account_ref=7, artifact_ref=ArtifactRef(type=ArtifactType.DRAFT, id=100)
    ))
    assert DraftArtifactView.model_validate(latest.data.content).resolved_draft_version_ref == 203


def test_exact_version_from_other_root_is_rejected():
    facade = ReviewFacade()
    foreign = _version(301, 1, "其他 Root")
    foreign.draft_id = 101
    facade.drafts.versions[301] = foreign
    result = QueryArtifactTool(facade=facade).execute(QueryArtifactInput(
        account_ref=7, artifact_ref=ArtifactRef(type=ArtifactType.DRAFT, id=100), draft_version_ref=301,
    ))
    assert result.error.code == "DRAFT_VERSION_ROOT_MISMATCH"


class Collector:
    def __init__(self, success=True):
        self.success = success
        self.note_calls = 0

    def collect_notes(self, account, urls, **kwargs):
        self.note_calls += 1
        if not self.success:
            return {"success_count": 0, "failed_count": 1, "items": [], "warnings": [], "error_code": "PROVIDER_ERROR"}
        return {"success_count": 1, "failed_count": 0, "items": [{"input_value": urls[0], "status": "SUCCESS", "ids": {"competitor_note_id": 31}, "data_count": {"comments_saved": 0}, "warnings": []}], "warnings": []}


class MetricsService:
    def __init__(self, facade):
        self.facade = facade
        self.calls = 0

    def snapshot(self, note_ref, window):
        self.calls += 1
        self.facade.public.append(self.facade._snapshot(20, NOW))
        return SimpleNamespace(snapshot_ref=2)


def test_authorized_refresh_appends_canonical_metrics_and_preserves_history():
    facade = ReviewFacade()
    collector = Collector()
    metrics_service = MetricsService(facade)
    refresh = PublishedNoteRefreshService(collector=collector, metrics_service=metrics_service)
    scope = CollectionAccessScope(
        workspace_account_ref=7, authorization_source=CollectionAuthorizationSource.BOUND_PUBLISHED_NOTE,
        allowed_note_urls=(URL,), published_note_ref=500,
    )
    tool = CollectXhsNotesTool(collector=collector, access_scope=scope, refresh_service=refresh)
    before = _metrics(facade).data.public_metrics["likes"].value
    collected = tool.execute(CollectXhsNotesInput(
        account_ref=7, note_urls=[URL], include_comments=False,
        collection_purpose=NoteCollectionPurpose.REFRESH_BOUND_PUBLISHED_NOTE,
    ))
    after = _metrics(facade).data
    assert collected.success is True and before == 10
    assert after.public_metrics["likes"].value == 20
    assert after.public_metrics["collects"].value == 5 and after.public_metrics["comments"].value == 3
    assert len(facade.public) == 2 and metrics_service.calls == 1
    assert after.public_metrics["views"].value is None
    assert after.public_metrics["views"].provenance == "UNKNOWN"


def test_failed_or_research_collection_does_not_create_public_snapshot():
    facade = ReviewFacade()
    failed_collector = Collector(success=False)
    metrics_service = MetricsService(facade)
    refresh = PublishedNoteRefreshService(collector=failed_collector, metrics_service=metrics_service)
    assert refresh.refresh(7, 500, URL, include_comments=False, max_comments=0)["success_count"] == 0
    assert metrics_service.calls == 0 and len(facade.public) == 1

    research_collector = Collector()
    research_tool = CollectXhsNotesTool(
        collector=research_collector,
        access_scope=CollectionAccessScope(
            workspace_account_ref=7, authorization_source=CollectionAuthorizationSource.USER_PROVIDED,
            allowed_note_urls=(URL,),
        ),
        refresh_service=PublishedNoteRefreshService(collector=research_collector, metrics_service=metrics_service),
    )
    research_tool.execute(CollectXhsNotesInput(
        account_ref=7, note_urls=[URL], collection_purpose=NoteCollectionPurpose.RESEARCH_INPUT,
    ))
    assert metrics_service.calls == 0 and len(facade.public) == 1


def test_post_review_analyze_artifact_and_candidate_contracts_close():
    facade = ReviewFacade()
    metrics_result = _metrics(facade).data
    exact_result = QueryArtifactTool(facade=facade).execute(QueryArtifactInput(
        account_ref=7, artifact_ref=ArtifactRef(type=ArtifactType.DRAFT, id=100),
        draft_version_ref=metrics_result.published_draft_version_ref,
    ))
    draft = DraftArtifactView.model_validate(exact_result.data.content)
    published_ref = {"kind": "published_note", "id": 500}
    analyze = AnalyzePostPublishReviewInput(
        published_note={"published_note_ref": 500, "evidence_refs": [published_ref]},
        published_draft=draft.resolved_content.model_dump(mode="json"),
        content_strategy={"strategy_artifact_ref": draft.strategy_artifact_ref},
        opportunity={"opportunity_ref": draft.opportunity_ref, "content_goal": draft.content_goal},
        metrics=metrics_result,
        historical_context=[],
    )
    semantic = PostPublishReviewLLMResult(
        observed_results=["点赞 10"], public_performance_analysis="已观察",
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
    assert analyze.published_draft["title"] == "真正发布的版本"
    assert artifact.review_result.evidence_refs == semantic.evidence_refs
    assert candidate.candidate.status == "PROPOSED"
