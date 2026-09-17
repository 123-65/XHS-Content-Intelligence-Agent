import re
from collections import Counter

from app.analysis.competitor.schemas import (
    AudienceDemandAnalysis,
    CompetitorEvidence,
    CompetitorSemanticResult,
    ContentOpportunityAnalysis,
    ContentPillarAnalysis,
    ContentStyleAnalysis,
    EvidenceRef,
    FollowRecommendationAnalysis,
    HighPerformingPatternAnalysis,
    MetricEvidence,
    ObservedSignal,
    PersonaAnalysis,
)


COMMENT_DEMAND_RULES: dict[str, tuple[str, ...]] = {
    "ROUTE": ("路线", "顺序", "路径", "怎么学", "从哪开始"),
    "RESOURCE": ("资料", "资源", "清单", "文档", "书单"),
    "PROJECT": ("项目", "实战", "作品", "案例"),
    "SOURCE_CODE": ("源码", "代码", "github", "仓库"),
    "PRICE": ("多少钱", "价格", "费用", "付费", "贵"),
    "COURSE": ("课程", "训练营", "教学"),
    "CONSULTATION": ("咨询", "私信", "可以问", "怎么联系"),
    "ANXIETY": ("焦虑", "来得及", "普通本科", "学不会", "没基础"),
    "MARKETING_RESISTANCE": ("割韭菜", "广告", "营销", "骗人", "套路"),
}

TITLE_PATTERN_RULES: dict[str, tuple[str, ...]] = {
    "数字清单型": (r"\d+",),
    "方法教程型": ("怎么", "如何", "教程", "方法"),
    "避坑警示型": ("别", "不要", "避坑", "踩坑"),
    "人群痛点型": ("普通", "大学生", "小白", "新手", "零基础"),
    "路线步骤型": ("路线", "步骤", "顺序", "路径"),
    "项目求职型": ("项目", "实战", "简历", "面试", "求职"),
}

CONTENT_PILLAR_RULES: dict[str, tuple[str, ...]] = {
    "学习路线": ("路线", "顺序", "怎么学", "入门"),
    "项目实战": ("项目", "实战", "业务闭环", "作品"),
    "求职简历": ("简历", "面试", "求职", "作品集"),
    "资源工具": ("资料", "资源", "工具", "模板"),
    "避坑复盘": ("避坑", "踩坑", "复盘", "别"),
}

CONVERSION_SIGNAL_RULES: dict[str, tuple[str, ...]] = {
    "收藏": ("收藏", "先收藏", "存起来"),
    "评论": ("评论", "留言", "告诉我"),
    "私信": ("私信", "咨询", "领取", "资料包"),
    "成交": ("价格", "课程", "付费", "下单"),
}

RISK_RULES: dict[str, tuple[str, ...]] = {
    "夸大承诺": ("保证", "包就业", "稳赚", "无风险"),
    "焦虑营销": ("再不学", "来不及", "淘汰", "废了"),
    "强营销": ("立刻下单", "限时付款", "割韭菜"),
}


