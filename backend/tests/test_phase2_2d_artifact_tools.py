from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

from app.agent.schemas.execution import ArtifactType
from app.agent.tools.artifact_contracts import (
    CreateContentStrategyArtifactInput,
    CreateDraftVersionInput,
    CreatePostPublishReviewArtifactInput,
    CreateResearchArtifactInput,
    CreateStrategyCandidateInput,
)
from app.agent.tools.artifact_tools import (
    CreateContentStrategyArtifactTool,
    CreateDraftVersionTool,
    CreatePostPublishReviewArtifactTool,
    CreateResearchArtifactTool,
    CreateStrategyCandidateTool,
)
from app.agent.tools.access_scopes import EvidenceAccessScope
from app.agent.tools.definitions import ToolName
from app.agent.tools.execution_context import ToolExecutionContext
from app.agent.tools.implementation_registry import TOOL_HANDLER_REGISTRY, build_tool_handler
from app.agent.tools.registry import TOOL_REGISTRY
from app.agent.tools.xhs_contracts import CollectionAccessScope, CollectionAuthorizationSource
from app.schemas.content_strategy import ContentStrategyResult


BACKEND_ROOT = Path(__file__).resolve().parents[1]
NOW = datetime.now(timezone.utc)


def _research_evidence():
    return {
        "account_id": 7,
        "accounts": [],
        "notes": [],
        "comments": [],
        "computed_metrics": {
            "note_count": 0,
            "comment_count": 0,
            "account_count": 0,
            "average_likes": 0,
            "average_collects": 0,
            "average_comments": 0,
            "ranked_notes": [],
        },
        "used_account_ids": [],
        "used_note_ids": [],
        "used_comment_ids": [],
        "ocr_note_ids": [],
        "data_gaps": ["样本较少"],
    }


def _research_result():
    return {
        "persona": {
            "positioning": "实用教程",
            "expertise": [],
            "target_audience": ["新手"],
            "value_proposition": "降低门槛",
            "tone_and_style": ["清晰"],
            "confidence": 0.7,
            "evidence": [],
        },
        "content_pillars": [],
        "audience_demands": [],
        "high_performing_patterns": [],
        "content_style": {"structure": [], "tone": [], "hooks": [], "visual_patterns": [], "evidence_note_ids": []},
        "follow_recommendation": {
            "why_follow": "持续观察",
            "what_to_learn": [],
            "what_not_to_copy": [],
            "confidence": 0.5,
            "evidence": [],
        },
        "content_opportunities": [],
        "conversion_signals": [],
        "risk_points": [],
        "data_gaps": ["样本较少"],
    }


def _strategy_result():
    return ContentStrategyResult(
        account_id=7,
        research_report_id=31,
        strategy_goal="教育用户",
        target_audience="新手",
        content_directions=[{
            "direction": "教程",
            "rationale": "有事实依据",
            "evidence_refs": [{"kind": "research_report", "id": 31}],
        }],
        rationale="基于研究",
        evidence_refs=[{"kind": "research_report", "id": 31}],
        applicable_constraints=[],
        opportunities=[{
            "source_opportunity_id": 41,
            "topic": "Agent 教程",
            "angle": "实战",
            "target_audience": "新手",
            "content_goal": "帮助理解",
            "why_now": "需求明确",
            "evidence_refs": [{"kind": "content_opportunity", "id": 41}],
            "suggested_hook": "三步学会",
            "constraints": [],
        }],
        provider="semantic-result",
        model="semantic-result",
    )


def _post_review_result():
    return {
        "observed_results": ["收藏数为 43"],
        "public_performance_analysis": "收藏表现较高。",
        "optional_conversion_analysis": None,
        "strategy_alignment": "方向一致。",
        "what_worked": ["清单结构"],
        "what_did_not_work": [],
        "uncertainties": ["样本较少"],
        "evidence_refs": [{"kind": "published_note", "id": 31}],
        "strategy_candidates": [{
            "candidate_index": 0,
            "statement": "继续验证清单结构。",
            "scope": "下一轮内容",
            "supporting_refs": [{"kind": "published_note", "id": 31}],
            "contradicting_refs": [],
            "confidence_context": "当前仅有一篇笔记。",
            "status": "PROPOSED",
        }],
    }


