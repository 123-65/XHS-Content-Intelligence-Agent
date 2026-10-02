from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.agent.schemas.evidence import EvidenceRef, EvidenceType
from app.agent.tools.access_scopes import EvidenceAccessScope
from app.agent.tools.query_contracts import RetrieveResearchEvidenceInput
from app.agent.tools.query_tools import QueryToolDataFacade, RetrieveResearchEvidenceTool
from app.agent.tools.semantic_contracts import AnalyzeResearchInput
from app.analysis.competitor.evidence_adapter import CompetitorEvidenceAdapter


BACKEND_ROOT = Path(__file__).resolve().parents[1]
ACCOUNT_REF = EvidenceRef(type=EvidenceType.ACCOUNT, id=10)
NOTE_REF = EvidenceRef(type=EvidenceType.NOTE, id=20)
NOTE_WITHOUT_OCR_REF = EvidenceRef(type=EvidenceType.NOTE, id=21)
COMMENT_REF = EvidenceRef(type=EvidenceType.COMMENT, id=30)


class FakeResearchEvidenceRepository:
    """返回拥有独立原始字段的真实 Evidence 对象。"""

    def __init__(self, account_id=7):
        now = datetime.now(timezone.utc)
        self.account = SimpleNamespace(
            id=10,
            account_id=account_id,
            nickname="Agent 学长",
            bio=None,
            follower_count=None,
            note_count=12,
            source_type="XHS_MCP",
            provider_name="xhs-mcp",
            homepage_url="https://www.xiaohongshu.com/user/profile/10",
            collected_at=now,
        )
        self.notes = {
            20: SimpleNamespace(
                id=20,
                account_id=account_id,
                competitor_account_id=10,
                author_name="Agent 学长",
                title="27届双非如何做 Agent 项目",
                content="这是正文……",
                tags=["Agent", "求职"],
                like_count=100,
                collect_count=40,
                comment_count=8,
                source_type="XHS_MCP",
                provider_name="xhs-mcp",
                note_url="https://www.xiaohongshu.com/explore/20",
                collected_at=now,
                raw_snapshot={"image_ocr_texts": ["架构图文字"]},
            ),
            21: SimpleNamespace(
                id=21,
                account_id=account_id,
                competitor_account_id=10,
                author_name=None,
                title=None,
                content=None,
                tags=[],
                like_count=None,
                collect_count=None,
                comment_count=None,
                source_type="MANUAL",
                provider_name="manual-input",
                note_url="https://www.xiaohongshu.com/explore/21",
                collected_at=now,
                raw_snapshot={},
            ),
        }
        self.comment = SimpleNamespace(
            id=30,
            account_id=account_id,
            competitor_note_id=20,
            content="项目是怎么部署的？",
            like_count=6,
            source_type="XHS_MCP",
            provider_name="xhs-mcp",
            collected_at=now,
        )

    def get_competitor_account(self, object_id):
        return self.account if object_id == self.account.id else None

    def get_competitor_note(self, object_id):
        return self.notes.get(object_id)

    def get_competitor_comment(self, object_id):
        return self.comment if object_id == self.comment.id else None


def _facade(account_id=7):
    facade = QueryToolDataFacade.__new__(QueryToolDataFacade)
    facade.research_evidence = FakeResearchEvidenceRepository(account_id)
    return facade


def _retrieve(*refs, account_id=7):
    scope = EvidenceAccessScope(authorized_refs=frozenset(refs))
    return RetrieveResearchEvidenceTool(facade=_facade(account_id), access_scope=scope).execute(
        RetrieveResearchEvidenceInput(
            account_ref=account_id,
            evidence_refs=list(refs),
            purpose="竞品研究",
        )
    )


def test_retrieval_and_adapter_preserve_independent_note_fields_and_ocr():
    retrieved = _retrieve(NOTE_REF)
    facts = retrieved.data.items[0].structured_facts
    evidence = CompetitorEvidenceAdapter().from_bundle(retrieved.data)
    note = evidence.notes[0]

    assert facts["title"] == "27届双非如何做 Agent 项目"
    assert facts["body"] == "这是正文……"
    assert facts["provider_name"] == "xhs-mcp"
    assert facts["ocr_used"] is True
    assert note.title == "27届双非如何做 Agent 项目"
    assert note.content == "这是正文……"
    assert note.tags == ["Agent", "求职"]
    assert (note.like_count, note.collect_count, note.comment_count) == (100, 40, 8)
    assert (note.source_type, note.provider_name, note.id) == ("XHS_MCP", "xhs-mcp", 20)
    assert note.ocr_texts == ["架构图文字"]
    assert evidence.ocr_note_ids == [20]


