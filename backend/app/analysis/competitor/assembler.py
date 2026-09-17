from collections import Counter

from app.analysis.competitor.schemas import CompetitorEvidence, CompetitorSemanticResult
from app.models.competitors_analysis import CompetitorAnalysisReport
from app.models.content_opportunity import ContentOpportunity
from app.models.viral_note_breakdown import ViralNoteBreakdown
from app.schemas.competitor_report import CompetitorReportCreate


class CompetitorReportAssembler:
    """把结构化语义结果适配到现有报告表，不执行内容推理。"""

    def assemble(
        self,
        data: CompetitorReportCreate,
        evidence: CompetitorEvidence,
        semantic: CompetitorSemanticResult,
        analysis_engine: str,
        sample_state: dict,
    ) -> tuple[CompetitorAnalysisReport, list[ViralNoteBreakdown], list[ContentOpportunity]]:
        """构造现有报告、爆款拆解和内容机会实体。"""
        report = CompetitorAnalysisReport(
            account_id=data.account_id,
            name=data.name,
            keyword=data.keyword,
            source_type="COMPETITOR_COLLECTION",
            target_metric=data.target_metric,
            note_snapshot_ids=[],
            competitor_account_ids=evidence.used_account_ids,
            competitor_note_ids=evidence.used_note_ids,
            note_count=len(evidence.notes),
            comment_count=len(evidence.comments),
            persona_patterns=[self._persona(semantic, evidence)],
            content_pillars=[self._pillar(item) for item in semantic.content_pillars],
            top_tags=self._top_tags(evidence),
            title_patterns=[{"name": item, "count": 1} for item in semantic.content_style.hooks],
            cover_patterns=[{"name": item, "count": 1} for item in semantic.content_style.visual_patterns],
            content_structures=[{"name": item, "count": 1} for item in semantic.content_style.structure],
            comment_demands=[self._demand(item) for item in semantic.audience_demands],
            conversion_signals=[self._signal(item) for item in semantic.conversion_signals],
            replicability_summary=self._replicability(semantic, sample_state, analysis_engine),
            risk_points=[self._signal(item) for item in semantic.risk_points],
            high_performance_notes=self._high_notes(evidence, semantic),
            content_insights=self._insights(semantic),
            suggestions=self._suggestions(semantic, sample_state),
            summary=self._summary(evidence, semantic),
            status="SUCCESS",
        )
        return report, self._breakdowns(evidence, semantic), self._opportunities(evidence, semantic)

    def _persona(self, semantic: CompetitorSemanticResult, evidence: CompetitorEvidence) -> dict:
        persona = semantic.persona
        return {
            "name": persona.positioning,
            "count": len(evidence.accounts),
            "positioning": persona.positioning,
            "expertise": persona.expertise,
            "target_audience": persona.target_audience,
            "value_proposition": persona.value_proposition,
            "tone_and_style": persona.tone_and_style,
            "confidence": persona.confidence,
            "evidence": [item.model_dump() for item in persona.evidence],
        }

    def _pillar(self, item) -> dict:
        return {
            "name": item.name,
            "description": item.description,
            "count": len(item.evidence_note_ids),
            "evidence_note_ids": item.evidence_note_ids,
            "confidence": item.confidence,
        }

    def _demand(self, item) -> dict:
        return {
            "type": item.demand,
            "demand": item.demand,
            "user_intent": item.user_intent,
            "count": len(item.representative_comment_ids),
            "representative_comment_ids": item.representative_comment_ids,
            "confidence": item.confidence,
        }

    def _signal(self, item) -> dict:
        return {
            "name": item.name,
            "count": len(item.evidence),
            "confidence": item.confidence,
            "evidence": [ref.model_dump() for ref in item.evidence],
        }

    def _top_tags(self, evidence: CompetitorEvidence) -> list[dict]:
        tags = Counter(tag for note in evidence.notes for tag in note.tags)
        return [{"name": name, "count": count} for name, count in tags.most_common(20)]

    def _replicability(self, semantic: CompetitorSemanticResult, sample_state: dict, analysis_engine: str) -> dict:
        scores = [round(item.confidence * 100) for item in semantic.high_performing_patterns]
        return {
            "avg_score": round(sum(scores) / len(scores)) if scores else 0,
            "sample_count": len(scores),
            "risk_adjusted": any(item.name != "低风险" for item in semantic.risk_points),
            "analysis_engine": analysis_engine,
            **sample_state,
            "data_gaps": semantic.data_gaps,
        }

    def _high_notes(self, evidence: CompetitorEvidence, semantic: CompetitorSemanticResult) -> list[dict]:
        note_by_id = {item.id: item for item in evidence.notes}
        pattern_by_note = {
            note_id: item.pattern
            for item in semantic.high_performing_patterns
            for note_id in item.evidence_note_ids
        }
        result = []
        for metric in evidence.computed_metrics.ranked_notes[:5]:
            note = note_by_id[metric.note_id]
            result.append(
                {
                    "competitor_note_id": note.id,
                    "title": note.title,
                    "author_name": note.author_name,
                    "note_url": note.note_url,
                    "like_count": note.like_count,
                    "collect_count": note.collect_count,
                    "comment_count": note.comment_count,
                    "score": metric.engagement_score,
                    "reason": pattern_by_note.get(note.id, "按真实互动指标排序"),
                }
            )
        return result

    def _insights(self, semantic: CompetitorSemanticResult) -> list[str]:
        insights = [f"账号定位：{semantic.persona.positioning}。"]
        insights.extend(f"内容支柱「{item.name}」：{item.description}" for item in semantic.content_pillars[:3])
        insights.extend(f"用户需求「{item.demand}」：{item.user_intent}" for item in semantic.audience_demands[:3])
        return insights

    def _suggestions(self, semantic: CompetitorSemanticResult, sample_state: dict) -> list[str]:
        suggestions = []
        if sample_state.get("hint"):
            suggestions.append(sample_state["hint"])
        suggestions.append(semantic.follow_recommendation.why_follow)
        suggestions.extend(f"可学习：{item}" for item in semantic.follow_recommendation.what_to_learn)
        suggestions.extend(f"不要照搬：{item}" for item in semantic.follow_recommendation.what_not_to_copy)
        return suggestions

    def _summary(self, evidence: CompetitorEvidence, semantic: CompetitorSemanticResult) -> str:
        return (
            f"本次分析 {len(evidence.notes)} 篇竞品笔记和 {len(evidence.comments)} 条评论；"
            f"账号定位为「{semantic.persona.positioning}」，识别到 {len(semantic.content_pillars)} 个内容支柱、"
            f"{len(semantic.audience_demands)} 类用户需求。"
        )

    def _breakdowns(self, evidence: CompetitorEvidence, semantic: CompetitorSemanticResult) -> list[ViralNoteBreakdown]:
        note_by_id = {item.id: item for item in evidence.notes}
        comments_by_note: dict[int, list[int]] = {}
        for comment in evidence.comments:
            comments_by_note.setdefault(comment.competitor_note_id, []).append(comment.id)
        demand_by_comment = {
            comment_id: demand
            for demand in semantic.audience_demands
            for comment_id in demand.representative_comment_ids
        }
        pattern_by_note = {
            note_id: pattern
            for pattern in semantic.high_performing_patterns
            for note_id in pattern.evidence_note_ids
        }
        title_pattern = semantic.content_style.hooks[0] if semantic.content_style.hooks else "未识别"
        cover_pattern = semantic.content_style.visual_patterns[0] if semantic.content_style.visual_patterns else "未提供视觉证据"
        structure = semantic.content_style.structure[0] if semantic.content_style.structure else "未识别"
        risks = [item.name for item in semantic.risk_points]
        conversions = [item.name for item in semantic.conversion_signals]
        result = []
        for metric in evidence.computed_metrics.ranked_notes[:5]:
            note = note_by_id[metric.note_id]
            comment_demands = []
            for comment_id in comments_by_note.get(note.id, []):
                demand = demand_by_comment.get(comment_id)
                if demand:
                    comment_demands.append(self._demand(demand))
            confidence = pattern_by_note.get(note.id).confidence if note.id in pattern_by_note else 0.5
            result.append(
                ViralNoteBreakdown(
                    report_id=0,
                    competitor_note_id=note.id,
                    note_title=note.title,
                    note_url=note.note_url,
                    engagement_score=metric.engagement_score,
                    title_pattern=self._clip(title_pattern, 64),
                    cover_pattern=self._clip(cover_pattern, 64),
                    content_structure=self._clip(structure, 64),
                    comment_demands=comment_demands,
                    conversion_signals=conversions,
                    replicability_score=round(confidence * 100),
                    risk_points=risks,
                    evidence_summary=(
                        f"笔记「{note.title or note.id}」点赞 {note.like_count}、收藏 {note.collect_count}、"
                        f"评论 {note.comment_count}，互动分 {metric.engagement_score}。"
                    ),
                )
            )
        return result

    def _opportunities(self, evidence: CompetitorEvidence, semantic: CompetitorSemanticResult) -> list[ContentOpportunity]:
        pillar_by_note = {
            note_id: pillar.name
            for pillar in semantic.content_pillars
            for note_id in pillar.evidence_note_ids
        }
        demand_by_comment = {
            comment_id: demand.demand
            for demand in semantic.audience_demands
            for comment_id in demand.representative_comment_ids
        }
        real_risks = [item for item in semantic.risk_points if item.name != "低风险"]
        risk_level = "HIGH" if len(real_risks) > 1 else "MEDIUM" if real_risks else "LOW"
        target_audience = "、".join(semantic.persona.target_audience)
        result = []
        for item in semantic.content_opportunities[:3]:
            pillar = next((pillar_by_note[note_id] for note_id in item.evidence_note_ids if note_id in pillar_by_note), "待验证方向")
            demand = next((demand_by_comment[comment_id] for comment_id in item.evidence_comment_ids if comment_id in demand_by_comment), "待验证需求")
            score = round(item.confidence * 100)
            result.append(
                ContentOpportunity(
                    report_id=0,
                    opportunity_title=self._clip(item.opportunity, 256),
                    suggested_angle=self._clip(item.reason, 256),
                    target_audience=self._clip(target_audience, 128) or None,
                    content_pillar=self._clip(pillar, 64),
                    comment_demand_type=self._clip(demand, 64),
                    evidence_summary=(
                        f"笔记证据 {item.evidence_note_ids}；评论证据 {item.evidence_comment_ids}；"
                        f"置信度 {item.confidence:.2f}。"
                    ),
                    replicability_score=score,
                    risk_level=risk_level,
                    risk_points=[risk.name for risk in semantic.risk_points],
                    opportunity_score=max(0, score - (20 if risk_level == "HIGH" else 10 if risk_level == "MEDIUM" else 0)),
                )
            )
        return result

    def _clip(self, value: str, limit: int) -> str:
        return value[:limit]
