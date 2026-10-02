from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class StrictStrategyModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class EvidenceRef(StrictStrategyModel):
    kind: Literal[
        "research_report",
        "competitor_note",
        "content_opportunity",
        "published_note",
        "public_metric_snapshot",
        "private_metric_snapshot",
        "post_publish_review",
    ]
    id: int = Field(gt=0)


class ContentDirection(StrictStrategyModel):
    direction: str = Field(min_length=1)
    rationale: str = Field(min_length=1)
    evidence_refs: list[EvidenceRef] = Field(min_length=1)


class GeneratedOpportunity(StrictStrategyModel):
    source_opportunity_id: int = Field(gt=0)
    content_goal: str = Field(min_length=1)
    why_now: str = Field(min_length=1)
    suggested_hook: str = Field(min_length=1)
    evidence_refs: list[EvidenceRef] = Field(min_length=1)
    constraints: list[str] = Field(default_factory=list)


class GeneratedContentStrategy(StrictStrategyModel):
    strategy_goal: str = Field(min_length=1)
    target_audience: str = Field(min_length=1)
    content_directions: list[ContentDirection] = Field(min_length=1)
    rationale: str = Field(min_length=1)
    evidence_refs: list[EvidenceRef] = Field(min_length=1)
    applicable_constraints: list[str] = Field(default_factory=list)
    opportunities: list[GeneratedOpportunity] = Field(min_length=1)


class ContentStrategyRequest(StrictStrategyModel):
    account_id: int = Field(gt=0)
    research_report_id: int = Field(gt=0)
    max_opportunities: int = Field(default=3, ge=1, le=10)
    additional_constraints: list[str] = Field(default_factory=list)


class ContentOpportunityResult(StrictStrategyModel):
    source_opportunity_id: int
    topic: str
    angle: str
    target_audience: str
    content_goal: str
    why_now: str
    evidence_refs: list[EvidenceRef]
    suggested_hook: str
    constraints: list[str] = Field(default_factory=list)


class ContentStrategyResult(StrictStrategyModel):
    account_id: int
    research_report_id: int
    strategy_goal: str
    target_audience: str
    content_directions: list[ContentDirection]
    rationale: str
    evidence_refs: list[EvidenceRef]
    applicable_constraints: list[str]
    opportunities: list[ContentOpportunityResult]
    provider: str
    model: str
