from datetime import UTC, datetime, timedelta

from app.agent.schemas.execution import ArtifactRef, ArtifactType, WorkflowStatus
from app.agent.tools.access_scopes import EvidenceAccessScope
from app.agent.tools.artifact_contracts import CreatePostPublishReviewArtifactResult, CreateStrategyCandidateResult
from app.agent.tools.definitions import ToolError, ToolName, ToolResult
from app.agent.tools.execution_context import ToolExecutionContext
from app.agent.tools.query_contracts import ArtifactResult, GrowthContextResult, MetricValue, MetricWindowResult, PostPublishMetricsResult
from app.agent.tools.xhs_contracts import CollectionAccessScope, CollectionAuthorizationSource, CollectXhsNotesResult
from app.agent.workflows.definitions import WorkflowId
from app.agent.workflows.implementation_registry import WORKFLOW_HANDLER_REGISTRY, build_workflow_handler
from app.agent.workflows.post_publish_review import PostPublishReviewWorkflow, PostPublishReviewWorkflowInput
from app.schemas.publication import PostPublishReviewLLMResult, StrategyCandidate


NOW = datetime.now(UTC)
URL = "https://www.xiaohongshu.com/explore/note-1"


def _error(code="TEST_ERROR", retryable=False, category="TEST"):
    return ToolError(code=code, category=category, retryable=retryable, safe_message="失败")


def _metrics(public=True, private=True, url=URL, lineage=True, account=7):
    return PostPublishMetricsResult(
        published_note_ref=31, publish_url=url, account_ref=account, draft_ref=41,
        published_draft_binding_ref="binding:51", published_draft_version_number=1,
        published_draft_version_ref=51 if lineage else None, published_lineage_complete=lineage,
        public_metrics_status="AVAILABLE" if public else "UNKNOWN",
        public_metric_snapshot_ref=41 if public else None,
        public_metrics={"likes": MetricValue(value=12, provenance="MEASURED")} if public else {},
        private_metric_snapshot_ref=42 if private else None,
        private_metrics={"dm_count": MetricValue(value=2 if private else None, provenance="USER_ATTRIBUTED" if private else "UNKNOWN")},
        window=MetricWindowResult(start=NOW - timedelta(days=7), end=NOW), provenance=["MEASURED"],
    )


def _draft():
    return {
        "account_ref": 7, "strategy_artifact_ref": 61, "opportunity_ref": 71, "content_goal": "增长",
        "latest_draft_version_ref": 53, "latest_version": 3,
        "latest_content": {"title": "V3", "body": "latest", "tags": ["v3"], "cta": None},
        "resolved_draft_version_ref": 51, "resolved_version": 1,
        "resolved_content": {"title": "V1", "body": "published", "tags": ["v1"], "cta": None},
        "status": "PUBLISHED",
    }


def _strategy():
    return {
        "account_ref": 7, "research_artifact_ref": 11, "strategy_goal": "增长", "target_audience": "用户",
        "content_directions": [{"direction": "教程", "rationale": "有效", "evidence_refs": [{"kind": "research_report", "id": 11}]}],
        "rationale": "测试", "evidence_refs": [{"kind": "research_report", "id": 11}],
        "generated_opportunity_refs": [71],
    }


def _opportunity():
    return {
        "account_ref": 7, "strategy_artifact_ref": 61, "research_artifact_ref": 11, "source_opportunity_ref": 21,
        "opportunity": {"source_opportunity_id": 21, "topic": "主题", "angle": "角度", "target_audience": "用户",
                        "content_goal": "增长", "why_now": "现在", "evidence_refs": [{"kind": "research_report", "id": 11}],
                        "suggested_hook": "开头", "constraints": []},
    }


def _analysis(candidates=2):
    return PostPublishReviewLLMResult(
        observed_results=["点赞 12"], public_performance_analysis="有效", optional_conversion_analysis=None,
        strategy_alignment="一致", what_worked=["标题"], what_did_not_work=[], uncertainties=[],
        evidence_refs=[{"kind": "published_note", "id": 31}],
        strategy_candidates=[StrategyCandidate(candidate_index=i, statement=f"测试 {i}", scope="内容", confidence_context="样本有限") for i in range(candidates)],
    )


