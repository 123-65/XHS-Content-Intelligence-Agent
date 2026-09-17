from app.analysis.competitor.schemas import (
    AccountEvidence,
    AudienceDemandAnalysis,
    CommentEvidence,
    CompetitorEvidence,
    CompetitorSemanticResult,
    ComputedMetrics,
    ContentOpportunityAnalysis,
    ContentPillarAnalysis,
    ContentStyleAnalysis,
    EvidenceRef,
    FollowRecommendationAnalysis,
    HighPerformingPatternAnalysis,
    MetricEvidence,
    NoteEvidence,
    NoteMetricEvidence,
    PersonaAnalysis,
)
from app.schemas.llm import LLMStructuredResult, LLMUsage
from app.analysis.competitor.rule_baseline import RuleBaselineCompetitorAnalyzer


def make_evidence() -> CompetitorEvidence:
    return CompetitorEvidence(
        account_id=1,
        accounts=[
            AccountEvidence(
                id=11,
                nickname="FDE 现场手册",
                bio="企业 AI 落地与交付方法",
                follower_count=12000,
                source_type="XHS_MCP",
                provider_name="xiaohongshu_mcp",
            )
        ],
        notes=[
            NoteEvidence(
                id=21,
                competitor_account_id=11,
                title="企业 AI 项目如何落地",
                content="项目交付复盘",
                like_count=100,
                collect_count=80,
                comment_count=10,
                source_type="XHS_MCP",
                provider_name="xiaohongshu_mcp",
            )
        ],
        comments=[
            CommentEvidence(
                id=31,
                competitor_note_id=21,
                content="想了解交付阶段的常见问题",
                like_count=2,
                source_type="XHS_MCP",
                provider_name="xiaohongshu_mcp",
            )
        ],
        computed_metrics=ComputedMetrics(
            note_count=1,
            comment_count=1,
            account_count=1,
            average_likes=100,
            average_collects=80,
            average_comments=10,
            ranked_notes=[
                NoteMetricEvidence(
                    note_id=21,
                    like_count=100,
                    collect_count=80,
                    comment_count=10,
                    engagement_score=240,
                )
            ],
        ),
        used_account_ids=[11],
        used_note_ids=[21],
        used_comment_ids=[31],
        ocr_note_ids=[],
        data_gaps=["没有可用的 OCR 文本，无法分析图片内容"],
    )


def make_semantic(note_id: int = 21, comment_id: int = 31) -> CompetitorSemanticResult:
    return CompetitorSemanticResult(
        persona=PersonaAnalysis(
            positioning="企业 AI 落地与交付知识账号",
            expertise=["FDE", "企业 AI 交付"],
            target_audience=["企业 AI 实施人员"],
            value_proposition="提供真实交付方法与案例复盘",
            tone_and_style=["专业", "务实"],
            confidence=0.9,
            evidence=[EvidenceRef(source_type="ACCOUNT", source_id=11)],
        ),
        content_pillars=[
            ContentPillarAnalysis(
                name="企业 AI 交付",
                description="围绕项目落地和交付复盘",
                evidence_note_ids=[note_id],
                confidence=0.88,
            )
        ],
        audience_demands=[
            AudienceDemandAnalysis(
                demand="交付问题排查",
                user_intent="寻找项目实施中的问题处理方法",
                representative_comment_ids=[comment_id],
                confidence=0.82,
            )
        ],
        high_performing_patterns=[
            HighPerformingPatternAnalysis(
                pattern="真实项目复盘",
                evidence_note_ids=[note_id],
                metric_evidence=[MetricEvidence(note_id=note_id, metric="engagement_score", value=240)],
                confidence=0.8,
            )
        ],
        content_style=ContentStyleAnalysis(
            structure=["问题-方法-复盘"],
            tone=["专业", "克制"],
            hooks=["具体交付问题"],
            visual_patterns=[],
            evidence_note_ids=[note_id],
        ),
        follow_recommendation=FollowRecommendationAnalysis(
            why_follow="持续提供企业 AI 项目的一线交付经验",
            what_to_learn=["问题拆解方式"],
            what_not_to_copy=["未经验证的案例结论"],
            confidence=0.86,
            evidence=[EvidenceRef(source_type="NOTE", source_id=note_id)],
        ),
        content_opportunities=[
            ContentOpportunityAnalysis(
                opportunity="企业 AI 交付故障手册",
                reason="笔记和评论同时出现交付问题证据",
                evidence_note_ids=[note_id],
                evidence_comment_ids=[comment_id],
                confidence=0.83,
            )
        ],
        data_gaps=["缺少 OCR 文本"],
    )


class FakeCompetitorLLMClient:
    def __init__(self, semantic: CompetitorSemanticResult | None = None):
        self.semantic = semantic or make_semantic()
        self.calls = []

    def generate_structured(self, prompt, schema_model, system_prompt=None, **kwargs):
        self.calls.append(
            {
                "prompt": prompt,
                "schema_model": schema_model,
                "system_prompt": system_prompt,
                **kwargs,
            }
        )
        return LLMStructuredResult(
            data=self.semantic,
            text=self.semantic.model_dump_json(),
            model="fake-test-model",
            provider="fake-test-provider",
            usage=LLMUsage(),
            is_mock=True,
        )


class FakeStructuredCompetitorAnalyzer:
    """供工作流测试注入的结构化分析 Fake。"""

    analysis_engine = "LLM_STRUCTURED_V1"

    def analyze(self, evidence):
        return RuleBaselineCompetitorAnalyzer().analyze(evidence)
