from pathlib import Path
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from app.models.content_opportunity import ContentOpportunity
from app.models.content_strategy_artifact import ContentStrategyArtifact
from app.repositories.content_strategy_repo import ContentStrategyRepository
from app.schemas.content_strategy import ContentStrategyResult


BACKEND_ROOT = Path(__file__).resolve().parents[1]


class FakeSession:
    """模拟 Bundle 写入所需的最小 SQLAlchemy Session 行为。"""

    def __init__(self, account, report, opportunities):
        """保存可供 Repository 校验的账号、报告与机会。"""
        self.account = account
        self.report = report
        self.opportunities = {item.id: item for item in opportunities}
        self.added = []
        self.commits = 0
        self.rollbacks = 0

    def get(self, model, object_id):
        """按 Model 返回测试聚合中的对象。"""
        if model.__name__ == "AccountProfile":
            return self.account if object_id == self.account.id else None
        if model.__name__ == "CompetitorAnalysisReport":
            return self.report if object_id == self.report.id else None
        if model is ContentOpportunity:
            return self.opportunities.get(object_id)
        return None

    def add(self, item):
        """记录待保存的 Artifact。"""
        self.added.append(item)

    def flush(self):
        """为新 Artifact 分配模拟主键。"""
        for item in self.added:
            if isinstance(item, ContentStrategyArtifact) and item.id is None:
                item.id = 501

    def add_all(self, items):
        """记录派生 Opportunity 并分配模拟主键。"""
        for offset, item in enumerate(items, start=601):
            item.id = offset
            self.opportunities[item.id] = item
            self.added.append(item)

    def commit(self):
        """记录原子 Bundle 提交。"""
        self.commits += 1

    def refresh(self, item):
        """模拟刷新已持久化对象。"""
        return None

    def rollback(self):
        """记录写入失败时的事务回滚。"""
        self.rollbacks += 1


def _source(*, object_id=21, report_id=11, target_audience=None, strategy_artifact_id=None):
    """构造字段完整的 Research Opportunity。"""
    return ContentOpportunity(
        id=object_id,
        report_id=report_id,
        strategy_artifact_id=strategy_artifact_id,
        opportunity_title="Agent 项目避坑",
        suggested_angle="真实复盘",
        target_audience=target_audience,
        content_pillar="项目避坑",
        comment_demand_type="PROJECT",
        evidence_summary="样本评论在追问项目落地。",
        replicability_score=82,
        risk_level="MEDIUM",
        risk_points=["不承诺求职结果"],
        opportunity_score=76,
    )


def _result(source_id=21):
    """构造已经 Assembler 合并约束的 Strategy Result。"""
    return ContentStrategyResult(
        account_id=7,
        research_report_id=11,
        strategy_goal="建立真实项目心智",
        target_audience="27 届普通本科生",
        content_directions=[{"direction": "项目避坑", "rationale": "样本有明确需求", "evidence_refs": [{"kind": "research_report", "id": 11}]}],
        rationale="基于 Research 样本得出的建议。",
        evidence_refs=[{"kind": "research_report", "id": 11}],
        applicable_constraints=["不承诺求职结果"],
        opportunities=[{
            "source_opportunity_id": source_id,
            "topic": "Agent 项目避坑",
            "angle": "真实复盘",
            "target_audience": "27 届普通本科生",
            "content_goal": "说清工程误区",
            "why_now": "Research 样本出现相关追问",
            "evidence_refs": [{"kind": "content_opportunity", "id": source_id}],
            "suggested_hook": "别先堆 10 个 Agent",
            "constraints": ["不承诺求职结果", "明确标注样本边界"],
        }],
        provider="fake-provider",
        model="fake-model",
    )


def _repository(source):
    """构造带单一 Research Source 的 Repository。"""
    session = FakeSession(SimpleNamespace(id=7), SimpleNamespace(id=11, account_id=7), [source])
    return ContentStrategyRepository(session), session


def test_existing_research_opportunity_remains_compatible():
    """验证旧 Research Opportunity 不需回填任何 Strategy 字段。"""
    source = _source()
    assert source.report_id == 11
    assert source.strategy_artifact_id is None
    assert source.source_opportunity_id is None
    assert source.content_goal is None


