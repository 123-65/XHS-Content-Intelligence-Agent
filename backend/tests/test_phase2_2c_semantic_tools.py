from datetime import datetime, timezone
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.agent.tools.definitions import ToolEffect, ToolName
from app.agent.tools.execution_context import ToolExecutionContext
from app.agent.tools.implementation_registry import TOOL_HANDLER_REGISTRY, build_tool_handler
from app.agent.tools.registry import TOOL_REGISTRY
from app.agent.tools.semantic_contracts import (
    AnalyzePostPublishReviewInput,
    AnalyzeResearchInput,
    GenerateContentStrategyInput,
    GenerateDraftInput,
    ReviewDraftInput,
    ReviseDraftInput,
)
from app.agent.tools.semantic_tools import (
    AnalyzePostPublishReviewTool,
    AnalyzeResearchTool,
    GenerateContentStrategyTool,
    GenerateDraftTool,
    ReviewDraftTool,
    ReviseDraftTool,
)


BACKEND_ROOT = Path(__file__).resolve().parents[1]
SEMANTIC_TOOL_NAMES = {
    ToolName.ANALYZE_RESEARCH,
    ToolName.GENERATE_CONTENT_STRATEGY,
    ToolName.GENERATE_DRAFT,
    ToolName.REVIEW_DRAFT,
    ToolName.REVISE_DRAFT,
    ToolName.ANALYZE_POST_PUBLISH_REVIEW,
}


def _competitor_evidence() -> dict:
    """构造最小且可追溯的竞品研究证据。"""
    return {
        "account_id": 1,
        "accounts": [],
        "notes": [],
        "comments": [],
        "computed_metrics": {"note_count": 0, "comment_count": 0, "account_count": 0, "average_likes": 0, "average_collects": 0, "average_comments": 0, "ranked_notes": []},
        "used_account_ids": [],
        "used_note_ids": [],
        "used_comment_ids": [],
        "ocr_note_ids": [],
        "data_gaps": ["样本较少"],
    }


def _research_result() -> dict:
    """构造通过结构化校验的研究语义结果。"""
    return {
        "persona": {"positioning": "实用教程", "expertise": [], "target_audience": ["新手"], "value_proposition": "降低门槛", "tone_and_style": ["清晰"], "confidence": 0.7, "evidence": []},
        "content_pillars": [], "audience_demands": [], "high_performing_patterns": [],
        "content_style": {"structure": [], "tone": [], "hooks": [], "visual_patterns": [], "evidence_note_ids": []},
        "follow_recommendation": {"why_follow": "持续观察", "what_to_learn": [], "what_not_to_copy": [], "confidence": 0.5, "evidence": []},
        "content_opportunities": [], "conversion_signals": [], "risk_points": [], "data_gaps": ["样本较少"],
    }


def _evidence_bundle() -> dict:
    """构造带来源关系的 Tool 证据集合。"""
    return {"purpose": "生成内容", "truncated": False, "items": [{"evidence_ref": {"type": "NOTE", "id": 11}, "evidence_type": "NOTE", "content": "观察到的事实", "structured_facts": {}, "provenance": "DB", "source_ref": "note:11"}]}


def _opportunity() -> dict:
    """构造与策略绑定的内容机会。"""
    return {"source_opportunity_id": 7, "topic": "主题", "angle": "角度", "target_audience": "新手", "content_goal": "帮助理解", "why_now": "需求明确", "evidence_refs": [{"kind": "competitor_note", "id": 11}], "suggested_hook": "三步学会", "constraints": []}


def _draft() -> dict:
    """构造未持久化且身份完整的 Draft。"""
    return {"title": "标题", "body": "正文", "tags": ["教程"], "cta": None, "strategy_ref": "strategy:3", "opportunity_ref": 7, "content_goal": "帮助理解"}


def _review_result() -> dict:
    """构造不会直接修改 Draft 的评审结果。"""
    return {"overall_status": "PASS", "issues": [], "strategy_alignment": "一致", "evidence_grounding": "可追溯", "cited_evidence_refs": [{"kind": "competitor_note", "id": 11}], "style_consistency": "一致", "risk_findings": [], "revision_required": False, "summary": "通过"}


class FakeSemanticOwner:
    """按测试场景返回 Canonical Owner 的结构化结果。"""

    def __init__(self, result=None, error=None):
        """保存预期结果或异常。"""
        self.result = result
        self.error = error
        self.calls = []

    def generate_semantic(self, payload):
        """模拟策略或 Draft 纯语义入口。"""
        return self._respond(payload)

    def review_semantic(self, payload):
        """模拟 Review 纯语义入口。"""
        return self._respond(payload)

    def revise_semantic(self, payload):
        """模拟 Revision 纯语义入口。"""
        return self._respond(payload)

    def analyze(self, payload):
        """模拟结构化竞品分析入口。"""
        return self._respond(payload)

    def _respond(self, payload):
        """记录调用并执行预置响应。"""
        self.calls.append(payload)
        if self.error:
            raise self.error
        return self.result


