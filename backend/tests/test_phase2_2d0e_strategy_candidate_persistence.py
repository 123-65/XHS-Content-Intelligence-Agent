from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.models.review_report import ReviewReport
from app.models.strategy_candidate import StrategyCandidate as StrategyCandidateRecord
from app.repositories.publication_repo import PublicationRepository
from app.schemas.publication import StrategyCandidate


APP_ROOT = Path(__file__).resolve().parents[1] / "app"


class FakeSession:
    """模拟 Candidate Persistence 所需的最小数据库会话。"""

    def __init__(self, report=None):
        self.objects = {}
        if report is not None:
            self.objects[(ReviewReport, report.id)] = report
        self.next_id = 101
        self.memory_writes = 0

    def get(self, model, object_id):
        return self.objects.get((model, object_id))

    def add(self, item):
        if isinstance(item, StrategyCandidateRecord):
            item.id = self.next_id
            self.next_id += 1
            self.objects[(StrategyCandidateRecord, item.id)] = item

    def commit(self):
        return None

    def flush(self):
        return None

    def refresh(self, item):
        return None

    def rollback(self):
        return None


def _candidate(status="PROPOSED"):
    return StrategyCandidate(
        candidate_index=0,
        statement="继续验证清单型内容是否更易被收藏。",
        scope="下一轮内容实验",
        supporting_refs=[{"kind": "public_metric_snapshot", "id": 41}],
        contradicting_refs=[{"kind": "private_metric_snapshot", "id": 51}],
        confidence_context="当前仅有一篇笔记。",
        created_from_review=61,
        status=status,
    )


def _report(account_id=7):
    candidate = _candidate()
    return SimpleNamespace(
        id=61,
        account_id=account_id,
        review_type="POST_PUBLISH_REVIEW_V1",
        published_note_id=31,
        action_suggestions=[candidate.model_dump(mode="json")],
    )


def test_create_candidate_has_stable_database_id_and_complete_content():
    report = _report()
    original_snapshot = deepcopy(report.action_suggestions)
    session = FakeSession(report)
    repository = PublicationRepository(session)

    created = repository.create_strategy_candidate(
        account_id=7,
        review_report_id=61,
        candidate=_candidate(),
    )
    reloaded = repository.get_strategy_candidate(created.id)

    assert created.id == 101
    assert reloaded is created
    assert created.review_report_id == 61
    assert created.account_id == 7
    assert created.source_candidate_index == 0
    assert created.statement == "继续验证清单型内容是否更易被收藏。"
    assert created.scope == "下一轮内容实验"
    assert created.supporting_refs == [{"kind": "public_metric_snapshot", "id": 41}]
    assert created.contradicting_refs == [{"kind": "private_metric_snapshot", "id": 51}]
    assert created.confidence_context == "当前仅有一篇笔记。"
    assert created.status == "PROPOSED"
    assert report.action_suggestions == original_snapshot
    assert session.memory_writes == 0


def test_create_candidate_rejects_review_from_other_account():
    repository = PublicationRepository(FakeSession(_report(account_id=8)))

    with pytest.raises(ValueError, match="不存在或不属于当前账号"):
        repository.create_strategy_candidate(
            account_id=7,
            review_report_id=61,
            candidate=_candidate(),
        )


def test_create_candidate_rejects_missing_review():
    repository = PublicationRepository(FakeSession())

    with pytest.raises(ValueError, match="不存在或不属于当前账号"):
        repository.create_strategy_candidate(
            account_id=7,
            review_report_id=999,
            candidate=_candidate(),
        )


def test_create_candidate_rejects_content_not_in_review_snapshot():
    repository = PublicationRepository(FakeSession(_report()))
    candidate = _candidate().model_copy(update={"statement": "快照中不存在的候选"})

    with pytest.raises(ValueError, match="内容不属于"):
        repository.create_strategy_candidate(
            account_id=7,
            review_report_id=61,
            candidate=candidate,
        )


def test_create_candidate_rejects_non_proposed_status():
    repository = PublicationRepository(FakeSession(_report()))

    with pytest.raises(ValueError, match="必须为 PROPOSED"):
        repository.create_strategy_candidate(
            account_id=7,
            review_report_id=61,
            candidate=_candidate(status="CONFIRMED"),
        )


def test_candidate_architecture_has_no_backfill_second_repository_or_memory_commit():
    migration = (
        Path(__file__).resolve().parents[1]
        / "alembic"
        / "versions"
        / "e3f4a5b6c7d8_add_strategy_candidate_persistence.py"
    ).read_text(encoding="utf-8")
    repository_source = (APP_ROOT / "repositories" / "publication_repo.py").read_text(encoding="utf-8")

    assert "INSERT INTO strategy_candidate" not in migration.upper()
    assert "action_suggestions" not in migration
    assert not (APP_ROOT / "repositories" / "strategy_candidate_repo.py").exists()
    candidate_method = repository_source.split("def create_strategy_candidate", 1)[1].split("def create_package", 1)[0]
    assert "create_memory" not in candidate_method
    assert "StrategyMemoryService" not in candidate_method