class FakeRouter:
    def __init__(self, *, metrics=None, refreshed_metrics=None, refresh_failure=False, candidate_failure=None):
        self.metrics = metrics or _metrics()
        self.refreshed_metrics = refreshed_metrics or self.metrics
        self.refresh_failure = refresh_failure
        self.candidate_failure = candidate_failure
        self.calls = {name: 0 for name in ToolName}
        self.analysis_input = None
        self.candidate_inputs = []

    def build(self, name, context):
        router = self
        class Handler:
            def execute(self, data):
                router.calls[name] += 1
                if name == ToolName.QUERY_GROWTH_CONTEXT:
                    return ToolResult(success=True, data=GrowthContextResult(context_version="v1", observed_at=NOW))
                if name == ToolName.QUERY_POST_PUBLISH_METRICS:
                    value = router.metrics if router.calls[name] == 1 else router.refreshed_metrics
                    return ToolResult(success=True, data=value)
                if name == ToolName.QUERY_ARTIFACT:
                    content = _draft() if data.artifact_ref.type == ArtifactType.DRAFT else (_strategy() if data.artifact_ref.type == ArtifactType.CONTENT_STRATEGY else _opportunity())
                    return ToolResult(success=True, data=ArtifactResult(artifact_ref=data.artifact_ref, artifact_type=data.artifact_ref.type, version="v1", content=content))
                if name == ToolName.COLLECT_XHS_NOTES:
                    if router.refresh_failure:
                        return ToolResult(success=False, error=_error("PROVIDER_ERROR", True))
                    return ToolResult(success=True, data=CollectXhsNotesResult(requested_count=1, collected_count=1, failed_count=0, items=[], failed_items=[]))
                if name == ToolName.ANALYZE_POST_PUBLISH_REVIEW:
                    router.analysis_input = data
                    return ToolResult(success=True, data=_analysis())
                if name == ToolName.CREATE_POST_PUBLISH_REVIEW_ARTIFACT:
                    return ToolResult(success=True, data=CreatePostPublishReviewArtifactResult(artifact_ref=ArtifactRef(type=ArtifactType.POST_PUBLISH_REVIEW, id=81), published_note_ref=31))
                if name == ToolName.CREATE_STRATEGY_CANDIDATE:
                    router.candidate_inputs.append(data)
                    if router.candidate_failure == data.candidate.candidate_index:
                        return ToolResult(success=False, error=_error("PERSISTENCE_ERROR"))
                    return ToolResult(success=True, data=CreateStrategyCandidateResult(strategy_candidate_ref=f"STRATEGY_CANDIDATE:{90 + data.candidate.candidate_index}", status="PROPOSED", review_report_ref=81))
                raise AssertionError(name)
        return Handler()


def _input(**changes):
    values = dict(account_ref=7, published_note_ref=31, window_start=NOW - timedelta(days=7), window_end=NOW)
    values.update(changes)
    return PostPublishReviewWorkflowInput(**values)


def _context(scope=True):
    collection = CollectionAccessScope(workspace_account_ref=7, authorization_source=CollectionAuthorizationSource.BOUND_PUBLISHED_NOTE, allowed_note_urls=(URL,), published_note_ref=31) if scope else None
    return ToolExecutionContext(db=object(), evidence_access_scope=EvidenceAccessScope.deny_all(), collection_access_scope=collection)


def _run(monkeypatch, router, data=None, context=None):
    monkeypatch.setattr("app.agent.workflows.post_publish_review.build_tool_handler", router.build)
    return PostPublishReviewWorkflow().execute(data or _input(), context or _context())


def test_registered_and_standard_chain_uses_exact_published_v1(monkeypatch):
    assert WorkflowId.POST_PUBLISH_REVIEW_V1 in WORKFLOW_HANDLER_REGISTRY
    assert isinstance(build_workflow_handler(WorkflowId.POST_PUBLISH_REVIEW_V1), PostPublishReviewWorkflow)
    router = FakeRouter()
    result = _run(monkeypatch, router)
    assert result.status == WorkflowStatus.SUCCESS
    assert result.review_artifact_ref == 81
    assert result.candidate_refs == ["STRATEGY_CANDIDATE:90", "STRATEGY_CANDIDATE:91"]
    assert router.analysis_input.published_draft["title"] == "V1"
    assert {(ref.kind, ref.id) for ref in router.analysis_input.grounding_refs}.issuperset({
        ("published_note", 31), ("public_metric_snapshot", 41),
        ("private_metric_snapshot", 42), ("research_report", 11),
    })
    assert all(item.candidate.status == "PROPOSED" for item in router.candidate_inputs)


