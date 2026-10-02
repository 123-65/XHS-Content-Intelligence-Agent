"""Deprecated V0 competitor analysis retained for legacy API compatibility.

New production Research must use ``CompetitorReportService`` with the
structured LLM analysis core. This module is not a canonical Research owner.
"""

import re
from collections import Counter

from sqlalchemy.orm import Session

from app.models.competitors_analysis import CompetitorAnalysisReport
from app.models.xhs_note import XhsNoteSnapshot
from app.repositories.competitor_analysis_repo import CompetitorAnalysisRepository
from app.schemas.competitor_analysis import CompetitorAnalysisCreate


class CompetitorAnalysisService:
    """DEPRECATED/LEGACY_COMPAT V0 rule-based competitor analysis service."""

    def __init__(self, db: Session):
        """初始化竞品分析服务。"""
        self.repo = CompetitorAnalysisRepository(db)

    def create_analysis(self, data: CompetitorAnalysisCreate) -> CompetitorAnalysisReport:
        """创建竞品内容分析报告。"""
        notes = self.repo.list_notes_for_analysis(
            source_type=data.source_type,
            keyword=data.keyword,
            note_snapshot_ids=data.note_snapshot_ids,
            limit=data.limit,
        )
        if not notes:
            raise ValueError("没有可用于分析的竞品笔记，请先采集或手动创建笔记快照")

        top_tags = self._analyze_tags(notes)
        title_patterns = self._analyze_title_patterns(notes)
        high_notes = self._find_high_performance_notes(notes, data.target_metric)
        insights = self._build_content_insights(top_tags, title_patterns, high_notes)
        suggestions = self._build_suggestions(top_tags, title_patterns, high_notes)
        summary = self._build_summary(notes, top_tags, title_patterns)

        report = CompetitorAnalysisReport(
            account_id=data.account_id,
            name=data.name,
            keyword=data.keyword,
            source_type=data.source_type,
            target_metric=data.target_metric,
            note_snapshot_ids=[note.id for note in notes],
            note_count=len(notes),
            top_tags=top_tags,
            title_patterns=title_patterns,
            high_performance_notes=high_notes,
            content_insights=insights,
            suggestions=suggestions,
            summary=summary,
            status="SUCCESS",
        )
        return self.repo.create(report)

    def list_reports(self, limit: int = 20) -> list[CompetitorAnalysisReport]:
        """查询竞品分析报告列表。"""
        return self.repo.list_latest(limit)

    def get_report(self, report_id: int) -> CompetitorAnalysisReport:
        """查询竞品分析报告详情。"""
        report = self.repo.get_by_id(report_id)
        if not report:
            raise ValueError("竞品分析报告不存在")
        return report

    def _analyze_tags(self, notes: list[XhsNoteSnapshot]) -> list[dict]:
        """统计高频标签。"""
        counter: Counter[str] = Counter()
        for note in notes:
            for tag in note.tags or []:
                counter[tag] += 1
        return [{"tag": tag, "count": count} for tag, count in counter.most_common(10)]

    def _analyze_title_patterns(self, notes: list[XhsNoteSnapshot]) -> list[dict]:
        """分析标题结构模式。"""
        pattern_counter: Counter[str] = Counter()
        examples: dict[str, list[str]] = {}

        for note in notes:
            title = note.title or ""
            patterns = self._detect_title_patterns(title)
            for pattern in patterns:
                pattern_counter[pattern] += 1
                examples.setdefault(pattern, [])
                if title and len(examples[pattern]) < 3:
                    examples[pattern].append(title)

        return [
            {"pattern": pattern, "count": count, "examples": examples.get(pattern, [])}
            for pattern, count in pattern_counter.most_common()
        ]

    def _detect_title_patterns(self, title: str) -> list[str]:
        """识别单个标题属于哪些模式。"""
        patterns = []
        if re.search(r"\d+", title):
            patterns.append("数字清单型")
        if any(word in title for word in ["怎么", "如何", "教程", "方法"]):
            patterns.append("方法教程型")
        if any(word in title for word in ["别", "不要", "避坑", "踩坑"]):
            patterns.append("避坑警示型")
        if any(word in title for word in ["普通", "大学生", "小白", "新手", "零基础"]):
            patterns.append("人群痛点型")
        if any(word in title for word in ["路线", "步骤", "顺序", "规划"]):
            patterns.append("路线步骤型")
        if any(word in title for word in ["项目", "实战", "简历", "面试"]):
            patterns.append("项目求职型")
        if not patterns:
            patterns.append("普通表达型")
        return patterns

    def _find_high_performance_notes(self, notes: list[XhsNoteSnapshot], target_metric: str) -> list[dict]:
        """筛选高表现笔记。"""
        sorted_notes = sorted(notes, key=lambda note: self._score_note(note, target_metric), reverse=True)
        result = []

        for note in sorted_notes[:5]:
            result.append(
                {
                    "snapshot_id": note.id,
                    "title": note.title,
                    "author_name": note.author_name,
                    "note_url": note.note_url,
                    "like_count": note.like_count or 0,
                    "collect_count": note.collect_count or 0,
                    "comment_count": note.comment_count or 0,
                    "image_count": note.image_count or 0,
                    "score": self._score_note(note, target_metric),
                    "reason": self._build_high_note_reason(note),
                }
            )
        return result

    def _score_note(self, note: XhsNoteSnapshot, target_metric: str) -> float:
        """根据目标指标计算笔记表现分。"""
        like_count = note.like_count or 0
        collect_count = note.collect_count or 0
        comment_count = note.comment_count or 0

        if target_metric == "like":
            return float(like_count)
        if target_metric == "collect":
            return float(collect_count)
        if target_metric == "comment":
            return float(comment_count)

        return like_count * 1.0 + collect_count * 1.5 + comment_count * 2.0

    def _build_high_note_reason(self, note: XhsNoteSnapshot) -> str:
        """生成高表现笔记原因说明。"""
        title = note.title or ""
        reasons = []

        if note.collect_count and note.collect_count >= note.like_count * 0.3:
            reasons.append("收藏占比较高，可能具备教程、清单或路线价值")
        if any(word in title for word in ["路线", "步骤", "教程", "清单"]):
            reasons.append("标题偏教程/路线型，适合用户收藏")
        if any(word in title for word in ["别", "不要", "避坑"]):
            reasons.append("标题带避坑提醒，容易触发点击")
        if note.comment_count and note.comment_count > 50:
            reasons.append("评论较多，可能引发了讨论或咨询")

        return "；".join(reasons) if reasons else "综合互动表现较好，可作为参考样本"

    def _build_content_insights(
        self,
        top_tags: list[dict],
        title_patterns: list[dict],
        high_notes: list[dict],
    ) -> list[str]:
        """生成竞品内容洞察。"""
        insights = []

        if top_tags:
            tags = "、".join([item["tag"] for item in top_tags[:5]])
            insights.append(f"高频标签集中在：{tags}，说明竞品内容主要围绕这些话题获取流量。")

        if title_patterns:
            pattern = title_patterns[0]["pattern"]
            insights.append(f"出现最多的标题结构是「{pattern}」，可以作为后续标题生成的重要参考。")

        if high_notes:
            best = high_notes[0]
            insights.append(
                f"当前最高表现样本是「{best.get('title')}」，综合分为 {best.get('score')}，建议拆解其选题角度和表达方式。"
            )

        insights.append("当前分析基于公开互动数据，只能反映内容吸引力，不能直接代表真实成交效果。")
        return insights

    def _build_suggestions(
        self,
        top_tags: list[dict],
        title_patterns: list[dict],
        high_notes: list[dict],
    ) -> list[str]:
        """生成后续内容创作建议。"""
        suggestions = []

        if title_patterns:
            suggestions.append(f"下一批内容可以优先测试「{title_patterns[0]['pattern']}」标题。")

        if top_tags:
            suggestions.append(f"标签可以优先组合使用：{'、'.join([item['tag'] for item in top_tags[:3]])}。")

        suggestions.extend(
            [
                "建议把每篇内容设计成一次实验，提前设定目标指标，例如收藏率、评论数或私信线索数。",
                "不要只模仿高点赞内容，要重点观察收藏和评论，因为它们更接近学习类账号的转化行为。",
                "后续生成草稿时，应结合账号定位、竞品高频模式和历史策略记忆，而不是单纯复刻竞品。",
            ]
        )
        return suggestions

    def _build_summary(
        self,
        notes: list[XhsNoteSnapshot],
        top_tags: list[dict],
        title_patterns: list[dict],
    ) -> str:
        """生成分析摘要。"""
        tag_text = "、".join([item["tag"] for item in top_tags[:3]]) if top_tags else "暂无明显高频标签"
        pattern_text = title_patterns[0]["pattern"] if title_patterns else "暂无明显标题模式"
        return f"本次共分析 {len(notes)} 篇竞品笔记，高频标签包括 {tag_text}，主要标题模式为「{pattern_text}」。"