def test_account_and_comment_fields_are_not_reconstructed_from_content():
    retrieved = _retrieve(ACCOUNT_REF, COMMENT_REF)
    evidence = CompetitorEvidenceAdapter().from_bundle(retrieved.data)
    account = evidence.accounts[0]
    comment = evidence.comments[0]

    assert (account.nickname, account.bio, account.follower_count, account.note_count) == (
        "Agent 学长",
        None,
        None,
        12,
    )
    assert account.provider_name == "xhs-mcp"
    assert (comment.content, comment.competitor_note_id, comment.like_count) == (
        "项目是怎么部署的？",
        20,
        6,
    )
    assert comment.provider_name == "xhs-mcp"


def test_mixed_bundle_ids_metrics_and_account_are_deterministic():
    retrieved = _retrieve(ACCOUNT_REF, NOTE_REF, COMMENT_REF)
    evidence = CompetitorEvidenceAdapter().from_bundle(retrieved.data)

    assert evidence.account_id == 7
    assert evidence.used_account_ids == [10]
    assert evidence.used_note_ids == [20]
    assert evidence.used_comment_ids == [30]
    assert evidence.computed_metrics.note_count == 1
    assert evidence.computed_metrics.comment_count == 1
    assert evidence.computed_metrics.average_likes == 100
    assert evidence.computed_metrics.ranked_notes[0].engagement_score == 176.0


def test_optional_unknowns_stay_none_and_canonical_counts_follow_existing_builder():
    retrieved = _retrieve(ACCOUNT_REF, NOTE_WITHOUT_OCR_REF)
    evidence = CompetitorEvidenceAdapter().from_bundle(retrieved.data)
    account = evidence.accounts[0]
    note = evidence.notes[0]

    assert account.bio is None
    assert account.follower_count is None
    assert note.title is None and note.content is None and note.author_name is None
    assert (note.like_count, note.collect_count, note.comment_count) == (0, 0, 0)
    assert note.id not in evidence.ocr_note_ids


def test_adapter_rejects_mixed_accounts_and_missing_required_facts():
    first = _retrieve(NOTE_REF).data
    second = _retrieve(COMMENT_REF, account_id=8).data
    mixed = first.model_copy(update={"items": [*first.items, *second.items]})

    with pytest.raises(ValueError, match="多个 account_id"):
        CompetitorEvidenceAdapter().from_bundle(mixed)
    broken = first.model_copy(deep=True)
    broken.items[0].structured_facts.pop("provider_name")
    with pytest.raises(ValueError, match="缺少 provider_name"):
        CompetitorEvidenceAdapter().from_bundle(broken)


def test_retrieval_adapter_and_analyze_contract_connect_without_extra_lookup():
    retrieved = _retrieve(ACCOUNT_REF, NOTE_REF, COMMENT_REF)
    competitor_evidence = CompetitorEvidenceAdapter().from_bundle(retrieved.data)

    semantic_input = AnalyzeResearchInput(
        account_ref=7,
        growth_context={},
        evidence_bundle=competitor_evidence,
        research_goal="分析 Agent 内容机会",
    )

    assert semantic_input.evidence_bundle == competitor_evidence
    assert semantic_input.evidence_bundle.notes[0].title == "27届双非如何做 Agent 项目"


def test_adapter_architecture_is_pure_and_not_a_tool_or_workflow():
    source = (
        BACKEND_ROOT / "app" / "analysis" / "competitor" / "evidence_adapter.py"
    ).read_text(encoding="utf-8")
    forbidden = (
        "app.repositories",
        "sqlalchemy",
        "Session",
        "Provider",
        "fastapi",
        "HTTPException",
        "app.llm",
        "build_tool_handler",
        "app.agent.workflows",
    )
    assert not [token for token in forbidden if token in source]