class RuleBaselineCompetitorAnalyzer:
    """仅供回归和开发对照使用的历史关键词规则基线。"""

    analysis_engine = "RULE_BASELINE"

    def analyze(self, evidence: CompetitorEvidence) -> CompetitorSemanticResult:
        """运行集中隔离的历史规则，不作为正式产品默认分析器。"""
        pillars = self._pillars(evidence)
        demands = self._demands(evidence)
        title_patterns = self._title_patterns(evidence)
        structures = self._structures(evidence)
        conversion_signals = self._signals(evidence, CONVERSION_SIGNAL_RULES)
        risks = self._signals(evidence, RISK_RULES)
        top_note_ids = [item.note_id for item in evidence.computed_metrics.ranked_notes[:5]]
        fallback_refs = [EvidenceRef(source_type="NOTE", source_id=item) for item in top_note_ids[:1]]
        if not conversion_signals:
            conversion_signals = [ObservedSignal(name="弱转化信号", evidence=fallback_refs, confidence=0.2)]
        if not risks:
            risks = [ObservedSignal(name="低风险", evidence=fallback_refs, confidence=0.2)]
        return CompetitorSemanticResult(
            persona=self._persona(evidence),
            content_pillars=pillars,
            audience_demands=demands,
            high_performing_patterns=self._high_patterns(evidence, title_patterns),
            content_style=ContentStyleAnalysis(
                structure=structures or ["观点说明型"],
                tone=["知识分享"],
                hooks=title_patterns or ["普通表达型"],
                visual_patterns=self._cover_patterns(evidence) or ["未提供视觉证据"],
                evidence_note_ids=top_note_ids,
            ),
            follow_recommendation=FollowRecommendationAnalysis(
                why_follow="可持续观察高互动主题及评论反馈，但规则结果仅用于基线参考。",
                what_to_learn=["内容结构", "证据组织", "用户问题表达"],
                what_not_to_copy=["具体标题和正文", "未经验证的转化承诺"],
                confidence=0.45,
                evidence=[EvidenceRef(source_type="NOTE", source_id=item) for item in top_note_ids],
            ),
            content_opportunities=self._opportunities(pillars, demands),
            conversion_signals=conversion_signals,
            risk_points=risks,
            data_gaps=[*evidence.data_gaps, "当前结果来自关键词规则基线，不代表正式语义分析质量"],
        )

    def _persona(self, evidence: CompetitorEvidence) -> PersonaAnalysis:
        labels = []
        for account in evidence.accounts:
            text = f"{account.nickname} {account.bio or ''}"
            labels.extend(
                self._detect(
                    text,
                    {
                        "项目学姐/学长": ("学姐", "学长", "项目"),
                        "求职导师": ("求职", "简历", "面试"),
                        "资源整理号": ("资料", "资源", "清单"),
                        "实战教程号": ("教程", "实战", "路线"),
                    },
                    "知识分享号",
                )
            )
        positioning = Counter(labels).most_common(1)[0][0] if labels else "知识分享号"
        return PersonaAnalysis(
            positioning=positioning,
            expertise=[item.name for item in self._pillars(evidence)[:3]],
            target_audience=["账号内容的潜在读者"],
            value_proposition="通过知识内容提供学习或实践参考",
            tone_and_style=["知识分享"],
            confidence=0.4,
            evidence=[EvidenceRef(source_type="ACCOUNT", source_id=item.id) for item in evidence.accounts],
        )

    def _pillars(self, evidence: CompetitorEvidence) -> list[ContentPillarAnalysis]:
        matched: dict[str, list[int]] = {}
        for note in evidence.notes:
            names = self._detect(self._note_text(note), CONTENT_PILLAR_RULES, "综合内容")
            for name in names:
                matched.setdefault(name, []).append(note.id)
        return [
            ContentPillarAnalysis(
                name=name,
                description=f"规则关键词命中 {len(note_ids)} 篇笔记。",
                evidence_note_ids=note_ids,
                confidence=0.45,
            )
            for name, note_ids in sorted(matched.items(), key=lambda item: len(item[1]), reverse=True)
        ]

    def _demands(self, evidence: CompetitorEvidence) -> list[AudienceDemandAnalysis]:
        matched: dict[str, list[int]] = {}
        for comment in evidence.comments:
            demand = next(
                (
                    name
                    for name, keywords in COMMENT_DEMAND_RULES.items()
                    if any(keyword.lower() in comment.content.lower() for keyword in keywords)
                ),
                "UNKNOWN",
            )
            matched.setdefault(demand, []).append(comment.id)
        return [
            AudienceDemandAnalysis(
                demand=name,
                user_intent=f"规则识别为 {name} 的评论意图",
                representative_comment_ids=comment_ids[:3],
                confidence=0.4 if name != "UNKNOWN" else 0.2,
            )
            for name, comment_ids in sorted(matched.items(), key=lambda item: len(item[1]), reverse=True)
        ]

    def _title_patterns(self, evidence: CompetitorEvidence) -> list[str]:
        patterns = [
            pattern
            for note in evidence.notes
            for pattern in self._detect_regex(note.title or "", TITLE_PATTERN_RULES, "普通表达型")
        ]
        return [name for name, _ in Counter(patterns).most_common()]

    def _structures(self, evidence: CompetitorEvidence) -> list[str]:
        rules = {
            "问题-步骤-总结": ("怎么", "步骤", "总结"),
            "痛点-避坑-建议": ("别", "避坑", "建议"),
            "场景-清单-行动": ("清单", "行动", "收藏"),
            "项目-拆解-求职表达": ("项目", "拆解", "简历"),
        }
        values = [name for note in evidence.notes for name in self._detect(self._note_text(note), rules, "观点说明型")]
        return [name for name, _ in Counter(values).most_common()]

    def _cover_patterns(self, evidence: CompetitorEvidence) -> list[str]:
        rules = {
            "痛点警示封面": ("别", "不要", "避坑"),
            "路线承诺封面": ("路线", "步骤", "顺序"),
            "结果展示封面": ("简历", "项目", "作品"),
        }
        values = [name for note in evidence.notes for name in self._detect(note.title or "", rules, "知识点封面")]
        return [name for name, _ in Counter(values).most_common()]

    def _high_patterns(self, evidence: CompetitorEvidence, title_patterns: list[str]) -> list[HighPerformingPatternAnalysis]:
        result = []
        for index, metric in enumerate(evidence.computed_metrics.ranked_notes[:5]):
            result.append(
                HighPerformingPatternAnalysis(
                    pattern=title_patterns[index] if index < len(title_patterns) else "高互动内容",
                    evidence_note_ids=[metric.note_id],
                    metric_evidence=[
                        MetricEvidence(note_id=metric.note_id, metric="engagement_score", value=metric.engagement_score)
                    ],
                    confidence=0.5,
                )
            )
        return result

    def _signals(self, evidence: CompetitorEvidence, rules: dict[str, tuple[str, ...]]) -> list[ObservedSignal]:
        result = []
        for name, keywords in rules.items():
            refs = []
            for note in evidence.notes:
                if any(keyword.lower() in self._note_text(note).lower() for keyword in keywords):
                    refs.append(EvidenceRef(source_type="NOTE", source_id=note.id))
            for comment in evidence.comments:
                if any(keyword.lower() in comment.content.lower() for keyword in keywords):
                    refs.append(EvidenceRef(source_type="COMMENT", source_id=comment.id))
            if refs:
                result.append(ObservedSignal(name=name, evidence=refs, confidence=0.4))
        return result

    def _opportunities(
        self,
        pillars: list[ContentPillarAnalysis],
        demands: list[AudienceDemandAnalysis],
    ) -> list[ContentOpportunityAnalysis]:
        result = []
        demand_items = demands or [AudienceDemandAnalysis(demand="UNKNOWN", user_intent="评论证据不足", representative_comment_ids=[], confidence=0.1)]
        for index, pillar in enumerate(pillars[:3]):
            demand = demand_items[index % len(demand_items)]
            result.append(
                ContentOpportunityAnalysis(
                    opportunity=f"{pillar.name} × {demand.demand} 内容机会",
                    reason=f"规则基线同时观察到内容方向「{pillar.name}」和评论需求「{demand.demand}」。",
                    evidence_note_ids=pillar.evidence_note_ids,
                    evidence_comment_ids=demand.representative_comment_ids,
                    confidence=min(pillar.confidence, demand.confidence),
                )
            )
        return result

    def _note_text(self, note) -> str:
        return f"{note.title or ''} {note.content or ''} {' '.join(note.tags)}"

    def _detect(self, text: str, rules: dict[str, tuple[str, ...]], fallback: str) -> list[str]:
        matched = [name for name, keywords in rules.items() if any(keyword.lower() in text.lower() for keyword in keywords)]
        return matched or [fallback]

    def _detect_regex(self, text: str, rules: dict[str, tuple[str, ...]], fallback: str) -> list[str]:
        matched = [name for name, keys in rules.items() if any(re.search(key, text, flags=re.IGNORECASE) for key in keys)]
        return matched or [fallback]