def test_missing_note_waits_but_unknown_public_metrics_continue_analysis(monkeypatch):
    router = FakeRouter()
    missing_note = _run(monkeypatch, router, _input(published_note_ref=None))
    assert missing_note.status == WorkflowStatus.WAITING_USER
    assert router.calls[ToolName.ANALYZE_POST_PUBLISH_REVIEW] == 0
    router = FakeRouter(metrics=_metrics(public=False))
    no_metrics = _run(monkeypatch, router)
    assert no_metrics.status == WorkflowStatus.PARTIAL_SUCCESS
    assert "PUBLIC_METRICS_UNKNOWN" in no_metrics.warnings
    assert router.calls[ToolName.ANALYZE_POST_PUBLISH_REVIEW] == 1
    assert router.analysis_input.metrics.public_metrics == {}


def test_lineage_and_account_fail_before_analysis(monkeypatch):
    for metrics, code in ((_metrics(lineage=False), "PUBLISHED_VERSION_LINEAGE_MISSING"), (_metrics(account=8), "PERMISSION_ERROR")):
        router = FakeRouter(metrics=metrics)
        result = _run(monkeypatch, router)
        assert result.status == WorkflowStatus.FAILED and result.error.code == code
        assert router.calls[ToolName.ANALYZE_POST_PUBLISH_REVIEW] == 0


def test_refresh_requeries_and_private_unknown_is_partial(monkeypatch):
    router = FakeRouter(metrics=_metrics(private=False), refreshed_metrics=_metrics(private=False))
    result = _run(monkeypatch, router, _input(refresh_public_metrics=True))
    assert router.calls[ToolName.COLLECT_XHS_NOTES] == 1
    assert router.calls[ToolName.QUERY_POST_PUBLISH_METRICS] == 2
    assert result.status == WorkflowStatus.PARTIAL_SUCCESS
    assert "PRIVATE_METRICS_UNKNOWN" in result.warnings


def test_refresh_failure_with_old_metrics_degrades_but_scope_and_url_are_fatal(monkeypatch):
    result = _run(monkeypatch, FakeRouter(refresh_failure=True), _input(refresh_public_metrics=True))
    assert result.status == WorkflowStatus.PARTIAL_SUCCESS and "PUBLIC_METRICS_REFRESH_FAILED" in result.warnings
    no_url = _run(monkeypatch, FakeRouter(metrics=_metrics(url=None)), _input(refresh_public_metrics=True))
    assert no_url.status == WorkflowStatus.FAILED and no_url.error.code == "PUBLISHED_URL_MISSING"
    denied = _run(monkeypatch, FakeRouter(), _input(refresh_public_metrics=True), _context(scope=False))
    assert denied.status == WorkflowStatus.FAILED and denied.error.code == "PERMISSION_ERROR"


def test_candidate_partial_resume_only_retries_pending_index(monkeypatch):
    router = FakeRouter(candidate_failure=1)
    first = _run(monkeypatch, router)
    assert first.status == WorkflowStatus.PARTIAL_SUCCESS
    assert first.candidate_refs == ["STRATEGY_CANDIDATE:90"]
    assert "STRATEGY_CANDIDATE_PERSIST_PARTIAL" in first.warnings
    router.candidate_failure = None
    resumed = PostPublishReviewWorkflow().resume(first.state, _input(), _context())
    assert resumed.candidate_refs == ["STRATEGY_CANDIDATE:90", "STRATEGY_CANDIDATE:91"]
    assert router.calls[ToolName.ANALYZE_POST_PUBLISH_REVIEW] == 1
    assert router.calls[ToolName.CREATE_POST_PUBLISH_REVIEW_ARTIFACT] == 1