def _strategy_input() -> GenerateContentStrategyInput:
    """构造策略 Tool 的有效输入。"""
    return GenerateContentStrategyInput(account_ref=1, growth_context={}, research_result=_research_result(), evidence_refs=[{"kind": "competitor_note", "id": 11}])


def _strategy_result() -> dict:
    """构造不含预测字段的策略语义结果。"""
    ref = {"kind": "competitor_note", "id": 11}
    return {"strategy_goal": "教育用户", "target_audience": "新手", "content_directions": [{"direction": "教程", "rationale": "有事实依据", "evidence_refs": [ref]}], "rationale": "基于研究", "evidence_refs": [ref], "applicable_constraints": [], "opportunities": [{"source_opportunity_id": 7, "content_goal": "帮助理解", "why_now": "需求明确", "suggested_hook": "三步学会", "evidence_refs": [ref], "constraints": []}]}


def _metrics(public=True) -> dict:
    """构造保留私域 UNKNOWN 语义的发布指标。"""
    return {"published_note_ref": 9, "public_metrics_status": "AVAILABLE" if public else "UNKNOWN", "public_metrics": {"likes": {"value": 10, "provenance": "MEASURED"}} if public else {}, "private_metrics": None, "window": {"start": datetime(2026, 1, 1, tzinfo=timezone.utc), "end": datetime(2026, 1, 2, tzinfo=timezone.utc)}, "provenance": ["MEASURED"] if public else [], "missing_metrics": ["private_metrics", *([] if public else ["public_metrics"])]}


def test_registry_includes_six_pure_semantic_tools_in_final_handler_closure():
    """确认六个 Semantic Tool 保持 PURE，且最终 Tool Layer 已完整闭合。"""
    assert len(TOOL_REGISTRY) == 17
    assert len(TOOL_HANDLER_REGISTRY) == 17
    assert all(TOOL_REGISTRY[name].effect is ToolEffect.PURE for name in SEMANTIC_TOOL_NAMES)
    with pytest.raises(ValueError, match="缺少可信数据库会话"):
        build_tool_handler(ToolName.CREATE_DRAFT_VERSION, ToolExecutionContext(db=None))


def test_six_semantic_tools_return_typed_success_without_persistence():
    """验证六个 Tool 只返回语义结果，并保持 Draft 不可变身份。"""
    research = AnalyzeResearchTool(FakeSemanticOwner(_research_result())).execute(AnalyzeResearchInput(account_ref=1, growth_context={}, evidence_bundle=_competitor_evidence(), research_goal="分析"))
    strategy = GenerateContentStrategyTool(FakeSemanticOwner(_strategy_result())).execute(_strategy_input())
    draft = GenerateDraftTool(FakeSemanticOwner({"title": "标题", "body": "正文", "tags": [], "cta": None})).execute(GenerateDraftInput(account_context={}, strategy={"strategy_ref": "strategy:3"}, strategy_ref="strategy:3", opportunity=_opportunity(), evidence_bundle=_evidence_bundle()))
    review = ReviewDraftTool(FakeSemanticOwner(_review_result())).execute(ReviewDraftInput(draft=_draft(), strategy={}, opportunity=_opportunity(), evidence_bundle=_evidence_bundle(), account_context={}))
    revised = ReviseDraftTool(FakeSemanticOwner({"title": "新标题", "body": "新正文", "tags": [], "cta": None, "applied_changes": ["精简"]})).execute(ReviseDraftInput(source_draft=_draft(), revision_source="USER_FEEDBACK", user_instruction="精简", evidence_bundle=_evidence_bundle()))
    post = AnalyzePostPublishReviewTool(FakeSemanticOwner({"observed_results": ["点赞 10"], "public_performance_analysis": "已观察", "optional_conversion_analysis": None, "strategy_alignment": "待观察", "what_worked": [], "what_did_not_work": [], "uncertainties": ["私域未知"], "evidence_refs": [{"kind": "published_note", "id": 9}], "strategy_candidates": [{"candidate_index": 0, "statement": "继续测试", "scope": "教程", "supporting_refs": [{"kind": "published_note", "id": 9}], "contradicting_refs": [], "confidence_context": "样本少", "status": "PROPOSED"}]})).execute(AnalyzePostPublishReviewInput(published_note={}, published_draft=_draft(), content_strategy={}, opportunity=_opportunity(), metrics=_metrics(), grounding_refs=[{"kind": "published_note", "id": 9}]))
    results = (research, strategy, draft, review, revised, post)
    assert all(item.success and item.error is None for item in results), [item.model_dump() for item in results]
    assert (draft.data.strategy_ref, draft.data.opportunity_ref, draft.data.content_goal) == ("strategy:3", 7, "帮助理解")
    assert (revised.data.strategy_ref, revised.data.opportunity_ref, revised.data.content_goal) == ("strategy:3", 7, "帮助理解")
    assert post.data.optional_conversion_analysis is None


