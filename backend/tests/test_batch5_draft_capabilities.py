from pathlib import Path
from types import SimpleNamespace

from app.models.content_draft import ContentDraft
from app.models.content_draft_version import ContentDraftVersion
from app.models.draft_revision_plan import DraftRevisionPlan
from app.models.review_report import ReviewReport
from app.schemas.content_strategy import ContentOpportunityResult, EvidenceRef
from app.schemas.draft import DraftGenerationInput, DraftReviewInput, DraftRevisionInput
from app.services.draft_generation_sev import DraftGenerationService
from app.services.draft_review_sev import DRAFT_REVIEW_PROMPT_VERSION, DraftReviewService
from app.services.draft_revision_sev import DRAFT_REVISION_PROMPT_VERSION, DraftRevisionService


APP_ROOT = Path(__file__).resolve().parents[1] / "app"


class FakeLLMClient:
    provider = "fake-provider"
    model = "fake-model"

    def __init__(self, outputs):
        self.outputs = list(outputs)
        self.calls = []

    def generate_structured(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(
            data=self.outputs.pop(0),
            usage=SimpleNamespace(prompt_tokens=10, completion_tokens=20, total_tokens=30),
            estimated_cost=0.01,
            raw_response_id="fake-response",
        )


class FakeDraftRepository:
    def __init__(self):
        self.account = SimpleNamespace(
            id=7,
            positioning="Agent 项目求职内容",
            target_audience="27 届普通本科生",
            tone_preference="真实、自然",
            forbidden_topics="夸大求职结果",
        )
        self.opportunity = SimpleNamespace(id=21, opportunity_title="Agent 项目避坑")
        self.drafts = {}
        self.reviews = {}
        self.versions = []
        self.next_draft_id = 1

    def get_account(self, account_id):
        return self.account if account_id == 7 else None

    def get_opportunity(self, opportunity_id):
        return self.opportunity if opportunity_id == 21 else None

    def resolve_legacy_experiment_id(self, account_id, opportunity_id):
        return 301 if (account_id, opportunity_id) == (7, 21) else None

    def create_draft(self, *, experiment_id, content, version, status, context, llm_result):
        draft = SimpleNamespace(
            id=self.next_draft_id,
            experiment_id=experiment_id,
            title=content.title,
            recommended_title=content.title,
            body=content.body,
            body_text=content.body,
            tags=content.tags,
            tag_list=content.tags,
            cta=content.cta,
            cta_text=content.cta,
            version=version,
            status=status,
            generation_context=context,
        )
        self.drafts[draft.id] = draft
        self.next_draft_id += 1
        return draft

    def create_version(self, draft, *, created_from, parent_draft_ref, applied_changes):
        version = SimpleNamespace(
            draft_id=draft.id,
            version=draft.version,
            created_from=created_from,
            parent_draft_ref=parent_draft_ref,
            applied_changes=applied_changes,
        )
        self.versions.append(version)
        return version

    def get_draft(self, draft_id):
        return self.drafts.get(draft_id)

    def create_review(self, draft, account_id, result, llm_result):
        review = SimpleNamespace(
            id=len(self.reviews) + 101,
            draft_id=draft.id,
            issues=[item.model_dump() for item in result.issues],
            suggestions=[item.suggestion for item in result.issues],
            summary=result.summary,
        )
        self.reviews[review.id] = review
        return review

    def get_review(self, review_id):
        return self.reviews.get(review_id)


def _opportunity():
    return ContentOpportunityResult(
        source_opportunity_id=21,
        topic="Agent 项目避坑",
        angle="真实复盘",
        target_audience="27 届普通本科生",
        content_goal="说清工程误区",
        why_now="Research 样本出现相关疑问",
        evidence_refs=[EvidenceRef(kind="content_opportunity", id=21)],
        suggested_hook="别先堆 10 个 Agent",
        constraints=["不承诺求职结果"],
    )


def test_generate_review_and_revision_are_separate_capabilities_with_lineage():
    repo = FakeDraftRepository()
    client = FakeLLMClient([
        {"title": "Agent 项目别先堆框架", "body": "这是一篇初稿。", "tags": ["Agent"], "cta": "收藏复盘"},
        {
            "overall_status": "REVISE",
            "issues": [{"category": "STYLE", "severity": "MEDIUM", "location": "开头", "explanation": "语气偏硬", "suggestion": "更自然"}],
            "strategy_alignment": "对齐",
            "evidence_grounding": "未发现虚构研究事实",
            "cited_evidence_refs": [{"kind": "research_report", "id": 11}],
            "style_consistency": "需调整",
            "risk_findings": [],
            "revision_required": True,
            "summary": "调整开头语气",
        },
        {"title": "做 Agent 项目，先别急着堆框架", "body": "我做项目时也踩过这个坑。", "tags": ["Agent"], "cta": "收藏复盘", "applied_changes": ["调整开头语气"]},
        {"title": "做 Agent 项目，先别急着堆框架", "body": "我做项目时也踩过这个坑，第二步是先跑通链路。", "tags": ["Agent"], "cta": "收藏复盘", "applied_changes": ["补充第二步"]},
    ])
    generated = DraftGenerationService(None, client, repo).generate(DraftGenerationInput(
        account_id=7,
        strategy_ref="strategy:11:v1",
        opportunity=_opportunity(),
        research_artifact_ref=EvidenceRef(kind="research_report", id=11),
        evidence_refs=[EvidenceRef(kind="competitor_note", id=101)],
    ))
    original_body = repo.drafts[generated.draft_ref].body
    review = DraftReviewService(None, client, repo).review(DraftReviewInput(
        draft_ref=generated.draft_ref,
        account_id=7,
        strategy_ref=generated.strategy_ref,
        opportunity_ref=generated.opportunity_ref,
        evidence_refs=generated.evidence_refs,
    ))
    assert repo.drafts[generated.draft_ref].body == original_body

    v2 = DraftRevisionService(None, client, repo).revise(DraftRevisionInput(
        source_draft_ref=generated.draft_ref,
        account_id=7,
        revision_source="REVIEW_RESULT",
        review_result_ref=review.review_result_ref,
        preserved_constraints=["不承诺求职结果"],
    ))
    v3 = DraftRevisionService(None, client, repo).revise(DraftRevisionInput(
        source_draft_ref=v2.draft_ref,
        account_id=7,
        revision_source="USER_FEEDBACK",
        user_instruction="补充第二步",
    ))

    assert (v2.version, v2.parent_draft_ref) == (2, generated.draft_ref)
    assert (v3.version, v3.parent_draft_ref) == (3, v2.draft_ref)
    assert v2.opportunity_ref == v3.opportunity_ref == generated.opportunity_ref
    assert v2.strategy_ref == v3.strategy_ref == generated.strategy_ref
    assert [(item.version, item.parent_draft_ref) for item in repo.versions] == [(1, None), (2, 1), (3, 2)]


def test_exactly_one_owner_per_draft_capability_and_no_old_orchestration():
    expected = {
        "class DraftGenerationService": "services/draft_generation_sev.py",
        "class DraftReviewService": "services/draft_review_sev.py",
        "class DraftRevisionService": "services/draft_revision_sev.py",
    }
    for symbol, owner in expected.items():
        matches = [path.relative_to(APP_ROOT).as_posix() for path in APP_ROOT.rglob("*.py") if symbol in path.read_text(encoding="utf-8")]
        assert matches == [owner]
    forbidden = [
        "services/content_draft_v2_sev.py",
        "services/draft_revision_plan_sev.py",
        "services/draft_revision_apply_sev.py",
        "repositories/content_draft_v2_repo.py",
        "repositories/draft_revision_plan_repo.py",
    ]
    assert [path for path in forbidden if (APP_ROOT / path).exists()] == []


def test_draft_services_use_llm_client_without_research_or_provider_sdk():
    sources = "\n".join((APP_ROOT / "services" / name).read_text(encoding="utf-8") for name in (
        "draft_generation_sev.py", "draft_review_sev.py", "draft_revision_sev.py"
    ))
    assert "from app.llm.client import LLMClient" in sources
    for forbidden in ("app.llm.providers", "crawler", "xhs_collector", "competitor_note", "WriterAgent", "ReviewerAgent", "EditorAgent"):
        assert forbidden not in sources


def test_historical_draft_review_revision_models_remain():
    assert ContentDraft.__tablename__ == "content_draft"
    assert ContentDraftVersion.__tablename__ == "content_draft_version"
    assert ReviewReport.__tablename__ == "review_report"
    assert DraftRevisionPlan.__tablename__ == "draft_revision_plan"


def test_draft_revision_uses_task_specific_execution_policy(monkeypatch):
    monkeypatch.setattr("app.services.draft_revision_sev.settings.llm_draft_revision_model", "qwen3.8-flash")
    monkeypatch.setattr("app.services.draft_revision_sev.settings.llm_draft_revision_timeout_seconds", 120)
    monkeypatch.setattr("app.services.draft_revision_sev.settings.llm_draft_revision_enable_thinking", False)
    client = FakeLLMClient([{
        "title": "标题",
        "body": "更直接的开头。其余正文保持不变。",
        "tags": ["Agent"],
        "cta": "行动建议",
        "applied_changes": ["调整开头"],
    }])

    DraftRevisionService(None, client, FakeDraftRepository()).revise_semantic({"user_instruction": "调整开头"})

    call = client.calls[0]
    assert call["model"] == "qwen3.8-flash"
    assert call["timeout_seconds"] == 120
    assert call["extra_body"] == {"enable_thinking": False}
    assert call["prompt_version"] == DRAFT_REVISION_PROMPT_VERSION == "v2"
    assert "applied_changes" in call["system_prompt"]
    assert "非空" in call["system_prompt"]


def test_draft_review_uses_task_specific_structured_model(monkeypatch):
    monkeypatch.setattr("app.services.draft_review_sev.settings.llm_draft_review_model", "qwen3.7-flash-2026-07-15")
    client = FakeLLMClient([{
        "overall_status": "PASS",
        "issues": [],
        "strategy_alignment": "对齐",
        "evidence_grounding": "可追溯",
        "cited_evidence_refs": [],
        "style_consistency": "一致",
        "risk_findings": [],
        "revision_required": False,
        "summary": "通过",
    }])

    DraftReviewService(None, client, FakeDraftRepository()).review_semantic({"evidence_refs": []})

    call = client.calls[0]
    assert call["model"] == "qwen3.7-flash-2026-07-15"
    assert "extra_body" not in call
    assert call["timeout_seconds"] == 120
    assert call["prompt_version"] == DRAFT_REVIEW_PROMPT_VERSION == "v2"


def test_draft_revision_execution_policy_falls_back_to_global(monkeypatch):
    monkeypatch.setattr("app.services.draft_revision_sev.settings.llm_model", "global-strong")
    monkeypatch.setattr("app.services.draft_revision_sev.settings.llm_timeout_seconds", 30)
    monkeypatch.setattr("app.services.draft_revision_sev.settings.llm_draft_revision_model", None)
    monkeypatch.setattr("app.services.draft_revision_sev.settings.llm_draft_revision_timeout_seconds", None)
    monkeypatch.setattr("app.services.draft_revision_sev.settings.llm_draft_revision_enable_thinking", None)

    assert DraftRevisionService._execution_policy() == {
        "model": "global-strong",
        "timeout_seconds": 30,
    }


def test_draft_revision_applied_changes_is_required_and_non_empty():
    from pydantic import ValidationError
    from app.schemas.draft import DraftRevisionLLMResult

    valid = {"title": "标题", "body": "正文", "tags": [], "cta": None, "applied_changes": ["调整开头"]}
    assert DraftRevisionLLMResult.model_validate(valid).applied_changes == ["调整开头"]
    for invalid in (
        {"title": "标题", "body": "正文", "tags": [], "cta": None},
        {"title": "标题", "body": "正文", "tags": [], "cta": None, "applied_changes": []},
    ):
        try:
            DraftRevisionLLMResult.model_validate(invalid)
        except ValidationError:
            pass
        else:
            raise AssertionError("missing/empty applied_changes must fail")
