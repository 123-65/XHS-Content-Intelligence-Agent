from itertools import cycle

from sqlalchemy.orm import Session

from app.models.content_experiment import ContentExperiment
from app.models.content_opportunity import ContentOpportunity
from app.repositories.content_experiment_v2_repo import ContentExperimentV2Repository
from app.schemas.content_experiment_v2 import (
    ExperimentCardCreate,
    ExperimentCardResponse,
    ExperimentMetricTargetCreate,
    ExperimentMetricTargetResponse,
    ExperimentVariableCreate,
    ExperimentVariableResponse,
    GenerateExperimentsRequest,
)


PRIMARY_METRIC_BY_DEMAND = {
    "RESOURCE": "lead",
    "SOURCE_CODE": "lead",
    "CONSULTATION": "lead",
    "PRICE": "lead",
    "COURSE": "lead",
    "ROUTE": "collect",
    "PROJECT": "collect",
    "ANXIETY": "comment",
    "MARKETING_RESISTANCE": "comment",
    "UNKNOWN": "engagement",
}

EXPERIMENT_VARIANTS = (
    {"main_variable": "标题表达角度", "content_format": "图文笔记", "format_hint": "痛点标题 + 路线图"},
    {"main_variable": "封面信息密度", "content_format": "图文笔记", "format_hint": "强封面结论 + 步骤拆解"},
    {"main_variable": "CTA 引导方式", "content_format": "图文笔记", "format_hint": "软 CTA + 评论问题"},
    {"main_variable": "内容结构顺序", "content_format": "图文笔记", "format_hint": "问题-步骤-总结"},
    {"main_variable": "目标人群切口", "content_format": "图文笔记", "format_hint": "普通学生视角"},
)


