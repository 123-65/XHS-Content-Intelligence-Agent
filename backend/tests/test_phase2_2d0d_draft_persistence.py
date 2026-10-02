import inspect
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.models.account import AccountProfile
from app.models.content_draft import ContentDraft
from app.models.content_draft_version import ContentDraftVersion
from app.models.content_experiment import ContentExperiment
from app.models.content_opportunity import ContentOpportunity
from app.models.content_strategy_artifact import ContentStrategyArtifact
from app.repositories.draft_repo import DraftRepository
from app.schemas.draft import DraftContent


class FakeSession:
    """只模拟 DraftRepository 本阶段使用的 Session 行为。"""

    def __init__(self, objects):
        self.objects = {(type(item), item.id): item for item in objects}
        self.next_ids = {ContentDraft: 100, ContentDraftVersion: 200}
        self.commits = 0

    def get(self, model, object_id):
        return self.objects.get((model, object_id))

    def add(self, item):
        if item.id is None:
            item.id = self.next_ids[type(item)]
            self.next_ids[type(item)] += 1
        self.objects[(type(item), item.id)] = item

    def flush(self):
        return None

    def commit(self):
        self.commits += 1

    def refresh(self, item):
        return None

    def rollback(self):
        return None


def _identity_objects():
    account = SimpleNamespace(id=7)
    strategy = SimpleNamespace(id=11, account_id=7, research_artifact_id=31)
    opportunity = SimpleNamespace(
        id=21,
        strategy_artifact_id=11,
        report_id=31,
        content_goal="沉淀真实的 Agent 项目复盘",
    )
    return account, strategy, opportunity


def _repository():
    account, strategy, opportunity = _identity_objects()
    session = FakeSession([])
    session.objects[(AccountProfile, account.id)] = account
    session.objects[(ContentStrategyArtifact, strategy.id)] = strategy
    session.objects[(ContentOpportunity, opportunity.id)] = opportunity
    repository = DraftRepository(session)
    repository.get_latest_version = lambda draft_id: max(
        (
            item
            for (model, _), item in session.objects.items()
            if model is ContentDraftVersion and item.draft_id == draft_id
        ),
        key=lambda item: (item.version, item.id),
        default=None,
    )
    return repository, session


def test_agent_draft_v1_v2_v3_share_one_root_and_keep_identity():
    repository, session = _repository()
    v1_content = DraftContent(title="V1", body="第一版", tags=["Agent"], cta="收藏")
    root, v1 = repository.create_agent_draft_root(
        account_id=7,
        strategy_artifact_id=11,
        opportunity_id=21,
        content_goal="沉淀真实的 Agent 项目复盘",
        content=v1_content,
    )
    identity = (root.account_id, root.strategy_artifact_id, root.opportunity_id, root.content_goal)

    root, v2 = repository.append_agent_draft_version(
        draft_id=root.id,
        parent_version_id=v1.id,
        created_from="REVIEW_REVISION",
        content=DraftContent(title="V2", body="第二版", tags=["Agent", "复盘"]),
    )
    root, v3 = repository.append_agent_draft_version(
        draft_id=root.id,
        parent_version_id=v2.id,
        created_from="USER_REVISION",
        content=DraftContent(title="V3", body="第三版", tags=["Agent", "实战"]),
    )

    assert {v1.draft_id, v2.draft_id, v3.draft_id} == {root.id}
    assert [v1.version, v2.version, v3.version] == [1, 2, 3]
    assert [v1.parent_version_id, v2.parent_version_id, v3.parent_version_id] == [None, v1.id, v2.id]
    assert [v1.created_from, v2.created_from, v3.created_from] == [
        "GENERATED",
        "REVIEW_REVISION",
        "USER_REVISION",
    ]
    assert root.version == 3
    assert root.title == "V3"
    assert (root.account_id, root.strategy_artifact_id, root.opportunity_id, root.content_goal) == identity
    assert session.commits == 0


def test_append_rejects_generated_and_non_latest_parent():
    repository, _ = _repository()
    root, v1 = repository.create_agent_draft_root(
        account_id=7,
        strategy_artifact_id=11,
        opportunity_id=21,
        content_goal="沉淀真实的 Agent 项目复盘",
        content=DraftContent(title="V1", body="第一版"),
    )
    _, v2 = repository.append_agent_draft_version(
        draft_id=root.id,
        parent_version_id=v1.id,
        created_from="REVIEW_REVISION",
        content=DraftContent(title="V2", body="第二版"),
    )

    with pytest.raises(ValueError, match="只允许"):
        repository.append_agent_draft_version(
            draft_id=root.id,
            parent_version_id=v2.id,
            created_from="GENERATED",
            content=DraftContent(title="非法", body="非法追加"),
        )
    with pytest.raises(ValueError, match="latest"):
        repository.append_agent_draft_version(
            draft_id=root.id,
            parent_version_id=v1.id,
            created_from="USER_REVISION",
            content=DraftContent(title="分支", body="不允许分支"),
        )


