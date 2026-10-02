from app.agent.schemas.evidence import EvidenceRef, EvidenceType
from app.agent.tools.query_contracts import ContentOpportunityArtifactView
from app.schemas.content_strategy import EvidenceRef as StrategyEvidenceRef


def partition_opportunity_evidence(
    opportunity: ContentOpportunityArtifactView,
) -> tuple[list[StrategyEvidenceRef], list[EvidenceRef]]:
    """Split broad Strategy refs from canonical Research evidence refs."""
    grounding: list[StrategyEvidenceRef] = []
    projected = list(dict.fromkeys(opportunity.retrievable_evidence_refs))
    projected_set = frozenset(projected)
    retrieval_mapping = {"competitor_note": EvidenceType.NOTE}
    for ref in opportunity.opportunity.evidence_refs:
        if ref.kind == "research_report":
            if ref.id != opportunity.research_artifact_ref:
                raise ValueError("Opportunity 引用了其他 Research Artifact。")
            grounding.append(ref)
        elif ref.kind == "content_opportunity":
            if ref.id != opportunity.source_opportunity_ref:
                raise ValueError("Opportunity 引用了其他 Source Opportunity。")
            grounding.append(ref)
        elif ref.kind in retrieval_mapping:
            retrieval_ref = EvidenceRef(type=retrieval_mapping[ref.kind], id=ref.id)
            if retrieval_ref not in projected_set:
                raise ValueError("Opportunity 引用了当前 Research 之外的事实 Evidence。")
        else:
            raise ValueError(f"Opportunity Evidence 类型未定义分类: {ref.kind}")
    if not projected:
        raise ValueError("Research Artifact 没有可检索的事实 Evidence。")
    unique_grounding = {(ref.kind, ref.id): ref for ref in grounding}
    return list(unique_grounding.values()), projected


__all__ = ["partition_opportunity_evidence"]
