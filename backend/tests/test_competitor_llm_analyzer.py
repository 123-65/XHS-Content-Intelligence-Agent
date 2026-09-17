from pathlib import Path

import pytest

from app.analysis.competitor.engine import CompetitorAnalysisError
from app.analysis.competitor.llm_analyzer import LLMStructuredCompetitorAnalyzer
from app.analysis.competitor.rule_baseline import RuleBaselineCompetitorAnalyzer
from app.analysis.competitor.schemas import CompetitorSemanticResult
from app.llm.errors import LLMError, LLMSchemaValidationError
from app.schemas.competitor_report import CompetitorReportCreate
from app.services.competitor_report_sev import CompetitorReportService
from tests.competitor_analysis_fakes import FakeCompetitorLLMClient, make_evidence


def test_llm_analyzer_uses_unified_client_and_structured_schema():
    client = FakeCompetitorLLMClient()

    result = LLMStructuredCompetitorAnalyzer(client).analyze(make_evidence())

    assert result.persona.positioning == "企业 AI 落地与交付知识账号"
    assert client.calls[0]["schema_model"] is CompetitorSemanticResult
    assert client.calls[0]["prompt_key"] == "competitor_semantic_analysis"
    assert "不可信证据" in client.calls[0]["system_prompt"]
    assert "没有可用的 OCR" in client.calls[0]["prompt"]


def test_llm_analyzer_maps_schema_failure():
    class InvalidSchemaClient:
        def generate_structured(self, *args, **kwargs):
            raise LLMSchemaValidationError("invalid structured output")

    with pytest.raises(CompetitorAnalysisError) as exc_info:
        LLMStructuredCompetitorAnalyzer(InvalidSchemaClient()).analyze(make_evidence())

    assert exc_info.value.code == "ANALYSIS_SCHEMA_INVALID"


def test_llm_analyzer_maps_provider_failure_without_rule_fallback():
    class FailedProviderClient:
        def generate_structured(self, *args, **kwargs):
            raise LLMError("provider unavailable")

    with pytest.raises(CompetitorAnalysisError) as exc_info:
        LLMStructuredCompetitorAnalyzer(FailedProviderClient()).analyze(make_evidence())

    assert exc_info.value.code == "ANALYSIS_PROVIDER_FAILED"


def test_production_default_is_llm_and_rule_baseline_is_explicit():
    request = CompetitorReportCreate(account_id=1, name="test")
    service = CompetitorReportService(None)

    assert request.analysis_engine == "LLM_STRUCTURED_V1"
    assert service.analysis_engine == "LLM_STRUCTURED_V1"
    assert isinstance(service._resolve_analyzer("RULE_BASELINE"), RuleBaselineCompetitorAnalyzer)
    assert service._resolve_analyzer("LLM_STRUCTURED_V1").analysis_engine == "LLM_STRUCTURED_V1"


def test_business_and_api_modules_do_not_import_provider_sdks():
    root = Path(__file__).resolve().parents[1] / "app"
    forbidden = ("from openai", "import openai", "import dashscope", "from dashscope")
    offenders = []
    for folder in (root / "services", root / "api"):
        for path in folder.glob("*.py"):
            text = path.read_text(encoding="utf-8").lower()
            if any(item in text for item in forbidden):
                offenders.append(str(path))
    assert offenders == []
