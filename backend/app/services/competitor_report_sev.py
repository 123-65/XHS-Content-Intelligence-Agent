import re
from collections import Counter

from sqlalchemy.orm import Session

from app.enums.competitor_analysis import CommentDemandType, RiskLevel
from app.models.competitor_account import CompetitorAccount
from app.models.competitor_comment import CompetitorComment
from app.models.competitor_note import CompetitorNote
from app.models.competitors_analysis import CompetitorAnalysisReport
from app.models.content_opportunity import ContentOpportunity
from app.models.viral_note_breakdown import ViralNoteBreakdown
from app.repositories.competitor_report_repo import CompetitorReportRepository
from app.schemas.competitor_report import CompetitorReportCreate


class DataAvailabilityError(ValueError):
    """结构化表达业务数据不可用原因。"""

    def __init__(self, message: str, payload: dict):
        super().__init__(message)
        self.payload = payload


COMMENT_DEMAND_RULES: dict[CommentDemandType, tuple[str, ...]] = {
    CommentDemandType.ROUTE: ("路线", "顺序", "路径", "怎么学", "从哪开始"),
    CommentDemandType.RESOURCE: ("资料", "资源", "清单", "文档", "书单"),
    CommentDemandType.PROJECT: ("项目", "实战", "作品", "案例"),
    CommentDemandType.SOURCE_CODE: ("源码", "代码", "github", "GitHub", "仓库"),
    CommentDemandType.PRICE: ("多少钱", "价格", "费用", "付费", "贵"),
    CommentDemandType.COURSE: ("课程", "课", "训练营", "教学"),
    CommentDemandType.CONSULTATION: ("咨询", "私信", "可以问", "怎么联系"),
    CommentDemandType.ANXIETY: ("焦虑", "来得及", "普通本科", "学不会", "没基础"),
    CommentDemandType.MARKETING_RESISTANCE: ("割韭菜", "广告", "营销", "骗人", "套路"),
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


class CompetitorReportService:
    """V2 竞品与爆款分析业务服务。"""

    def __init__(self, db: Session):
        """初始化 V2 竞品分析服务。"""
        self.repo = CompetitorReportRepository(db)

    def create_report(self, data: CompetitorReportCreate) -> CompetitorAnalysisReport:
        """创建竞品分析报告并生成爆款拆解和内容机会。"""
        self._ensure_account_exists(data.account_id)
        accounts = self.repo.list_competitor_accounts(data.account_id)
        notes = self.repo.list_competitor_notes(data.account_id, data.keyword, data.limit)
        if not notes:
            state = self._empty_note_state(data.account_id, data.keyword)
            raise DataAvailabilityError(state["message"], state)

        comments = self.repo.list_comments_for_notes(data.account_id, [note.id for note in notes])
        analyses = self._analyze_notes(notes, comments)
        sample_state = self._sample_state(notes, comments)
        report = CompetitorAnalysisReport(
            account_id=data.account_id,
            name=data.name,
            keyword=data.keyword,
            source_type="COMPETITOR_COLLECTION",
            target_metric=data.target_metric,
            note_snapshot_ids=[],
            competitor_account_ids=[item.id for item in accounts],
            competitor_note_ids=[item.id for item in notes],
            note_count=len(notes),
            comment_count=len(comments),
            persona_patterns=self._analyze_personas(accounts),
            content_pillars=analyses["content_pillars"],
            top_tags=analyses["top_tags"],
            title_patterns=analyses["title_patterns"],
            cover_patterns=analyses["cover_patterns"],
            content_structures=analyses["content_structures"],
            comment_demands=analyses["comment_demands"],
            conversion_signals=analyses["conversion_signals"],
            replicability_summary={**analyses["replicability_summary"], **sample_state},
            risk_points=analyses["risk_points"],
            high_performance_notes=analyses["high_performance_notes"],
            content_insights=self._build_insights(analyses),
            suggestions=[sample_state["hint"], *self._build_suggestions(analyses)] if sample_state["reason"] != "READY" else self._build_suggestions(analyses),
            summary=self._build_summary(notes, comments, analyses),
            status="SUCCESS",
        )
        breakdowns = self._build_breakdowns(notes, comments, analyses)
        opportunities = self._build_opportunities(data, analyses)
        return self.repo.create_report_bundle(report, breakdowns, opportunities)

    def _empty_note_state(self, account_id: int, keyword: str | None) -> dict:
        """区分报告入口下没有可用笔记的具体业务原因。"""
        total_count = self.repo.count_competitor_notes(account_id)
        real_count = self.repo.count_competitor_notes(account_id, is_mock=False)
        keyword_total_count = self.repo.count_competitor_notes(account_id, keyword=keyword) if keyword else total_count
        keyword_real_count = self.repo.count_competitor_notes(account_id, keyword=keyword, is_mock=False) if keyword else real_count

        if total_count == 0:
            reason = "NO_COMPETITOR_NOTES"
            message = "当前账号暂无竞品笔记，请先采集或手动录入真实样本"
            action = "COLLECT_COMPETITOR_NOTES"
            hint = "请先通过真实采集链路或手动录入公开笔记，再创建竞品分析报告。"
        elif real_count == 0:
            reason = "ONLY_MOCK_COMPETITOR_NOTES"
            message = "当前只有 Mock 竞品笔记，不能用于真实竞品分析"
            action = "REPLACE_WITH_REAL_NOTES"
            hint = "请补充 MCP、ReadOnly 或手动录入的真实公开笔记样本。"
        elif keyword and keyword_total_count > 0 and keyword_real_count == 0:
            reason = "KEYWORD_MATCHED_ONLY_MOCK"
            message = "当前关键词只命中 Mock 笔记，不能用于真实竞品分析"
            action = "COLLECT_REAL_NOTES_FOR_KEYWORD"
            hint = "请围绕该关键词补充真实笔记，或移除关键词查看账号下其他真实样本。"
        elif keyword:
            reason = "KEYWORD_NO_MATCH"
            message = "当前关键词没有命中可用于分析的真实竞品笔记"
            action = "RELAX_KEYWORD_OR_COLLECT_MORE"
            hint = "请换一个更宽的关键词，或先采集/录入该关键词下的真实样本。"
        else:
            reason = "NO_USABLE_REAL_NOTES"
            message = "当前没有可用于分析的真实竞品笔记"
            action = "COLLECT_COMPETITOR_NOTES"
            hint = "请补充真实公开笔记样本后重试。"

        return {
            "data_quality": "EMPTY",
            "reason": reason,
            "action": action,
            "message": message,
            "hint": hint,
            "can_continue": False,
            "counts": {
                "total_count": total_count,
                "real_count": real_count,
                "keyword_total_count": keyword_total_count,
                "keyword_real_count": keyword_real_count,
            },
        }

    def _sample_state(self, notes: list[CompetitorNote], comments: list[CompetitorComment]) -> dict:
        """给可继续分析的样本打质量标记。"""
        if len(notes) < 3:
            return {
                "data_quality": "PARTIAL",
                "reason": "INSUFFICIENT_SAMPLE",
                "action": "CONTINUE_WITH_LOW_CONFIDENCE",
                "hint": "真实竞品笔记少于 3 条，本次报告可生成，但建议补充样本后再做运营决策。",
                "can_continue": True,
            }
        if len(comments) < 3:
            return {
                "data_quality": "PARTIAL",
                "reason": "INSUFFICIENT_COMMENT_SAMPLE",
                "action": "CONTINUE_WITH_LOW_CONFIDENCE",
                "hint": "评论样本偏少，评论需求分类只能作为低置信参考。",
                "can_continue": True,
            }
        return {
            "data_quality": "READY",
            "reason": "READY",
            "action": "CONTINUE",
            "hint": "",
            "can_continue": True,
        }

    def get_report(self, report_id: int) -> CompetitorAnalysisReport:
        """查询竞品分析报告详情。"""
        report = self.repo.get_report(report_id)
        if report:
            return report
        raise ValueError("竞品分析报告不存在")

    def list_viral_breakdowns(self, report_id: int) -> list[ViralNoteBreakdown]:
        """查询爆款笔记拆解列表。"""
        self.get_report(report_id)
        return self.repo.list_viral_breakdowns(report_id)

    def list_opportunities(self, report_id: int) -> list[ContentOpportunity]:
        """查询内容机会列表。"""
        self.get_report(report_id)
        return self.repo.list_opportunities(report_id)

    def _ensure_account_exists(self, account_id: int) -> None:
        """校验账号是否存在。"""
        if self.repo.get_account(account_id):
            return
        raise ValueError("账号配置不存在")

    def _analyze_notes(self, notes: list[CompetitorNote], comments: list[CompetitorComment]) -> dict:
        """分析竞品笔记和评论。"""
        title_patterns = self._counter_items(pattern for note in notes for pattern in self._detect_title_patterns(note.title or ""))
        content_pillars = self._counter_items(pillar for note in notes for pillar in self._detect_by_rules(self._note_text(note), CONTENT_PILLAR_RULES, "综合内容"))
        comment_demands = self._analyze_comment_demands(comments)
        conversion_signals = self._counter_items(signal for text in self._all_texts(notes, comments) for signal in self._detect_by_rules(text, CONVERSION_SIGNAL_RULES, "弱转化信号"))
        risk_points = self._counter_items(risk for text in self._all_texts(notes, comments) for risk in self._detect_by_rules(text, RISK_RULES, "低风险"))
        high_notes = self._high_performance_notes(notes)
        return {
            "top_tags": self._counter_items(tag for note in notes for tag in (note.tags or [])),
            "title_patterns": title_patterns,
            "cover_patterns": self._counter_items(self._detect_cover_pattern(note) for note in notes),
            "content_structures": self._counter_items(self._detect_content_structure(note) for note in notes),
            "content_pillars": content_pillars,
            "comment_demands": comment_demands,
            "conversion_signals": conversion_signals,
            "risk_points": risk_points,
            "high_performance_notes": high_notes,
            "replicability_summary": self._replicability_summary(high_notes, risk_points),
        }

    def _analyze_personas(self, accounts: list[CompetitorAccount]) -> list[dict]:
        """分析同行账号人设。"""
        return self._counter_items(self._detect_persona(account) for account in accounts)

    def _detect_persona(self, account: CompetitorAccount) -> str:
        """识别同行账号人设。"""
        text = f"{account.nickname} {account.bio or ''}"
        rules = {
            "项目学姐/学长": ("学姐", "学长", "项目"),
            "求职导师": ("求职", "简历", "面试"),
            "资源整理号": ("资料", "资源", "清单"),
            "实战教程号": ("教程", "实战", "路线"),
        }
        return self._detect_by_rules(text, rules, "知识分享号")[0]

    def _detect_title_patterns(self, title: str) -> list[str]:
        """识别标题模式。"""
        patterns = [
            name for name, keys in TITLE_PATTERN_RULES.items()
            if any(re.search(key, title, flags=re.IGNORECASE) for key in keys)
        ]
        return patterns or ["普通表达型"]

    def _detect_cover_pattern(self, note: CompetitorNote) -> str:
        """识别封面模式。"""
        title = note.title or ""
        rules = {
            "痛点警示封面": ("别", "不要", "避坑"),
            "路线承诺封面": ("路线", "步骤", "顺序"),
            "结果展示封面": ("简历", "项目", "作品"),
        }
        return self._detect_by_rules(title, rules, "知识点封面")[0]

    def _detect_content_structure(self, note: CompetitorNote) -> str:
        """识别内容结构。"""
        text = self._note_text(note)
        rules = {
            "问题-步骤-总结": ("怎么", "步骤", "总结"),
            "痛点-避坑-建议": ("别", "避坑", "建议"),
            "场景-清单-行动": ("清单", "行动", "收藏"),
            "项目-拆解-求职表达": ("项目", "拆解", "简历"),
        }
        return self._detect_by_rules(text, rules, "观点说明型")[0]

    def _analyze_comment_demands(self, comments: list[CompetitorComment]) -> list[dict]:
        """分析评论需求分类。"""
        examples: dict[str, list[str]] = {}
        counts = Counter(self._classify_comment(comment.content) for comment in comments)
        for comment in comments:
            demand_type = self._classify_comment(comment.content)
            examples.setdefault(demand_type, [])
            if len(examples[demand_type]) < 3:
                examples[demand_type].append(comment.content)
        return [
            {"type": demand_type, "count": count, "examples": examples.get(demand_type, [])}
            for demand_type, count in counts.most_common()
        ] or [{"type": CommentDemandType.UNKNOWN.value, "count": 0, "examples": []}]

    def _classify_comment(self, content: str) -> str:
        """识别单条评论需求。"""
        return next(
            (
                demand.value
                for demand, keywords in COMMENT_DEMAND_RULES.items()
                if any(keyword.lower() in content.lower() for keyword in keywords)
            ),
            CommentDemandType.UNKNOWN.value,
        )

    def _high_performance_notes(self, notes: list[CompetitorNote]) -> list[dict]:
        """筛选高表现笔记。"""
        return [
            {
                "competitor_note_id": note.id,
                "title": note.title,
                "author_name": note.author_name,
                "note_url": note.note_url,
                "like_count": note.like_count or 0,
                "collect_count": note.collect_count or 0,
                "comment_count": note.comment_count or 0,
                "score": self._score_note(note),
                "reason": self._high_note_reason(note),
            }
            for note in sorted(notes, key=self._score_note, reverse=True)[:5]
        ]

    def _build_breakdowns(self, notes: list[CompetitorNote], comments: list[CompetitorComment], analyses: dict) -> list[ViralNoteBreakdown]:
        """生成爆款笔记拆解。"""
        comments_by_note = self._comments_by_note(comments)
        return [
            ViralNoteBreakdown(
                report_id=0,
                competitor_note_id=note.id,
                note_title=note.title,
                note_url=note.note_url,
                engagement_score=self._score_note(note),
                title_pattern=self._detect_title_patterns(note.title or "")[0],
                cover_pattern=self._detect_cover_pattern(note),
                content_structure=self._detect_content_structure(note),
                comment_demands=self._analyze_comment_demands(comments_by_note.get(note.id, [])),
                conversion_signals=self._detect_by_rules(self._note_text(note), CONVERSION_SIGNAL_RULES, "弱转化信号"),
                replicability_score=self._replicability_score(note, analyses["risk_points"]),
                risk_points=self._detect_by_rules(self._note_text(note), RISK_RULES, "低风险"),
                evidence_summary=self._evidence_summary(note),
            )
            for note in sorted(notes, key=self._score_note, reverse=True)[:5]
        ]

    def _build_opportunities(self, data: CompetitorReportCreate, analyses: dict) -> list[ContentOpportunity]:
        """生成内容机会。"""
        pillars = [item["name"] for item in analyses["content_pillars"][:3]] or ["学习路线"]
        demands = [item["type"] for item in analyses["comment_demands"][:3]] or [CommentDemandType.UNKNOWN.value]
        risk_level = self._risk_level(analyses["risk_points"])
        return [
            ContentOpportunity(
                report_id=0,
                opportunity_title=f"{pillar} × {demand} 内容机会",
                suggested_angle=f"围绕{data.keyword or pillar}，用{pillar}内容承接用户的{demand}需求",
                target_audience="账号目标用户",
                content_pillar=pillar,
                comment_demand_type=demand,
                evidence_summary=self._opportunity_evidence(pillar, demand, analyses),
                replicability_score=analyses["replicability_summary"]["avg_score"],
                risk_level=risk_level.value,
                risk_points=[item["name"] for item in analyses["risk_points"][:3]],
                opportunity_score=self._opportunity_score(analyses["replicability_summary"]["avg_score"], risk_level),
            )
            for pillar, demand in zip(pillars, [*demands, *demands, *demands])
        ][:3]

    def _counter_items(self, values) -> list[dict]:
        """将可迭代值统计成列表。"""
        return [{"name": name, "count": count} for name, count in Counter(value for value in values if value).most_common()]

    def _detect_by_rules(self, text: str, rules: dict[str, tuple[str, ...]], fallback: str) -> list[str]:
        """按关键词规则识别标签。"""
        matched = [name for name, keywords in rules.items() if any(keyword.lower() in text.lower() for keyword in keywords)]
        return matched or [fallback]

    def _all_texts(self, notes: list[CompetitorNote], comments: list[CompetitorComment]) -> list[str]:
        """汇总可分析文本。"""
        return [self._note_text(note) for note in notes] + [comment.content for comment in comments]

    def _note_text(self, note: CompetitorNote) -> str:
        """拼接笔记可分析文本。"""
        return f"{note.title or ''} {note.content or ''} {' '.join(note.tags or [])}"

    def _score_note(self, note: CompetitorNote) -> float:
        """计算笔记互动表现分。"""
        return float((note.like_count or 0) + (note.collect_count or 0) * 1.5 + (note.comment_count or 0) * 2)

    def _high_note_reason(self, note: CompetitorNote) -> str:
        """生成高表现原因。"""
        reasons = [
            "收藏占比较高，具备教程或清单价值" if (note.collect_count or 0) >= (note.like_count or 0) * 0.3 else "",
            "评论较多，说明用户有追问或转化线索" if (note.comment_count or 0) >= 50 else "",
            "标题包含路线、项目或求职信号" if self._detect_title_patterns(note.title or "") else "",
        ]
        return "；".join(reason for reason in reasons if reason) or "综合互动表现较好"

    def _replicability_score(self, note: CompetitorNote, risk_points: list[dict]) -> int:
        """计算可复制性评分。"""
        base = 72 + min(int((note.collect_count or 0) / 50), 18)
        penalty = 12 if any(item["name"] != "低风险" for item in risk_points) else 0
        return max(0, min(100, base - penalty))

    def _replicability_summary(self, high_notes: list[dict], risk_points: list[dict]) -> dict:
        """生成可复制性总结。"""
        scores = [self._replicability_score_proxy(item, risk_points) for item in high_notes]
        avg_score = round(sum(scores) / len(scores)) if scores else 0
        return {"avg_score": avg_score, "sample_count": len(scores), "risk_adjusted": any(item["name"] != "低风险" for item in risk_points)}

    def _replicability_score_proxy(self, high_note: dict, risk_points: list[dict]) -> int:
        """根据高表现摘要估算可复制性。"""
        base = 72 + min(int(high_note["collect_count"] / 50), 18)
        penalty = 12 if any(item["name"] != "低风险" for item in risk_points) else 0
        return max(0, min(100, base - penalty))

    def _risk_level(self, risk_points: list[dict]) -> RiskLevel:
        """根据风险点判断风险等级。"""
        real_risks = [item for item in risk_points if item["name"] != "低风险"]
        return {0: RiskLevel.LOW, 1: RiskLevel.MEDIUM}.get(len(real_risks), RiskLevel.HIGH)

    def _opportunity_score(self, replicability_score: int, risk_level: RiskLevel) -> int:
        """计算内容机会评分。"""
        penalty = {RiskLevel.LOW: 0, RiskLevel.MEDIUM: 10, RiskLevel.HIGH: 25}[risk_level]
        return max(0, min(100, replicability_score + 8 - penalty))

    def _comments_by_note(self, comments: list[CompetitorComment]) -> dict[int, list[CompetitorComment]]:
        """按笔记 ID 聚合评论。"""
        result: dict[int, list[CompetitorComment]] = {}
        for comment in comments:
            if comment.competitor_note_id is not None:
                result.setdefault(comment.competitor_note_id, []).append(comment)
        return result

    def _evidence_summary(self, note: CompetitorNote) -> str:
        """生成爆款拆解证据摘要。"""
        return f"笔记「{note.title}」点赞 {note.like_count or 0}、收藏 {note.collect_count or 0}、评论 {note.comment_count or 0}，互动分 {self._score_note(note)}。"

    def _opportunity_evidence(self, pillar: str, demand: str, analyses: dict) -> str:
        """生成内容机会证据摘要。"""
        top_pattern = analyses["title_patterns"][0]["name"] if analyses["title_patterns"] else "普通表达型"
        return f"高频内容支柱包含「{pillar}」，评论需求出现「{demand}」，标题模式以「{top_pattern}」为主。"

    def _build_insights(self, analyses: dict) -> list[str]:
        """生成分析洞察。"""
        return [
            f"主要内容支柱是「{analyses['content_pillars'][0]['name']}」。" if analyses["content_pillars"] else "暂无明显内容支柱。",
            f"主要标题模式是「{analyses['title_patterns'][0]['name']}」。" if analyses["title_patterns"] else "暂无明显标题模式。",
            f"主要评论需求是「{analyses['comment_demands'][0]['type']}」。",
            "高收藏和高评论内容更适合沉淀为后续内容实验的候选方向。",
        ]

    def _build_suggestions(self, analyses: dict) -> list[str]:
        """生成分析建议。"""
        return [
            "优先选择可复制性高、风险低的选题进入内容实验。",
            "不要直接复刻爆款标题和正文，应复用结构、需求和证据链。",
            "评论需求里出现资源、项目、咨询信号时，可以设计更自然的 CTA。",
        ]

    def _build_summary(self, notes: list[CompetitorNote], comments: list[CompetitorComment], analyses: dict) -> str:
        """生成报告摘要。"""
        top_pillar = analyses["content_pillars"][0]["name"] if analyses["content_pillars"] else "暂无明显内容支柱"
        top_demand = analyses["comment_demands"][0]["type"] if analyses["comment_demands"] else CommentDemandType.UNKNOWN.value
        return f"本次分析 {len(notes)} 篇竞品笔记和 {len(comments)} 条评论，主要内容支柱为「{top_pillar}」，主要评论需求为「{top_demand}」。"