class FakeResearchRepository:
    def __init__(self):
        self.calls = 0

    def get_account(self, account_id):
        return SimpleNamespace(id=account_id) if account_id == 7 else None

    def create_report_bundle(self, report, breakdowns, opportunities):
        self.calls += 1
        report.id = 31
        report.created_at = NOW
        return report


class FakeAssembler:
    def assemble(self, create, evidence, semantic, engine, state):
        return SimpleNamespace(id=None, created_at=None), [], []


class FakeStrategyRepository:
    def create_strategy_bundle(self, result):
        return SimpleNamespace(id=51, research_artifact_id=31, created_at=NOW), [SimpleNamespace(id=61)]


class FakeDraftRepository:
    def __init__(self):
        self.root = None
        self.versions = []

    def create_agent_draft_root(self, **kwargs):
        self.root = SimpleNamespace(id=100, account_id=7, strategy_artifact_id=51, opportunity_id=61, content_goal="帮助理解")
        version = SimpleNamespace(id=201, version=1, parent_version_id=None, created_from="GENERATED", created_at=NOW)
        self.versions.append(version)
        return self.root, version

    def append_agent_draft_version(self, **kwargs):
        parent = next((item for item in self.versions if item.id == kwargs["parent_version_id"]), None)
        if parent is None or parent is not self.versions[-1]:
            raise ValueError("Parent Version 不是当前 latest Version")
        version = SimpleNamespace(
            id=parent.id + 1,
            version=parent.version + 1,
            parent_version_id=parent.id,
            created_from=kwargs["created_from"],
            created_at=NOW,
        )
        self.versions.append(version)
        return self.root, version


class FakePublicationRepository:
    def __init__(self):
        self.note = SimpleNamespace(id=31, account_id=7, draft_id=100)
        self.report = None
        self.candidate = None
        self.memory_writes = 0

    def get_note(self, object_id):
        return self.note if object_id == 31 else None

    def create_post_review(self, note, account_id, result, metadata=None):
        self.report = SimpleNamespace(
            id=71,
            account_id=account_id,
            published_note_id=note.id,
            action_suggestions=[item.model_dump(mode="json") for item in result.strategy_candidates],
            created_at=NOW,
        )
        return self.report

    def create_strategy_candidate(self, account_id, review_report_id, candidate):
        if self.report is None or review_report_id != self.report.id:
            raise ValueError("PostPublishReview 不存在")
        source = self.report.action_suggestions[candidate.candidate_index]
        if source["statement"] != candidate.statement:
            raise ValueError("Candidate snapshot mismatch")
        self.candidate = SimpleNamespace(id=81, review_report_id=review_report_id, status="PROPOSED", created_at=NOW)
        return self.candidate

    def get_strategy_candidate(self, object_id):
        return self.candidate if self.candidate and object_id == self.candidate.id else None


def test_research_artifact_uses_report_bundle_without_semantic_reexecution():
    repository = FakeResearchRepository()
    result = CreateResearchArtifactTool(repository=repository, assembler=FakeAssembler()).execute(
        CreateResearchArtifactInput(
            account_ref=7,
            research_result=_research_result(),
            research_evidence=_research_evidence(),
            report_name="Research",
        )
    )

    assert result.success and result.error is None
    assert result.data.artifact_ref.type is ArtifactType.RESEARCH
    assert result.data.artifact_ref.id == 31
    assert repository.calls == 1


def test_strategy_artifact_returns_real_generated_opportunity_ids():
    result = CreateContentStrategyArtifactTool(repository=FakeStrategyRepository()).execute(
        CreateContentStrategyArtifactInput(
            account_ref=7,
            research_artifact_ref=31,
            strategy_result=_strategy_result(),
        )
    )

    assert result.success
    assert result.data.artifact_ref.id == 51
    assert result.data.research_artifact_ref == 31
    assert result.data.generated_opportunity_refs == [61]


