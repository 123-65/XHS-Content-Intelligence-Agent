import pytest

from app.analysis.competitor.engine import CompetitorAnalysisError
from app.analysis.competitor.grounding import CompetitorGroundingValidator
from tests.competitor_analysis_fakes import make_evidence, make_semantic


def test_grounding_accepts_current_evidence_and_data_gaps():
    result = CompetitorGroundingValidator().validate(make_evidence(), make_semantic())

    assert result.data_gaps == ["缺少 OCR 文本"]


def test_grounding_rejects_fabricated_note_id():
    with pytest.raises(CompetitorAnalysisError) as exc_info:
        CompetitorGroundingValidator().validate(make_evidence(), make_semantic(note_id=999))

    assert exc_info.value.code == "ANALYSIS_GROUNDING_FAILED"
    assert "999" in str(exc_info.value)


def test_grounding_rejects_fabricated_comment_id():
    with pytest.raises(CompetitorAnalysisError) as exc_info:
        CompetitorGroundingValidator().validate(make_evidence(), make_semantic(comment_id=999))

    assert exc_info.value.code == "ANALYSIS_GROUNDING_FAILED"
    assert "999" in str(exc_info.value)
