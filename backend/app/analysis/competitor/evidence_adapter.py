from app.agent.schemas.evidence import EvidenceType
from app.agent.tools.query_contracts import EvidenceBundle, EvidenceItem
from app.analysis.competitor.evidence import CompetitorEvidenceBuilder
from app.analysis.competitor.schemas import AccountEvidence, CommentEvidence, CompetitorEvidence, NoteEvidence


class CompetitorEvidenceAdapter:
    """把通用 EvidenceBundle 纯确定性转换为 Research 专属 CompetitorEvidence。"""

    def __init__(self, builder: CompetitorEvidenceBuilder | None = None):
        """复用唯一 CompetitorEvidence metrics 与 data-gap Owner。"""
        self.builder = builder or CompetitorEvidenceBuilder()

    def from_bundle(self, bundle: EvidenceBundle) -> CompetitorEvidence:
        """按正式 EvidenceType 分类、去重并验证账号一致性。"""
        accounts: list[AccountEvidence] = []
        notes: list[NoteEvidence] = []
        comments: list[CommentEvidence] = []
        account_ids: set[int] = set()
        seen: set[tuple[EvidenceType, int]] = set()

        for item in bundle.items:
            key = (item.evidence_type, item.evidence_ref.id)
            if key in seen:
                continue
            seen.add(key)
            account_id = self._required_fact(item, "account_id")
            account_ids.add(int(account_id))
            if item.evidence_type == EvidenceType.ACCOUNT:
                accounts.append(self._account(item))
            elif item.evidence_type == EvidenceType.NOTE:
                notes.append(self._note(item))
            elif item.evidence_type == EvidenceType.COMMENT:
                comments.append(self._comment(item))
            else:
                raise ValueError(f"不支持的 Evidence Type: {item.evidence_type}")

        if not account_ids:
            raise ValueError("EvidenceBundle 缺少可信 account_id")
        if len(account_ids) != 1:
            raise ValueError("EvidenceBundle 包含多个 account_id")
        return self.builder.build_from_typed(account_ids.pop(), accounts, notes, comments)

    def _account(self, item: EvidenceItem) -> AccountEvidence:
        facts = item.structured_facts
        return AccountEvidence(
            id=item.evidence_ref.id,
            nickname=self._required_fact(item, "nickname"),
            bio=facts.get("bio"),
            follower_count=facts.get("follower_count"),
            note_count=facts.get("note_count"),
            source_type=self._required_fact(item, "source_type"),
            provider_name=self._required_fact(item, "provider_name"),
        )

    def _note(self, item: EvidenceItem) -> NoteEvidence:
        facts = item.structured_facts
        return NoteEvidence(
            id=item.evidence_ref.id,
            competitor_account_id=facts.get("competitor_account_id"),
            author_name=facts.get("author_name"),
            title=facts.get("title"),
            content=facts.get("body"),
            tags=list(facts.get("tags") or []),
            like_count=self._canonical_count(facts.get("like_count")),
            collect_count=self._canonical_count(facts.get("collect_count")),
            comment_count=self._canonical_count(facts.get("comment_count")),
            note_url=item.source_ref,
            source_type=self._required_fact(item, "source_type"),
            provider_name=self._required_fact(item, "provider_name"),
            ocr_texts=list(facts.get("ocr_texts") or []) if facts.get("ocr_used") is True else [],
        )

    def _comment(self, item: EvidenceItem) -> CommentEvidence:
        facts = item.structured_facts
        return CommentEvidence(
            id=item.evidence_ref.id,
            competitor_note_id=int(self._required_fact(item, "competitor_note_id")),
            content=item.content,
            like_count=self._canonical_count(facts.get("like_count")),
            source_type=self._required_fact(item, "source_type"),
            provider_name=self._required_fact(item, "provider_name"),
        )

    def _required_fact(self, item: EvidenceItem, name: str):
        """拒绝缺失的目标必填事实，不构造占位业务值。"""
        value = item.structured_facts.get(name)
        if value is None or value == "":
            raise ValueError(f"Evidence {item.evidence_ref.type}:{item.evidence_ref.id} 缺少 {name}")
        return value

    def _canonical_count(self, value: int | None) -> int:
        """沿用现有 CompetitorEvidenceBuilder 对 nullable 计数的规范化规则。"""
        return value or 0