def test_draft_tool_creates_v1_v2_v3_under_one_root_with_version_parents():
    repository = FakeDraftRepository()
    tool = CreateDraftVersionTool(repository=repository)
    v1 = tool.execute(CreateDraftVersionInput(root={
        "action": "CREATE_V1",
        "account_ref": 7,
        "strategy_artifact_ref": 51,
        "opportunity_ref": 61,
        "content_goal": "帮助理解",
        "content": {"title": "V1", "body": "第一版"},
    }))
    v2 = tool.execute(CreateDraftVersionInput(root={
        "action": "APPEND",
        "draft_ref": v1.data.draft_ref,
        "parent_draft_ref": v1.data.draft_version_ref,
        "created_from": "REVIEW_REVISION",
        "content": {"title": "V2", "body": "第二版"},
    }))
    v3 = tool.execute(CreateDraftVersionInput(root={
        "action": "APPEND",
        "draft_ref": v2.data.draft_ref,
        "parent_draft_ref": v2.data.draft_version_ref,
        "created_from": "USER_REVISION",
        "content": {"title": "V3", "body": "第三版"},
    }))

    assert [v1.data.draft_ref, v2.data.draft_ref, v3.data.draft_ref] == [100, 100, 100]
    assert [v1.data.draft_version_ref, v2.data.draft_version_ref, v3.data.draft_version_ref] == [201, 202, 203]
    assert [v1.data.parent_draft_ref, v2.data.parent_draft_ref, v3.data.parent_draft_ref] == [None, 201, 202]
    assert [v1.data.created_from, v2.data.created_from, v3.data.created_from] == ["GENERATED", "REVIEW_REVISION", "USER_REVISION"]
    assert (repository.root.strategy_artifact_id, repository.root.opportunity_id, repository.root.content_goal) == (51, 61, "帮助理解")


def test_post_review_and_candidate_return_stable_refs_without_memory_write():
    repository = FakePublicationRepository()
    review_input = CreatePostPublishReviewArtifactInput(
        account_ref=7,
        published_note_ref=31,
        draft_ref=100,
        strategy_ref=51,
        opportunity_ref=61,
        review_result=_post_review_result(),
        evidence_refs=[{"kind": "published_note", "id": 31}],
    )
    review = CreatePostPublishReviewArtifactTool(repository=repository).execute(review_input)
    candidate = CreateStrategyCandidateTool(repository=repository).execute(
        CreateStrategyCandidateInput(
            account_ref=7,
            post_publish_review_ref=review.data.artifact_ref.id,
            candidate=review_input.review_result.strategy_candidates[0].model_copy(update={"created_from_review": 71}),
        )
    )

    assert review.success and review.data.artifact_ref.id == 71
    assert review.data.published_note_ref == 31
    assert candidate.success and candidate.data.strategy_candidate_ref == "STRATEGY_CANDIDATE:81"
    assert candidate.data.status == "PROPOSED"
    assert repository.get_strategy_candidate(81) is repository.candidate
    assert repository.memory_writes == 0


def test_artifact_failures_return_no_data_and_real_error():
    repository = FakeDraftRepository()
    failed = CreateDraftVersionTool(repository=repository).execute(CreateDraftVersionInput(root={
        "action": "APPEND",
        "draft_ref": 100,
        "parent_draft_ref": 999,
        "created_from": "USER_REVISION",
        "content": {"title": "非法", "body": "非法"},
    }))

    assert not failed.success
    assert failed.data is None
    assert failed.error is not None


def test_registry_closes_and_formal_builder_builds_all_seventeen_tools():
    assert set(TOOL_HANDLER_REGISTRY) == set(TOOL_REGISTRY)
    assert len(TOOL_HANDLER_REGISTRY) == 17
    context = ToolExecutionContext(
        db=object(),
        evidence_access_scope=EvidenceAccessScope.deny_all(),
        collection_access_scope=CollectionAccessScope(
            workspace_account_ref=7,
            authorization_source=CollectionAuthorizationSource.USER_PROVIDED,
        ),
    )
    for name in ToolName:
        assert build_tool_handler(name, context).name == name.value


def test_artifact_tool_architecture_has_no_forbidden_dependencies():
    source = (BACKEND_ROOT / "app" / "agent" / "tools" / "artifact_tools.py").read_text(encoding="utf-8")
    forbidden = (
        "app.llm",
        "Provider",
        "HTTPException",
        "fastapi",
        "app.agent.workflows",
        "StrategyMemoryService",
        "ContentExperiment",
        "CompetitorAnalysisRepository",
        "CompetitorReportService",
        "LLMStructuredCompetitorAnalyzer",
        "GenericArtifact",
    )
    assert not [token for token in forbidden if token in source]
