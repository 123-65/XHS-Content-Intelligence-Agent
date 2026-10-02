from pathlib import Path

from app.analysis.competitor.llm_analyzer import LLMStructuredCompetitorAnalyzer
from app.services.competitor_report_sev import CompetitorReportService
from evals.baselines.research_rule_baseline import RuleBaselineCompetitorAnalyzer
from tests.competitor_analysis_fakes import make_evidence


BACKEND_ROOT = Path(__file__).resolve().parents[1]
APP_ROOT = BACKEND_ROOT / "app"


def _python_sources(root: Path):
    return root.rglob("*.py")


def test_production_does_not_import_evals_or_rule_baseline():
    forbidden = (
        "evals.baselines",
        "backend.evals",
        "analysis.competitor.rule_baseline",
        "RuleBaselineCompetitorAnalyzer",
    )
    offenders = []
    for path in _python_sources(APP_ROOT):
        text = path.read_text(encoding="utf-8")
        if any(token in text for token in forbidden):
            offenders.append(str(path.relative_to(BACKEND_ROOT)))
    assert offenders == []


def test_production_research_resolves_only_structured_llm():
    analyzer = CompetitorReportService(None)._resolve_analyzer()
    assert isinstance(analyzer, LLMStructuredCompetitorAnalyzer)
    assert analyzer.analysis_engine == "LLM_STRUCTURED_V1"


def test_rule_baseline_runs_independently_in_eval_namespace():
    result = RuleBaselineCompetitorAnalyzer().analyze(make_evidence())
    assert result.persona.positioning
    assert result.data_gaps


def test_new_agent_workflow_and_tools_do_not_depend_on_legacy_collectors():
    roots = [APP_ROOT / "agent", APP_ROOT / "workflow"]
    forbidden = (
        "XhsUrlCollectService",
        "CrawlerCollectionService",
        "app.crawler.providers",
        "SimpleHttpXhsProvider",
    )
    offenders = []
    for root in roots:
        if not root.exists():
            continue
        for path in _python_sources(root):
            text = path.read_text(encoding="utf-8")
            if any(token in text for token in forbidden):
                offenders.append(str(path.relative_to(BACKEND_ROOT)))
    assert offenders == []


def test_canonical_collector_does_not_fallback_to_legacy_collectors():
    paths = [
        APP_ROOT / "services" / "xhs_collector_sev.py",
        APP_ROOT / "collectors" / "xhs" / "xiaohongshu_mcp_provider.py",
        APP_ROOT / "collectors" / "xhs" / "normalizer.py",
        APP_ROOT / "collectors" / "xhs" / "base.py",
        APP_ROOT / "collectors" / "xhs" / "provider_types.py",
    ]
    forbidden = (
        "XhsUrlCollectService",
        "CrawlerCollectionService",
        "app.crawler.providers",
        "SimpleHttpXhsProvider",
    )
    offenders = []
    for path in paths:
        text = path.read_text(encoding="utf-8")
        if any(token in text for token in forbidden):
            offenders.append(str(path.relative_to(BACKEND_ROOT)))
    assert offenders == []