def test_legacy_create_draft_derives_account_from_experiment():
    experiment = SimpleNamespace(id=301, account_id=7)
    session = FakeSession([])
    session.objects[(ContentExperiment, experiment.id)] = experiment
    repository = DraftRepository(session)
    llm_result = SimpleNamespace(
        usage=SimpleNamespace(prompt_tokens=1, completion_tokens=2, total_tokens=3),
        estimated_cost=0,
        raw_response_id=None,
    )

    draft = repository.create_draft(
        experiment_id=301,
        content=DraftContent(title="Legacy", body="旧链路"),
        version=1,
        status="GENERATED",
        context={},
        llm_result=llm_result,
    )

    assert draft.experiment_id == 301
    assert draft.account_id == 7


def test_migration_preserves_legacy_versions_and_uses_partial_unique_index():
    migration = (
        Path(__file__).resolve().parents[1]
        / "alembic"
        / "versions"
        / "d2e3f4a5b6c7_add_agent_draft_persistence.py"
    ).read_text(encoding="utf-8")

    assert 'postgresql_where=sa.text("created_from IS NOT NULL")' in migration
    assert "DELETE FROM content_draft" not in migration.upper()
    assert "DELETE FROM content_draft_version" not in migration.upper()
    assert "cannot downgrade while New Agent Draft rows exist" in migration


def test_create_agent_draft_root_rejects_strategy_account_mismatch():
    repository, session = _repository()
    session.objects[(ContentStrategyArtifact, 11)].account_id = 8

    with pytest.raises(ValueError, match="不属于当前账号"):
        repository.create_agent_draft_root(
            account_id=7,
            strategy_artifact_id=11,
            opportunity_id=21,
            content_goal="沉淀真实的 Agent 项目复盘",
            content=DraftContent(title="V1", body="第一版"),
        )


def test_create_agent_draft_root_rejects_opportunity_from_other_strategy():
    repository, session = _repository()
    session.objects[(ContentOpportunity, 21)].strategy_artifact_id = 12

    with pytest.raises(ValueError, match="不属于当前 Strategy Artifact"):
        repository.create_agent_draft_root(
            account_id=7,
            strategy_artifact_id=11,
            opportunity_id=21,
            content_goal="沉淀真实的 Agent 项目复盘",
            content=DraftContent(title="V1", body="第一版"),
        )


def test_create_agent_draft_root_rejects_content_goal_mismatch():
    repository, session = _repository()
    session.objects[(ContentOpportunity, 21)].content_goal = "目标 A"

    with pytest.raises(ValueError, match="content_goal 不一致"):
        repository.create_agent_draft_root(
            account_id=7,
            strategy_artifact_id=11,
            opportunity_id=21,
            content_goal="目标 B",
            content=DraftContent(title="V1", body="第一版"),
        )


def test_create_agent_draft_root_rejects_research_lineage_mismatch():
    repository, session = _repository()
    session.objects[(ContentOpportunity, 21)].report_id = 32

    with pytest.raises(ValueError, match="Research lineage 不一致"):
        repository.create_agent_draft_root(
            account_id=7,
            strategy_artifact_id=11,
            opportunity_id=21,
            content_goal="沉淀真实的 Agent 项目复盘",
            content=DraftContent(title="V1", body="第一版"),
        )


def test_append_rejects_parent_version_from_other_draft_root():
    repository, _ = _repository()
    root_a, _ = repository.create_agent_draft_root(
        account_id=7,
        strategy_artifact_id=11,
        opportunity_id=21,
        content_goal="沉淀真实的 Agent 项目复盘",
        content=DraftContent(title="Root A V1", body="A 的第一版"),
    )
    _, v1_b = repository.create_agent_draft_root(
        account_id=7,
        strategy_artifact_id=11,
        opportunity_id=21,
        content_goal="沉淀真实的 Agent 项目复盘",
        content=DraftContent(title="Root B V1", body="B 的第一版"),
    )

    with pytest.raises(ValueError, match="不属于当前 Draft Root"):
        repository.append_agent_draft_version(
            draft_id=root_a.id,
            parent_version_id=v1_b.id,
            created_from="USER_REVISION",
            content=DraftContent(title="非法版本", body="不能跨 Root 追加"),
        )


def test_append_rejects_unknown_created_from():
    repository, _ = _repository()
    root, v1 = repository.create_agent_draft_root(
        account_id=7,
        strategy_artifact_id=11,
        opportunity_id=21,
        content_goal="沉淀真实的 Agent 项目复盘",
        content=DraftContent(title="V1", body="第一版"),
    )

    with pytest.raises(ValueError, match="只允许"):
        repository.append_agent_draft_version(
            draft_id=root.id,
            parent_version_id=v1.id,
            created_from="UNKNOWN",
            content=DraftContent(title="非法版本", body="非法来源"),
        )


def test_append_interface_does_not_allow_root_identity_mutation():
    parameters = inspect.signature(DraftRepository.append_agent_draft_version).parameters

    assert "strategy_artifact_id" not in parameters
    assert "opportunity_id" not in parameters
    assert "content_goal" not in parameters
