from pathlib import Path
from types import SimpleNamespace

import pytest

from app.models.content_experiment import ContentExperiment
from app.models.content_opportunity import ContentOpportunity
from app.models.experiment_metric_target import ExperimentMetricTarget
from app.models.experiment_variable import ExperimentVariable
from app.models.viral_note_breakdown import ViralNoteBreakdown
from app.schemas.content_strategy import ContentStrategyRequest
from app.services.content_strategy_sev import ContentStrategyService


BACKEND_ROOT = Path(__file__).resolve().parents[1]
APP_ROOT = BACKEND_ROOT / "app"

REMOVED_EXPERIMENT_OWNERS = (
    "services/content_experiment_sev.py",
    "services/content_experiment_v2_sev.py",
    "services/operation_experiment_sev.py",
    "repositories/content_experiment_repo.py",
    "repositories/content_experiment_v2_repo.py",
    "api/content_experiment_rout.py",
    "api/content_experiment_v2_rout.py",
    "api/operation_experiment.py",
)


class FakeRepository:
    def __init__(self):
        self.account = SimpleNamespace(
            id=7,
            positioning="Agent 项目求职内容",
            target_audience="27 届普通本科生",
            content_domain="AI 求职",
            primary_goal="lead",
            business_model="consulting",
            main_product="Agent 项目辅导",
            tone_preference="真实、克制",
            account_stage="STARTUP",
        )
        self.report = SimpleNamespace(
            id=11,
            account_id=7,
            status="SUCCESS",
            summary="样本中多次出现项目落地和求职焦虑。",
            content_insights=["真实避坑内容收藏意图较强"],
            comment_demands=[{"demand": "项目如何写进简历"}],
            risk_points=[{"risk": "避免夸大就业效果"}],
            competitor_note_ids=[101, 102],
        )
        self.opportunities = [
            ContentOpportunity(
                id=21,
                report_id=11,
                opportunity_title="双非 27 届做 Agent 项目最容易踩的 5 个坑",
                suggested_angle="真实项目复盘",
                target_audience="27 届普通本科生",
                content_pillar="项目避坑",
                comment_demand_type="PROJECT",
                evidence_summary="两篇样本的评论都在追问项目落地。",
                risk_points=["不承诺求职结果"],
                opportunity_score=86,
            )
        ]

    def get_account(self, account_id):
        return self.account if account_id == self.account.id else None

    def get_report(self, report_id):
        return self.report if report_id == self.report.id else None

    def list_opportunities(self, report_id, limit):
        return self.opportunities[:limit] if report_id == self.report.id else []


