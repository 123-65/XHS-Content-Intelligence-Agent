from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class StrictModel(BaseModel):
    """拒绝未声明字段的分析基础模型。"""

    model_config = ConfigDict(extra="forbid")


class AccountEvidence(StrictModel):
    id: int
    nickname: str
    bio: str | None = None
    follower_count: int | None = None
    note_count: int | None = None
    source_type: str
    provider_name: str


class NoteEvidence(StrictModel):
    id: int
    competitor_account_id: int | None = None
    author_name: str | None = None
    title: str | None = None
    content: str | None = None
    tags: list[str] = Field(default_factory=list)
    like_count: int = 0
    collect_count: int = 0
    comment_count: int = 0
    note_url: str | None = None
    source_type: str
    provider_name: str
    ocr_texts: list[str] = Field(default_factory=list)


class CommentEvidence(StrictModel):
    id: int
    competitor_note_id: int
    content: str
    like_count: int = 0
    source_type: str
    provider_name: str


class NoteMetricEvidence(StrictModel):
    note_id: int
    like_count: int
    collect_count: int
    comment_count: int
    engagement_score: float


class ComputedMetrics(StrictModel):
    note_count: int
    comment_count: int
    account_count: int
    average_likes: float
    average_collects: float
    average_comments: float
    ranked_notes: list[NoteMetricEvidence] = Field(default_factory=list)


class CompetitorEvidence(StrictModel):
    account_id: int
    accounts: list[AccountEvidence]
    notes: list[NoteEvidence]
    comments: list[CommentEvidence]
    computed_metrics: ComputedMetrics
    used_account_ids: list[int]
    used_note_ids: list[int]
    used_comment_ids: list[int]
    ocr_note_ids: list[int]
    data_gaps: list[str] = Field(default_factory=list)


class EvidenceRef(StrictModel):
    source_type: Literal["ACCOUNT", "NOTE", "COMMENT", "METRIC", "OCR"]
    source_id: int
    detail: str | None = None


class PersonaAnalysis(StrictModel):
    positioning: str
    expertise: list[str]
    target_audience: list[str]
    value_proposition: str
    tone_and_style: list[str]
    confidence: float = Field(ge=0, le=1)
    evidence: list[EvidenceRef]


class ContentPillarAnalysis(StrictModel):
    name: str
    description: str
    evidence_note_ids: list[int]
    confidence: float = Field(ge=0, le=1)


class AudienceDemandAnalysis(StrictModel):
    demand: str
    user_intent: str
    representative_comment_ids: list[int]
    confidence: float = Field(ge=0, le=1)


class MetricEvidence(StrictModel):
    note_id: int
    metric: str
    value: float


class HighPerformingPatternAnalysis(StrictModel):
    pattern: str
    evidence_note_ids: list[int]
    metric_evidence: list[MetricEvidence]
    confidence: float = Field(ge=0, le=1)


class ContentStyleAnalysis(StrictModel):
    structure: list[str]
    tone: list[str]
    hooks: list[str]
    visual_patterns: list[str]
    evidence_note_ids: list[int]


class FollowRecommendationAnalysis(StrictModel):
    why_follow: str
    what_to_learn: list[str]
    what_not_to_copy: list[str]
    confidence: float = Field(ge=0, le=1)
    evidence: list[EvidenceRef]


class ContentOpportunityAnalysis(StrictModel):
    opportunity: str
    reason: str
    evidence_note_ids: list[int]
    evidence_comment_ids: list[int]
    confidence: float = Field(ge=0, le=1)


class ObservedSignal(StrictModel):
    name: str
    evidence: list[EvidenceRef]
    confidence: float = Field(ge=0, le=1)


class CompetitorSemanticResult(StrictModel):
    persona: PersonaAnalysis
    content_pillars: list[ContentPillarAnalysis]
    audience_demands: list[AudienceDemandAnalysis]
    high_performing_patterns: list[HighPerformingPatternAnalysis]
    content_style: ContentStyleAnalysis
    follow_recommendation: FollowRecommendationAnalysis
    content_opportunities: list[ContentOpportunityAnalysis]
    conversion_signals: list[ObservedSignal] = Field(default_factory=list)
    risk_points: list[ObservedSignal] = Field(default_factory=list)
    data_gaps: list[str] = Field(default_factory=list)