def test_strategy_bundle_persists_artifact_and_complete_derived_opportunity():
    """验证 Bundle 一次保存 Artifact，复制 Source 字段并写入 Strategy 增量语义。"""
    source = _source()
    repository, session = _repository(source)

    artifact, opportunities = repository.create_strategy_bundle(_result())

    generated = opportunities[0]
    assert (artifact.id, artifact.account_id, artifact.research_artifact_id) == (501, 7, 11)
    assert artifact.provider == "fake-provider" and artifact.model == "fake-model"
    assert (generated.report_id, generated.strategy_artifact_id, generated.source_opportunity_id) == (11, 501, 21)
    assert (generated.opportunity_title, generated.suggested_angle, generated.target_audience) == (
        source.opportunity_title,
        source.suggested_angle,
        "27 届普通本科生",
    )
    assert (generated.content_pillar, generated.comment_demand_type, generated.evidence_summary) == (
        source.content_pillar,
        source.comment_demand_type,
        source.evidence_summary,
    )
    assert (generated.replicability_score, generated.risk_level, generated.risk_points, generated.opportunity_score) == (
        82,
        "MEDIUM",
        ["不承诺求职结果"],
        76,
    )
    assert (generated.content_goal, generated.why_now, generated.suggested_hook) == (
        "说清工程误区",
        "Research 样本出现相关追问",
        "别先堆 10 个 Agent",
    )
    assert generated.evidence_refs == [{"kind": "content_opportunity", "id": 21}]
    assert generated.constraints == ["不承诺求职结果", "明确标注样本边界"]
    assert session.commits == 0 and session.rollbacks == 0


def test_source_target_audience_takes_precedence():
    """验证 Source 有目标人群时不被 Strategy 默认值覆盖。"""
    repository, _ = _repository(_source(target_audience="清晰 Source 人群"))
    _, opportunities = repository.create_strategy_bundle(_result())
    assert opportunities[0].target_audience == "清晰 Source 人群"


@pytest.mark.parametrize(
    ("source", "source_id", "message"),
    [
        (_source(object_id=22), 999, "Source Opportunity 不存在"),
        (_source(report_id=12), 21, "不属于当前 Research Artifact"),
        (_source(strategy_artifact_id=400), 21, "不能继续作为派生 Source"),
    ],
)
def test_invalid_source_lineage_is_rejected_before_writing(source, source_id, message):
    """验证未知、跨 Research 或已派生 Source 在写入前被拒绝。"""
    repository, session = _repository(source)
    with pytest.raises(ValueError, match=message):
        repository.create_strategy_bundle(_result(source_id))
    assert session.added == []
    assert session.commits == 0


def test_strategy_result_rejects_missing_incremental_field():
    """验证类型合同在 Repository 之前拒绝缺少的 Strategy 字段。"""
    payload = _result().model_dump()
    del payload["opportunities"][0]["content_goal"]
    with pytest.raises(ValidationError):
        ContentStrategyResult.model_validate(payload)


def test_model_and_migration_freeze_nullable_and_constraint_boundaries():
    """验证 report_id 保持非空，新字段可空且 Migration 含完整性约束。"""
    table = ContentOpportunity.__table__
    assert table.c.report_id.nullable is False
    for name in ("strategy_artifact_id", "source_opportunity_id", "content_goal", "why_now", "suggested_hook", "evidence_refs", "constraints"):
        assert table.c[name].nullable is True
    constraints = {item.name for item in table.constraints}
    assert "ck_content_opportunity_strategy_fields_complete" in constraints
    migration = (BACKEND_ROOT / "alembic" / "versions" / "c1d2e3f4a5b6_add_content_strategy_persistence.py").read_text(encoding="utf-8")
    assert "alter_column" not in migration
    assert 'add_column("content_opportunity", sa.Column("report_id"' not in migration
    assert "ck_content_opportunity_strategy_fields_complete" in migration


def test_strategy_persistence_does_not_use_experiment_or_generic_artifact():
    """验证新持久化路径不复活 Experiment 或通用 Artifact 系统。"""
    source = (BACKEND_ROOT / "app" / "repositories" / "content_strategy_repo.py").read_text(encoding="utf-8")
    forbidden = ("ContentExperiment", "ExperimentVariable", "ExperimentMetricTarget", "GenericArtifact", "ArtifactService")
    assert not [token for token in forbidden if token in source]
