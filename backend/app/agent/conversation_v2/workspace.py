from pydantic import BaseModel, ConfigDict, Field

from app.agent.context.contracts import ObjectRef, ResolvedObjectType, StructuredContext
from app.agent.schemas.execution import ArtifactRef, ArtifactType
from app.repositories.content_strategy_repo import ContentStrategyRepository


class WorkspaceObjectSummary(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    kind: ResolvedObjectType
    ref: int
    summary: str


class TrustedWorkspaceSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid")

    research_ref: int | None = None
    strategy_ref: int | None = None
    opportunity_ref: int | None = None
    opportunity_strategy_ref: int | None = None
    draft_ref: int | None = None
    published_note_ref: int | None = None
    review_ref: int | None = None
    summaries: list[WorkspaceObjectSummary] = Field(default_factory=list)

    def prompt_text(self) -> str:
        if not self.summaries:
            return "本轮没有显式选择可信 workspace 对象。"
        return "可信 workspace（身份由服务器解析，禁止模型改写）：\n" + "\n".join(
            f"- {item.kind.value} #{item.ref}: {item.summary}" for item in self.summaries
        )


class RecentTrustedContext(BaseModel):
    model_config = ConfigDict(extra="forbid")

    research_ref: int | None = None
    strategy_ref: int | None = None
    opportunity_ref: int | None = None
    opportunity_strategy_ref: int | None = None
    draft_ref: int | None = None
    published_note_ref: int | None = None


_FIELD_BY_TYPE = {
    ResolvedObjectType.RESEARCH: "research_ref",
    ResolvedObjectType.CONTENT_STRATEGY: "strategy_ref",
    ResolvedObjectType.CONTENT_OPPORTUNITY: "opportunity_ref",
    ResolvedObjectType.DRAFT: "draft_ref",
    ResolvedObjectType.PUBLISHED_NOTE: "published_note_ref",
}


class TrustedWorkspaceBuilder:
    def __init__(self, db):
        self.strategies = ContentStrategyRepository(db)

    def build(self, selection: StructuredContext) -> TrustedWorkspaceSnapshot:
        values: dict[str, int] = {}
        summaries: list[WorkspaceObjectSummary] = []
        for trusted in selection.references:
            field = _FIELD_BY_TYPE.get(trusted.ref.type)
            if field is None or not isinstance(trusted.ref.id, int):
                continue
            values[field] = trusted.ref.id
            summaries.append(WorkspaceObjectSummary(kind=trusted.ref.type, ref=trusted.ref.id, summary="已通过账号归属校验"))
        if opportunity_ref := values.get("opportunity_ref"):
            opportunity = self.strategies.get_opportunity(opportunity_ref)
            if opportunity and opportunity.strategy_artifact_id:
                strategy = self.strategies.get_strategy_artifact(opportunity.strategy_artifact_id)
                opportunity_owner = next(
                    item.account_ref
                    for item in selection.references
                    if item.ref.type == ResolvedObjectType.CONTENT_OPPORTUNITY and item.ref.id == opportunity_ref
                )
                if strategy is not None and strategy.account_id == opportunity_owner:
                    values["opportunity_strategy_ref"] = strategy.id
                    summaries.append(WorkspaceObjectSummary(
                        kind=ResolvedObjectType.CONTENT_STRATEGY,
                        ref=strategy.id,
                        summary="由所选内容机会的持久化 lineage 推导",
                    ))
        return TrustedWorkspaceSnapshot(**values, summaries=summaries)

    def recent(self, context: StructuredContext) -> RecentTrustedContext:
        values: dict[str, int] = {}
        for trusted in context.references:
            field = _FIELD_BY_TYPE.get(trusted.ref.type)
            if field and isinstance(trusted.ref.id, int):
                values[field] = trusted.ref.id
        if context.review_refs:
            values["review_ref"] = context.review_refs[-1]
        if context.opportunity_collections:
            collection = context.opportunity_collections[-1]
            if collection.opportunity_refs:
                values["opportunity_ref"] = int(collection.opportunity_refs[0].ref.id)
                values["strategy_ref"] = int(collection.strategy_ref.ref.id)
                values["opportunity_strategy_ref"] = int(collection.strategy_ref.ref.id)
        return RecentTrustedContext(**values)


def artifact_for(kind: ResolvedObjectType, ref: int) -> ArtifactRef | None:
    mapping = {
        ResolvedObjectType.RESEARCH: ArtifactType.RESEARCH,
        ResolvedObjectType.CONTENT_STRATEGY: ArtifactType.CONTENT_STRATEGY,
        ResolvedObjectType.CONTENT_OPPORTUNITY: ArtifactType.CONTENT_OPPORTUNITY,
        ResolvedObjectType.DRAFT: ArtifactType.DRAFT,
        ResolvedObjectType.PUBLISHED_NOTE: ArtifactType.POST_PUBLISH_REVIEW,
    }
    artifact_type = mapping.get(kind)
    return ArtifactRef(type=artifact_type, id=ref) if artifact_type else None
