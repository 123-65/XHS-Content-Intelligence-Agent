import json

from sqlalchemy.orm import Session

from app.core.config import settings
from app.llm.client import LLMClient
from app.llm.evidence import StructuredBusinessValidationError
from app.repositories.content_strategy_repo import ContentStrategyRepository
from app.schemas.content_strategy import (
    ContentStrategyRequest,
    ContentStrategyResult,
    GeneratedContentStrategy,
)
from app.services.opportunity_assembler import OpportunityAssembler


class ContentStrategyService:
    """Content Strategy 的唯一正式业务 Owner。"""

    def __init__(
        self,
        db: Session,
        llm_client: LLMClient | None = None,
        repository: ContentStrategyRepository | None = None,
        opportunity_assembler: OpportunityAssembler | None = None,
    ):
        """初始化内容策略服务。"""
        self.repo = repository or ContentStrategyRepository(db)
        self._llm_client = llm_client
        self.opportunity_assembler = opportunity_assembler or OpportunityAssembler()

    def generate(self, request: ContentStrategyRequest) -> ContentStrategyResult:
        """从现有 Research Artifact 生成兼容业务结果。"""
        account = self.repo.get_account(request.account_id)
        if not account:
            raise ValueError("账号配置不存在")
        report = self.repo.get_report(request.research_report_id)
        if not report:
            raise ValueError("Research Artifact 不存在")
        if report.account_id != request.account_id:
            raise ValueError("Research Artifact 不属于当前账号")
        if report.status != "SUCCESS":
            raise ValueError("Research Artifact 尚不可用于 Strategy")

        opportunities = self.repo.list_opportunities(report.id, request.max_opportunities)
        if not opportunities:
            raise ValueError("Research Artifact 没有可用的 Content Opportunity")

        allowed_refs = self._allowed_evidence_refs(report, opportunities)
        generated = self._generate_strategy(account, report, opportunities, request.additional_constraints)
        opportunity_by_id = {item.id: item for item in opportunities}
        unknown_ids = {item.source_opportunity_id for item in generated.opportunities} - set(opportunity_by_id)
        if unknown_ids:
            raise ValueError(f"Strategy 引用了未提供的 Content Opportunity: {sorted(unknown_ids)}")
        self._validate_evidence_refs(generated, allowed_refs)

        result_opportunities = [
            self.opportunity_assembler.assemble(
                item,
                opportunity_by_id[item.source_opportunity_id],
                generated.target_audience,
                generated.applicable_constraints,
            )
            for item in generated.opportunities
        ]
        client = self._client()
        return ContentStrategyResult(
            account_id=account.id,
            research_report_id=report.id,
            strategy_goal=generated.strategy_goal,
            target_audience=generated.target_audience,
            content_directions=generated.content_directions,
            rationale=generated.rationale,
            evidence_refs=generated.evidence_refs,
            applicable_constraints=generated.applicable_constraints,
            opportunities=result_opportunities,
            provider=client.provider,
            model=client.model,
        )

    def generate_semantic(self, payload: dict) -> GeneratedContentStrategy:
        """对 Workflow 已准备的上下文执行纯语义策略生成，不访问 Repository。"""
        result = self._client().generate_structured(
            prompt="请基于以下已授权 Research 事实生成 Content Strategy，不得输出预测指标。\n" + json.dumps(payload, ensure_ascii=False),
            schema_model=GeneratedContentStrategy,
            system_prompt="Research 是事实，Strategy 是建议。不得预测爆款概率、点赞、成交或收入，不得创造 EvidenceRef。",
            prompt_key="content_strategy_semantic",
            prompt_version="v1",
            timeout_seconds=settings.llm_content_strategy_timeout_seconds,
        )
        strategy = GeneratedContentStrategy.model_validate(result.data)
        allowed = self._allowed_semantic_evidence_refs(payload)
        try:
            self._validate_evidence_refs(strategy, allowed)
        except ValueError as exc:
            self._client().record_business_validation_failure(
                exc,
                strategy.model_dump(mode="json"),
                validation_layer="POST_PARSE_BUSINESS_VALIDATION",
            )
            raise
        return strategy

    @staticmethod
    def _allowed_semantic_evidence_refs(payload: dict) -> set[tuple[str, int]]:
        """Authorize only evidence identities actually present in the trusted Strategy input."""
        allowed = {(item["kind"], item["id"]) for item in payload.get("evidence_refs", [])}
        for item in payload.get("historical_opportunities", []):
            opportunity_id = item.get("source_opportunity_id") if isinstance(item, dict) else None
            if isinstance(opportunity_id, int) and not isinstance(opportunity_id, bool) and opportunity_id > 0:
                allowed.add(("content_opportunity", opportunity_id))
        return allowed

    def _generate_strategy(self, account, report, opportunities, additional_constraints: list[str]) -> GeneratedContentStrategy:
        """调用统一 LLM 生成兼容业务策略。"""
        result = self._client().generate_structured(
            prompt=self._prompt(account, report, opportunities, additional_constraints),
            schema_model=GeneratedContentStrategy,
            system_prompt=(
                "你是内容策略服务。只能根据提供的账号上下文和 Research Evidence 给出建议；"
                "事实与建议必须分开，不得预测爆款概率、点赞数、成交数，不得创造 evidence ref。"
            ),
            prompt_key="content_strategy",
            prompt_version="v1",
            timeout_seconds=settings.llm_content_strategy_timeout_seconds,
        )
        return GeneratedContentStrategy.model_validate(result.data)

    def _client(self) -> LLMClient:
        """延迟创建统一 LLMClient。"""
        if self._llm_client is None:
            self._llm_client = LLMClient()
        return self._llm_client

    def _allowed_evidence_refs(self, report, opportunities) -> set[tuple[str, int]]:
        """计算当前策略允许引用的事实集合。"""
        refs = {("research_report", report.id)}
        refs.update(("competitor_note", int(note_id)) for note_id in report.competitor_note_ids or [])
        refs.update(("content_opportunity", item.id) for item in opportunities)
        return refs

    def _validate_evidence_refs(self, strategy: GeneratedContentStrategy, allowed: set[tuple[str, int]]) -> None:
        """拒绝策略输出创造未提供的 EvidenceRef。"""
        located = [(f"evidence_refs.{index}", ref) for index, ref in enumerate(strategy.evidence_refs)]
        located.extend(
            (f"content_directions.{direction_index}.evidence_refs.{ref_index}", ref)
            for direction_index, direction in enumerate(strategy.content_directions)
            for ref_index, ref in enumerate(direction.evidence_refs)
        )
        located.extend(
            (f"opportunities.{opportunity_index}.evidence_refs.{ref_index}", ref)
            for opportunity_index, opportunity in enumerate(strategy.opportunities)
            for ref_index, ref in enumerate(opportunity.evidence_refs)
        )
        for path, ref in located:
            if (ref.kind, ref.id) not in allowed:
                raise StructuredBusinessValidationError(
                    f"Strategy 包含无效 EvidenceRefs: {[(ref.kind, ref.id)]}",
                    validation_path=path,
                    expected="EvidenceRef 必须属于本次输入的 authorized evidence_refs",
                    actual_value=ref.model_dump(mode="json"),
                )

    def _prompt(self, account, report, opportunities, additional_constraints: list[str]) -> str:
        """构造兼容业务入口的策略提示。"""
        payload = {
            "growth_context": {
                "account_id": account.id,
                "positioning": account.positioning,
                "target_audience": account.target_audience,
                "content_domain": account.content_domain,
                "primary_goal": account.primary_goal,
                "business_model": account.business_model,
                "main_product": account.main_product,
                "tone_preference": account.tone_preference,
                "account_stage": account.account_stage,
            },
            "research_artifact": {
                "evidence_ref": {"kind": "research_report", "id": report.id},
                "summary": report.summary,
                "content_insights": report.content_insights,
                "comment_demands": report.comment_demands,
                "risk_points": report.risk_points,
                "competitor_note_refs": [
                    {"kind": "competitor_note", "id": int(note_id)} for note_id in report.competitor_note_ids or []
                ],
            },
            "available_opportunities": [
                {
                    "source_opportunity_id": item.id,
                    "evidence_ref": {"kind": "content_opportunity", "id": item.id},
                    "topic": item.opportunity_title,
                    "angle": item.suggested_angle,
                    "target_audience": item.target_audience,
                    "content_pillar": item.content_pillar,
                    "evidence_summary": item.evidence_summary,
                    "risk_points": item.risk_points,
                }
                for item in opportunities
            ],
            "additional_constraints": additional_constraints,
        }
        return "请生成 Content Strategy V1 结构化结果。\n" + json.dumps(payload, ensure_ascii=False)
