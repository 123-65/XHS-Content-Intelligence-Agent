from app.analysis.competitor.engine import CompetitorAnalysisError
from app.analysis.competitor.schemas import CompetitorEvidence, CompetitorSemanticResult, EvidenceRef


class CompetitorGroundingValidator:
    """校验所有分析引用都属于当前证据集合。"""

    def validate(
        self,
        evidence: CompetitorEvidence,
        result: CompetitorSemanticResult,
    ) -> CompetitorSemanticResult:
        """拒绝模型编造的账号、笔记、评论、指标和 OCR 引用。"""
        account_ids = set(evidence.used_account_ids)
        note_ids = set(evidence.used_note_ids)
        comment_ids = set(evidence.used_comment_ids)
        ocr_note_ids = set(evidence.ocr_note_ids)

        refs = [*result.persona.evidence, *result.follow_recommendation.evidence]
        refs.extend(ref for item in result.conversion_signals for ref in item.evidence)
        refs.extend(ref for item in result.risk_points for ref in item.evidence)
        for ref in refs:
            self._validate_ref(ref, account_ids, note_ids, comment_ids, ocr_note_ids)

        self._validate_ids("content_pillars.evidence_note_ids", note_ids, [item_id for item in result.content_pillars for item_id in item.evidence_note_ids])
        self._validate_ids("audience_demands.representative_comment_ids", comment_ids, [item_id for item in result.audience_demands for item_id in item.representative_comment_ids])
        self._validate_ids("high_performing_patterns.evidence_note_ids", note_ids, [item_id for item in result.high_performing_patterns for item_id in item.evidence_note_ids])
        self._validate_ids("high_performing_patterns.metric_evidence", note_ids, [item.note_id for pattern in result.high_performing_patterns for item in pattern.metric_evidence])
        self._validate_ids("content_style.evidence_note_ids", note_ids, result.content_style.evidence_note_ids)
        self._validate_ids("content_opportunities.evidence_note_ids", note_ids, [item_id for item in result.content_opportunities for item_id in item.evidence_note_ids])
        self._validate_ids("content_opportunities.evidence_comment_ids", comment_ids, [item_id for item in result.content_opportunities for item_id in item.evidence_comment_ids])
        return result

    def _validate_ref(
        self,
        ref: EvidenceRef,
        account_ids: set[int],
        note_ids: set[int],
        comment_ids: set[int],
        ocr_note_ids: set[int],
    ) -> None:
        allowed = {
            "ACCOUNT": account_ids,
            "NOTE": note_ids,
            "COMMENT": comment_ids,
            "METRIC": note_ids,
            "OCR": ocr_note_ids,
        }[ref.source_type]
        if ref.source_id not in allowed:
            self._fail(f"{ref.source_type}:{ref.source_id}")

    def _validate_ids(self, field: str, allowed: set[int], values: list[int]) -> None:
        invalid = sorted(set(values) - allowed)
        if invalid:
            self._fail(f"{field} contains {invalid}")

    def _fail(self, detail: str) -> None:
        raise CompetitorAnalysisError("ANALYSIS_GROUNDING_FAILED", f"分析引用不属于当前证据：{detail}")