class ContentExperimentV2Service:
    """V2 内容实验业务服务。"""

    def __init__(self, db: Session):
        """初始化 V2 内容实验服务。"""
        self.repo = ContentExperimentV2Repository(db)

    def generate_experiments(self, data: GenerateExperimentsRequest) -> list[ContentExperiment]:
        """从内容机会生成候选实验卡。"""
        account = self.repo.get_account(data.account_id)
        if not account:
            raise ValueError("账号配置不存在")
        if data.report_id is not None and not self.repo.get_report(data.report_id):
            raise ValueError("竞品分析报告不存在")

        recent_experiments = self.repo.list_recent_experiments(data.account_id)
        blocked_pillars = self._blocked_pillars(recent_experiments)
        opportunities = [
            opportunity
            for opportunity in self.repo.list_opportunities(data.account_id, data.report_id, data.limit)
            if opportunity.content_pillar not in blocked_pillars
        ]
        if not opportunities:
            raise ValueError("没有可用于生成实验的内容机会，或相关方向被内容组合约束暂时屏蔽")

        cards = self._build_cards(data, account, opportunities)
        return [self.repo.create_card(card) for card in cards]

    def get_experiment_card(self, experiment_id: int) -> ExperimentCardResponse:
        """查询实验卡详情。"""
        experiment = self._get_experiment_or_raise(experiment_id)
        return self._build_response(experiment)

    def list_experiment_cards(self, account_id: int | None = None) -> list[ExperimentCardResponse]:
        """查询实验卡列表。"""
        return [self._build_response(item) for item in self.repo.list_experiments(account_id)]

    def approve_experiment(self, experiment_id: int) -> ExperimentCardResponse:
        """审批候选实验。"""
        experiment = self._get_experiment_or_raise(experiment_id)
        if experiment.status != "CANDIDATE":
            raise ValueError("只有 CANDIDATE 状态的实验可以审批")
        return self._build_response(self.repo.approve(experiment))

    def _build_cards(self, data: GenerateExperimentsRequest, account, opportunities: list[ContentOpportunity]) -> list[ExperimentCardCreate]:
        """构建候选实验卡。"""
        opportunity_cycle = cycle(opportunities)
        variant_cycle = cycle(EXPERIMENT_VARIANTS)
        cards = []
        for _ in range(data.limit):
            opportunity = next(opportunity_cycle)
            variant = next(variant_cycle)
            cards.append(self._build_card(data.account_id, account, opportunity, variant))
        return cards

    def _build_card(self, account_id: int, account, opportunity: ContentOpportunity, variant: dict) -> ExperimentCardCreate:
        """根据内容机会构建单张实验卡。"""
        primary_metric = PRIMARY_METRIC_BY_DEMAND.get(opportunity.comment_demand_type, "engagement")
        secondary_metrics = self._secondary_metrics(primary_metric)
        target_values = self._target_values(primary_metric, opportunity.opportunity_score)
        cta_strength = "SOFT" if account.account_stage == "STARTUP" else "MEDIUM"
        success_criteria = self._success_criteria(primary_metric, target_values)
        failure_criteria = self._failure_criteria(primary_metric, target_values)
        control_variables = [
            {"name": "cta_strength", "value": cta_strength, "reason": "起号期不允许强 CTA" if cta_strength == "SOFT" else "非起号期允许中等 CTA"},
            {"name": "content_format", "value": variant["content_format"]},
            {"name": "target_audience", "value": opportunity.target_audience or account.target_audience},
        ]
        return ExperimentCardCreate(
            account_id=account_id,
            analysis_report_id=opportunity.report_id,
            content_opportunity_id=opportunity.id,
            experiment_name=f"{opportunity.content_pillar}实验：{opportunity.opportunity_title}",
            hypothesis=self._hypothesis(opportunity, primary_metric),
            content_pillar=opportunity.content_pillar,
            content_format=f"{variant['content_format']} - {variant['format_hint']}",
            main_variable=variant["main_variable"],
            control_variables=control_variables,
            primary_metric=primary_metric,
            secondary_metrics=secondary_metrics,
            success_criteria=success_criteria,
            failure_criteria=failure_criteria,
            fallback_strategy=self._fallback_strategy(opportunity),
            risk_level=opportunity.risk_level,
            target_metric=primary_metric,
            expected_result=self._expected_result(success_criteria),
            topic_angle=opportunity.suggested_angle,
            selected_topic=opportunity.opportunity_title,
            target_values=target_values,
            variables=self._variables(variant, control_variables),
            metric_targets=self._metric_targets(primary_metric, secondary_metrics, target_values),
        )

    def _blocked_pillars(self, recent_experiments: list[ContentExperiment]) -> set[str]:
        """计算暂不推荐的内容支柱。"""
        return self._same_recent_pillar(recent_experiments) | self._failed_pillars(recent_experiments)

    def _same_recent_pillar(self, recent_experiments: list[ContentExperiment]) -> set[str]:
        """连续三个实验不能都是同一内容支柱。"""
        recent_three = [item.content_pillar for item in recent_experiments[:3] if item.content_pillar]
        return {recent_three[0]} if len(recent_three) == 3 and len(set(recent_three)) == 1 else set()

    def _failed_pillars(self, recent_experiments: list[ContentExperiment]) -> set[str]:
        """连续失败方向暂不推荐。"""
        pillars = {item.content_pillar for item in recent_experiments if item.content_pillar}
        return {
            pillar
            for pillar in pillars
            if len([item for item in recent_experiments if item.content_pillar == pillar and item.status == "FAILED"][:2]) >= 2
        }

    def _hypothesis(self, opportunity: ContentOpportunity, primary_metric: str) -> str:
        """生成实验假设。"""
        return (
            f"如果围绕「{opportunity.suggested_angle}」设计{opportunity.content_pillar}内容，"
            f"并控制营销强度，可能提升 {primary_metric} 表现。证据：{opportunity.evidence_summary}"
        )

    def _secondary_metrics(self, primary_metric: str) -> list[str]:
        """生成辅助指标。"""
        candidates = ["collect", "comment", "lead", "engagement"]
        return [metric for metric in candidates if metric != primary_metric][:3]

    def _target_values(self, primary_metric: str, opportunity_score: int) -> dict:
        """根据机会分生成指标目标。"""
        base_value = max(20, opportunity_score)
        metric_key = {
            "collect": "collect_count",
            "comment": "comment_count",
            "lead": "lead_count",
            "engagement": "engagement_count",
        }.get(primary_metric, f"{primary_metric}_count")
        return {metric_key: base_value}

    def _success_criteria(self, primary_metric: str, target_values: dict) -> dict:
        """生成成功标准。"""
        return {"primary_metric": primary_metric, "target_values": target_values, "judgement": "发布后达到或超过主指标目标"}

    def _failure_criteria(self, primary_metric: str, target_values: dict) -> dict:
        """生成失败标准。"""
        return {"primary_metric": primary_metric, "target_values": target_values, "judgement": "发布后低于主指标目标的 60%"}

    def _fallback_strategy(self, opportunity: ContentOpportunity) -> str:
        """生成失败兜底策略。"""
        return f"如果实验失败，保留「{opportunity.content_pillar}」方向，但更换标题切口或降低营销表达，优先复测低风险变量。"

    def _expected_result(self, success_criteria: dict) -> str:
        """生成预期结果描述。"""
        values = success_criteria["target_values"]
        return "，".join(f"{key} >= {value}" for key, value in values.items())

    def _variables(self, variant: dict, control_variables: list[dict]) -> list[ExperimentVariableCreate]:
        """生成实验变量。"""
        return [
            ExperimentVariableCreate(
                variable_name=variant["main_variable"],
                variable_type="MAIN",
                variable_value={"format_hint": variant["format_hint"]},
                description="本次实验主要观察该变量对内容表现的影响。",
            ),
            *[
                ExperimentVariableCreate(
                    variable_name=item["name"],
                    variable_type="CONTROL",
                    variable_value={"value": item["value"]},
                    description=item.get("reason"),
                )
                for item in control_variables
            ],
        ]

    def _metric_targets(self, primary_metric: str, secondary_metrics: list[str], target_values: dict) -> list[ExperimentMetricTargetCreate]:
        """生成指标目标。"""
        primary_target = ExperimentMetricTargetCreate(
            metric_name=primary_metric,
            metric_type="PRIMARY",
            target_value=next(iter(target_values.values())),
            comparison_operator=">=",
            description="本次实验主目标指标。",
        )
        secondary_targets = [
            ExperimentMetricTargetCreate(
                metric_name=metric,
                metric_type="SECONDARY",
                target_value=0,
                comparison_operator=">=",
                description="辅助观察指标，不作为首轮成败唯一依据。",
            )
            for metric in secondary_metrics
        ]
        return [primary_target, *secondary_targets]

    def _get_experiment_or_raise(self, experiment_id: int) -> ContentExperiment:
        """查询内容实验，不存在时抛出业务错误。"""
        experiment = self.repo.get_experiment(experiment_id)
        if experiment:
            return experiment
        raise ValueError("内容实验不存在")

    def _build_response(self, experiment: ContentExperiment) -> ExperimentCardResponse:
        """构建带变量和指标目标的实验卡响应。"""
        variables = [
            ExperimentVariableResponse.model_validate(item)
            for item in self.repo.list_variables(experiment.id)
        ]
        metric_targets = [
            ExperimentMetricTargetResponse.model_validate(item)
            for item in self.repo.list_metric_targets(experiment.id)
        ]
        return ExperimentCardResponse.model_validate(
            {
                **experiment.__dict__,
                "variables": variables,
                "metric_targets": metric_targets,
            }
        )