def test_post_publish_review_tool_propagates_only_explicit_grounding_refs():
    owner = FakeSemanticOwner({"observed_results": [], "public_performance_analysis": "公开未知", "optional_conversion_analysis": None, "strategy_alignment": "待观察", "what_worked": [], "what_did_not_work": [], "uncertainties": [], "evidence_refs": [], "strategy_candidates": []})
    refs = [{"kind": "published_note", "id": 9}, {"kind": "private_metric_snapshot", "id": 51}]

    result = AnalyzePostPublishReviewTool(owner).execute(AnalyzePostPublishReviewInput(
        published_note={}, published_draft=_draft(), content_strategy={},
        opportunity=_opportunity(), metrics=_metrics(False), grounding_refs=refs,
    ))

    assert result.success is True
    assert owner.calls[0]["evidence_refs"] == refs


def test_review_draft_exposes_verified_grounding_and_retrieved_note_refs():
    """Review may cite verified lineage refs, while its authorized set remains explicit."""
    owner = FakeSemanticOwner({
        **_review_result(),
        "cited_evidence_refs": [
            {"kind": "research_report", "id": 13},
            {"kind": "content_opportunity", "id": 17},
            {"kind": "competitor_note", "id": 11},
        ],
    })
    result = ReviewDraftTool(owner).execute(ReviewDraftInput(
        draft=_draft(),
        strategy={},
        opportunity=_opportunity(),
        evidence_bundle=_evidence_bundle(),
        grounding_refs=[
            {"kind": "research_report", "id": 13},
            {"kind": "content_opportunity", "id": 17},
        ],
        account_context={},
    ))

    assert result.success
    assert owner.calls[0]["evidence_refs"] == [
        {"kind": "research_report", "id": 13},
        {"kind": "content_opportunity", "id": 17},
        {"kind": "competitor_note", "id": 11},
    ]
    assert "grounding_refs" not in owner.calls[0]


def test_semantic_failures_have_no_partial_data_and_contracts_reject_bad_inputs():
    """验证 Grounding、身份、证据和复盘事实失败时不伪造成功。"""
    failed = AnalyzeResearchTool(FakeSemanticOwner(error=ValueError("grounding failed"))).execute(AnalyzeResearchInput(account_ref=1, growth_context={}, evidence_bundle=_competitor_evidence(), research_goal="分析"))
    mismatch = GenerateDraftTool(FakeSemanticOwner({})).execute(GenerateDraftInput(account_context={}, strategy={"strategy_ref": "strategy:other"}, strategy_ref="strategy:3", opportunity=_opportunity(), evidence_bundle=_evidence_bundle()))
    assert not failed.success and failed.data is None and failed.error
    assert not mismatch.success and mismatch.data is None and mismatch.error.code == "VALIDATION_ERROR"
    with pytest.raises(ValidationError):
        GenerateDraftInput(account_context={}, strategy={}, strategy_ref="strategy:3", opportunity=_opportunity(), evidence_bundle={"items": [], "purpose": "x"})
    with pytest.raises(ValidationError):
        ReviseDraftInput(source_draft=_draft(), revision_source="USER_FEEDBACK", evidence_bundle=_evidence_bundle())
    partial = AnalyzePostPublishReviewInput(published_note={}, published_draft={}, content_strategy={}, opportunity={}, metrics=_metrics(False))
    assert partial.metrics.public_metrics_status == "UNKNOWN"
    assert partial.metrics.public_metrics == {}
    with pytest.raises(ValidationError):
        AnalyzePostPublishReviewInput(published_note={}, published_draft={}, content_strategy={}, opportunity={}, metrics={**_metrics(False), "public_metrics_status": "AVAILABLE"})


def test_semantic_tool_boundary_has_no_forbidden_runtime_dependencies():
    """保护 Tool 层不直接访问 LLM、Repository、Provider、DB、Workflow 或持久化。"""
    source = (BACKEND_ROOT / "app" / "agent" / "tools" / "semantic_tools.py").read_text(encoding="utf-8")
    forbidden = ("app.llm", "app.repositories", "app.crawler", "sqlalchemy", "fastapi", "HTTPException", "app.agent.workflows", ".commit(", ".add(", "create_artifact")
    assert not [token for token in forbidden if token in source]
    for owner in ("LLMStructuredCompetitorAnalyzer", "ContentStrategyService", "DraftGenerationService", "DraftReviewService", "DraftRevisionService", "PostPublishReviewService"):
        assert owner in source


@pytest.mark.parametrize(
    ("relative_path", "method_name"),
    [
        ("app/services/content_strategy_sev.py", "generate_semantic"),
        ("app/services/draft_generation_sev.py", "generate_semantic"),
        ("app/services/draft_review_sev.py", "review_semantic"),
        ("app/services/draft_revision_sev.py", "revise_semantic"),
        ("app/services/post_publish_review_v0_sev.py", "review_semantic"),
    ],
)
def test_canonical_semantic_entrypoints_do_not_use_repository(relative_path, method_name):
    """保护 Canonical Owner 的语义入口不读写 Repository。"""
    import ast

    tree = ast.parse((BACKEND_ROOT / relative_path).read_text(encoding="utf-8"))
    method = next(node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef) and node.name == method_name)
    method_source = ast.unparse(method)
    assert "self.repo" not in method_source
    assert ".commit(" not in method_source
    assert "create_" not in method_source