class FakeLLMClient:
    provider = "fake-provider"
    model = "fake-model"

    def __init__(self, data):
        self.data = data
        self.calls = []

    def generate_structured(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(data=self.data)

    def record_business_validation_failure(self, exc, candidate, **kwargs):
        self.calls.append({"validation_error": exc, "candidate": candidate, **kwargs})


def _generated_strategy(evidence_id: int = 101, opportunity_id: int = 21) -> dict:
    report_ref = {"kind": "research_report", "id": 11}
    note_ref = {"kind": "competitor_note", "id": evidence_id}
    opportunity_ref = {"kind": "content_opportunity", "id": opportunity_id}
    return {
        "strategy_goal": "建立真实 Agent 项目落地心智",
        "target_audience": "27 届普通本科生",
        "content_directions": [
            {
                "direction": "Agent 项目避坑",
                "rationale": "样本评论展示了明确的项目落地疑问。",
                "evidence_refs": [report_ref, note_ref],
            }
        ],
        "rationale": "这是基于当前样本的内容建议，不是结果预测。",
        "evidence_refs": [report_ref, note_ref],
        "applicable_constraints": ["不承诺求职结果"],
        "opportunities": [
            {
                "source_opportunity_id": opportunity_id,
                "content_goal": "解释项目中的常见工程误区",
                "why_now": "当前 Research 样本中已出现相关追问",
                "suggested_hook": "做 Agent 项目时，别先堆 10 个 Agent",
                "evidence_refs": [opportunity_ref, note_ref],
                "constraints": ["明确标注为样本观察"],
            }
        ],
    }


def _service(data: dict) -> tuple[ContentStrategyService, FakeLLMClient]:
    client = FakeLLMClient(data)
    return ContentStrategyService(None, llm_client=client, repository=FakeRepository()), client


def _semantic_payload(opportunity_id=200):
    return {
        "account_ref": 7,
        "growth_context": {},
        "research_result": {"artifact_ref": {"type": "RESEARCH", "id": 100}},
        "historical_opportunities": [
            {"source_opportunity_id": opportunity_id, "topic": "可信选题", "evidence_summary": "可信研究机会"}
        ],
        "strategy_memory": [],
        "evidence_refs": [{"kind": "research_report", "id": 100}],
        "constraints": [],
    }


def _semantic_output(evidence_kind="content_opportunity", evidence_id=200):
    ref = {"kind": evidence_kind, "id": evidence_id}
    return {
        "strategy_goal": "确定选题",
        "target_audience": "学生",
        "content_directions": [{"direction": "方向", "rationale": "依据", "evidence_refs": [ref]}],
        "rationale": "基于可信输入",
        "evidence_refs": [ref],
        "applicable_constraints": [],
        "opportunities": [{
            "source_opportunity_id": 200,
            "content_goal": "目标",
            "why_now": "现在",
            "suggested_hook": "开头",
            "evidence_refs": [ref],
            "constraints": [],
        }],
    }


def test_semantic_strategy_authorizes_only_canonical_opportunities_in_current_input():
    valid_service, _ = _service(_semantic_output(evidence_id=200))
    result = valid_service.generate_semantic(_semantic_payload(200))
    assert result.evidence_refs[0].model_dump() == {"kind": "content_opportunity", "id": 200}

    for unauthorized in (300, 400, 999):
        service, client = _service(_semantic_output(evidence_id=unauthorized))
        with pytest.raises(ValueError, match="无效 EvidenceRefs"):
            service.generate_semantic(_semantic_payload(200))
        assert client.calls[-1]["validation_layer"] == "POST_PARSE_BUSINESS_VALIDATION"


def test_semantic_strategy_keeps_research_report_authorized():
    service, _ = _service(_semantic_output("research_report", 100))
    assert service.generate_semantic(_semantic_payload(200)).evidence_refs[0].id == 100


def test_research_context_generates_valid_strategy_and_opportunity():
    service, client = _service(_generated_strategy())

    result = service.generate(ContentStrategyRequest(account_id=7, research_report_id=11))

    assert result.strategy_goal == "建立真实 Agent 项目落地心智"
    assert result.provider == "fake-provider"
    assert result.opportunities[0].topic.startswith("双非 27 届")
    assert result.opportunities[0].angle == "真实项目复盘"
    assert result.opportunities[0].constraints == ["不承诺求职结果", "明确标注为样本观察"]
    assert client.calls[0]["schema_model"].__name__ == "GeneratedContentStrategy"
    assert client.calls[0]["prompt_key"] == "content_strategy"


def test_strategy_rejects_invented_evidence_ref():
    service, _ = _service(_generated_strategy(evidence_id=999))

    with pytest.raises(ValueError, match="无效 EvidenceRefs"):
        service.generate(ContentStrategyRequest(account_id=7, research_report_id=11))


def test_strategy_rejects_unknown_opportunity():
    service, _ = _service(_generated_strategy(opportunity_id=999))

    with pytest.raises(ValueError, match="未提供的 Content Opportunity"):
        service.generate(ContentStrategyRequest(account_id=7, research_report_id=11))


def test_content_strategy_is_the_only_production_owner():
    owners = []
    for path in APP_ROOT.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        if "class ContentStrategyService" in text:
            owners.append(path.relative_to(APP_ROOT).as_posix())
    assert owners == ["services/content_strategy_sev.py"]
    assert all(not (APP_ROOT / path).exists() for path in REMOVED_EXPERIMENT_OWNERS)


def test_strategy_has_no_experiment_or_direct_provider_dependency():
    source = (APP_ROOT / "services" / "content_strategy_sev.py").read_text(encoding="utf-8")
    assert "experiment_variable" not in source
    assert "experiment_metric_target" not in source
    assert "ContentExperiment" not in source
    assert "StrategyAgent" not in source
    assert "app.llm.providers" not in source
    assert "from app.llm.client import LLMClient" in source


def test_historical_strategy_related_tables_are_preserved():
    assert ContentOpportunity.__tablename__ == "content_opportunity"
    assert ContentExperiment.__tablename__ == "content_experiment"
    assert ExperimentVariable.__tablename__ == "experiment_variable"
    assert ExperimentMetricTarget.__tablename__ == "experiment_metric_target"
    assert ViralNoteBreakdown.__tablename__ == "viral_note_breakdown"
