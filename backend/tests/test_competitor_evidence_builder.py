from app.analysis.competitor.evidence import CompetitorEvidenceBuilder
from app.models.competitor_account import CompetitorAccount
from app.models.competitor_comment import CompetitorComment
from app.models.competitor_note import CompetitorNote


def test_evidence_builder_only_contains_real_records_and_metrics():
    """Evidence Builder 排除 Mock，并且只计算事实指标。"""
    real_account = CompetitorAccount(
        id=11,
        account_id=1,
        nickname="真实账号",
        source_type="XHS_MCP",
        provider_name="xiaohongshu_mcp",
        is_mock=False,
    )
    mock_account = CompetitorAccount(
        id=12,
        account_id=1,
        nickname="Mock 账号",
        source_type="SEED_SAMPLE",
        provider_name="seed_sample",
        is_mock=True,
    )
    real_note = CompetitorNote(
        id=21,
        account_id=1,
        competitor_account_id=11,
        title="真实笔记",
        like_count=100,
        collect_count=20,
        comment_count=5,
        source_type="XHS_MCP",
        provider_name="xiaohongshu_mcp",
        is_mock=False,
        raw_snapshot={"image_ocr_texts": ["真实 OCR 文本"]},
    )
    mock_note = CompetitorNote(
        id=22,
        account_id=1,
        title="Mock 笔记",
        source_type="SEED_SAMPLE",
        provider_name="seed_sample",
        is_mock=True,
    )
    real_comment = CompetitorComment(
        id=31,
        account_id=1,
        competitor_note_id=21,
        content="真实评论",
        source_type="XHS_MCP",
        provider_name="xiaohongshu_mcp",
        is_mock=False,
    )
    mock_comment = CompetitorComment(
        id=32,
        account_id=1,
        competitor_note_id=21,
        content="Mock 评论",
        source_type="SEED_SAMPLE",
        provider_name="seed_sample",
        is_mock=True,
    )

    evidence = CompetitorEvidenceBuilder().build(
        1,
        [real_account, mock_account],
        [real_note, mock_note],
        [real_comment, mock_comment],
    )

    assert evidence.used_account_ids == [11]
    assert evidence.used_note_ids == [21]
    assert evidence.used_comment_ids == [31]
    assert evidence.ocr_note_ids == [21]
    assert evidence.computed_metrics.ranked_notes[0].engagement_score == 140
    assert all(item.source_type != "SEED_SAMPLE" for item in [*evidence.accounts, *evidence.notes, *evidence.comments])
