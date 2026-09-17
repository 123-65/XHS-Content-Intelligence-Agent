from app.analysis.competitor.schemas import (
    AccountEvidence,
    CommentEvidence,
    CompetitorEvidence,
    ComputedMetrics,
    NoteEvidence,
    NoteMetricEvidence,
)
from app.models.competitor_account import CompetitorAccount
from app.models.competitor_comment import CompetitorComment
from app.models.competitor_note import CompetitorNote


class CompetitorEvidenceBuilder:
    """把真实数据库记录组装为无语义判断的事实证据。"""

    def build(
        self,
        account_id: int,
        accounts: list[CompetitorAccount],
        notes: list[CompetitorNote],
        comments: list[CompetitorComment],
    ) -> CompetitorEvidence:
        """过滤 Mock、计算数值聚合并记录数据缺口。"""
        real_accounts = [item for item in accounts if not item.is_mock and item.account_id == account_id]
        real_notes = [item for item in notes if not item.is_mock and item.account_id == account_id]
        note_ids = {item.id for item in real_notes}
        real_comments = [
            item
            for item in comments
            if not item.is_mock and item.account_id == account_id and item.competitor_note_id in note_ids
        ]

        account_evidence = [self._account(item) for item in real_accounts]
        note_evidence = [self._note(item) for item in real_notes]
        comment_evidence = [self._comment(item) for item in real_comments]
        ranked_notes = sorted((self._metric(item) for item in note_evidence), key=lambda item: item.engagement_score, reverse=True)
        gaps = self._data_gaps(account_evidence, note_evidence, comment_evidence)
        ocr_note_ids = [item.id for item in note_evidence if item.ocr_texts]

        return CompetitorEvidence(
            account_id=account_id,
            accounts=account_evidence,
            notes=note_evidence,
            comments=comment_evidence,
            computed_metrics=ComputedMetrics(
                note_count=len(note_evidence),
                comment_count=len(comment_evidence),
                account_count=len(account_evidence),
                average_likes=self._average(item.like_count for item in note_evidence),
                average_collects=self._average(item.collect_count for item in note_evidence),
                average_comments=self._average(item.comment_count for item in note_evidence),
                ranked_notes=ranked_notes,
            ),
            used_account_ids=[item.id for item in account_evidence],
            used_note_ids=[item.id for item in note_evidence],
            used_comment_ids=[item.id for item in comment_evidence],
            ocr_note_ids=ocr_note_ids,
            data_gaps=gaps,
        )

    def _account(self, item: CompetitorAccount) -> AccountEvidence:
        return AccountEvidence(
            id=item.id,
            nickname=item.nickname,
            bio=item.bio,
            follower_count=item.follower_count,
            note_count=item.note_count,
            source_type=item.source_type,
            provider_name=item.provider_name,
        )

    def _note(self, item: CompetitorNote) -> NoteEvidence:
        raw = item.raw_snapshot or {}
        ocr_texts = [str(text).strip() for text in raw.get("image_ocr_texts", []) if str(text).strip()]
        return NoteEvidence(
            id=item.id,
            competitor_account_id=item.competitor_account_id,
            author_name=item.author_name,
            title=item.title,
            content=item.content,
            tags=item.tags or [],
            like_count=item.like_count or 0,
            collect_count=item.collect_count or 0,
            comment_count=item.comment_count or 0,
            note_url=item.note_url,
            source_type=item.source_type,
            provider_name=item.provider_name,
            ocr_texts=ocr_texts,
        )

    def _comment(self, item: CompetitorComment) -> CommentEvidence:
        return CommentEvidence(
            id=item.id,
            competitor_note_id=int(item.competitor_note_id),
            content=item.content,
            like_count=item.like_count or 0,
            source_type=item.source_type,
            provider_name=item.provider_name,
        )

    def _metric(self, note: NoteEvidence) -> NoteMetricEvidence:
        return NoteMetricEvidence(
            note_id=note.id,
            like_count=note.like_count,
            collect_count=note.collect_count,
            comment_count=note.comment_count,
            engagement_score=float(note.like_count + note.collect_count * 1.5 + note.comment_count * 2),
        )

    def _data_gaps(
        self,
        accounts: list[AccountEvidence],
        notes: list[NoteEvidence],
        comments: list[CommentEvidence],
    ) -> list[str]:
        gaps = []
        if not accounts:
            gaps.append("未提供真实同行账号资料")
        if not comments:
            gaps.append("未提供真实评论样本")
        if notes and not any(item.ocr_texts for item in notes):
            gaps.append("没有可用的 OCR 文本，无法分析图片内容")
        if notes and any(item.like_count == 0 and item.collect_count == 0 and item.comment_count == 0 for item in notes):
            gaps.append("部分笔记缺少互动指标")
        return gaps

    def _average(self, values) -> float:
        items = list(values)
        return round(sum(items) / len(items), 2) if items else 0.0
