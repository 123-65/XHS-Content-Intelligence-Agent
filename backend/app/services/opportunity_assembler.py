from app.models.content_opportunity import ContentOpportunity
from app.schemas.content_strategy import ContentOpportunityResult, GeneratedOpportunity


class OpportunityAssembler:
    """将已有 Research Opportunity 与 Strategy 建议组装为正式 Content Opportunity。"""

    def assemble(
        self,
        generated: GeneratedOpportunity,
        source: ContentOpportunity,
        default_audience: str,
        strategy_constraints: list[str],
    ) -> ContentOpportunityResult:
        constraints = list(dict.fromkeys([*strategy_constraints, *generated.constraints, *(source.risk_points or [])]))
        return ContentOpportunityResult(
            source_opportunity_id=source.id,
            topic=source.opportunity_title,
            angle=source.suggested_angle,
            target_audience=source.target_audience or default_audience,
            content_goal=generated.content_goal,
            why_now=generated.why_now,
            evidence_refs=generated.evidence_refs,
            suggested_hook=generated.suggested_hook,
            constraints=constraints,
        )

