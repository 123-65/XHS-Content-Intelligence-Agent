from fastapi.testclient import TestClient

from app.core.database import SessionLocal
from app.main import app
from app.models.memory_evidence import MemoryEvidence
from app.models.review_report import ReviewReport
from app.models.strategy_memory import StrategyMemory
from tests.test_draft_context_preview_api import _create_experiment as _create_b7_experiment
from tests.test_draft_context_preview_api import _create_report_graph
from tests.test_post_publish_review_api import _create_backfilled_note, _review, _set_target


def _client() -> TestClient:
    return TestClient(app)


def _create_hit_review(monkeypatch) -> tuple[int, int, int, int, int, int]:
    account_id, experiment_id, draft_id, package_id, note_id = _create_backfilled_note(
        monkeypatch,
        like_count=10,
        collect_count=8,
        comment_count=2,
        share_count=1,
        follower_gain=3,
        lead_count=2,
    )
    _set_target(experiment_id, "collect", {"collect_count": 5})
    response = _review(note_id, account_id)
    assert response.status_code == 200
    review_id = response.json()["review_id"]
    return account_id, experiment_id, draft_id, package_id, note_id, review_id


def _create_unknown_target_review(monkeypatch) -> tuple[int, int]:
    account_id, experiment_id, _, _, note_id = _create_backfilled_note(monkeypatch)
    _set_target(experiment_id, "collect", {})
    response = _review(note_id, account_id)
    assert response.status_code == 200
    return account_id, response.json()["review_id"]


def _confirm(review_id: int, account_id: int, confirmed: bool = True, selected_candidates: list[dict] | None = None, **extra):
    payload = {
        "account_id": account_id,
        "confirmed": confirmed,
        "selected_candidates": selected_candidates
        if selected_candidates is not None
        else [
            {
                "candidate_index": 0,
                "memory_type": "CONTENT_DIRECTION",
                "content": "Confirmed content direction from manual post-publish signal.",
                "evidence": "collect actual=8, target=5",
                "confidence": "MEDIUM",
            }
        ],
    }
    payload.update(extra)
    return _client().post(f"/agent/post-publish-reviews/{review_id}/strategy-memories/confirm", json=payload)


def _counts() -> dict[str, int]:
    with SessionLocal() as db:
        return {
            "review_reports": db.query(ReviewReport).count(),
            "strategy_memory": db.query(StrategyMemory).count(),
            "memory_evidence": db.query(MemoryEvidence).count(),
        }


def _memory(memory_id: int) -> StrategyMemory:
    with SessionLocal() as db:
        memory = db.get(StrategyMemory, memory_id)
        assert memory is not None
        db.expunge(memory)
        return memory


def test_confirmed_false_does_not_write_strategy_memory(monkeypatch):
    account_id, _, _, _, _, review_id = _create_hit_review(monkeypatch)
    before = _counts()

    response = _confirm(review_id, account_id, confirmed=False)

    data = response.json()
    assert response.status_code == 200
    assert data["status"] == "WAITING_CONFIRMATION"
    assert data["created_memory_ids"] == []
    assert _counts() == before


def test_review_not_found_returns_404_without_side_effects():
    before = _counts()

    response = _confirm(999999999, 1)

    assert response.status_code == 404
    assert response.json()["detail"] == "post publish review not found"
    assert _counts() == before


def test_non_b14_review_returns_blocked(monkeypatch):
    account_id, experiment_id, draft_id, _, note_id, _ = _create_hit_review(monkeypatch)
    with SessionLocal() as db:
        report = ReviewReport(
            draft_id=draft_id,
            account_id=account_id,
            experiment_id=experiment_id,
            published_note_id=note_id,
            review_type="CONTENT_REVIEW",
            result_status="PASS",
            status="SUCCESS",
            summary="not b14",
        )
        db.add(report)
        db.commit()
        db.refresh(report)
        review_id = report.id
    before = _counts()

    response = _confirm(review_id, account_id)

    data = response.json()
    assert response.status_code == 200
    assert data["status"] == "BLOCKED"
    assert data["error_code"] == "INVALID_REVIEW_TYPE"
    assert _counts() == before


def test_account_mismatch_returns_400_without_memory(monkeypatch):
    account_id, _, _, _, _, review_id = _create_hit_review(monkeypatch)
    before = _counts()

    response = _confirm(review_id, account_id + 999)

    assert response.status_code == 400
    assert response.json()["detail"] == "review account_id does not match"
    assert _counts() == before


def test_review_without_candidates_returns_data_insufficient(monkeypatch):
    account_id, review_id = _create_unknown_target_review(monkeypatch)
    before = _counts()

    response = _confirm(review_id, account_id)

    data = response.json()
    assert response.status_code == 200
    assert data["status"] == "DATA_INSUFFICIENT"
    assert data["error_code"] == "NO_STRATEGY_MEMORY_CANDIDATES"
    assert _counts() == before


def test_empty_selected_candidates_returns_data_insufficient(monkeypatch):
    account_id, _, _, _, _, review_id = _create_hit_review(monkeypatch)
    before = _counts()

    response = _confirm(review_id, account_id, selected_candidates=[])

    data = response.json()
    assert response.status_code == 200
    assert data["status"] == "DATA_INSUFFICIENT"
    assert data["error_code"] == "NO_SELECTED_CANDIDATES"
    assert _counts() == before


def test_candidate_index_out_of_range_returns_validation_error(monkeypatch):
    account_id, _, _, _, _, review_id = _create_hit_review(monkeypatch)

    response = _confirm(
        review_id,
        account_id,
        selected_candidates=[
            {
                "candidate_index": 999,
                "memory_type": "CONTENT_DIRECTION",
                "content": "valid content",
                "evidence": "valid evidence",
                "confidence": "MEDIUM",
            }
        ],
    )

    assert response.status_code == 200
    assert response.json()["status"] == "VALIDATION_ERROR"
    assert response.json()["error_code"] == "CANDIDATE_INDEX_OUT_OF_RANGE"


def test_empty_content_returns_validation_error(monkeypatch):
    account_id, _, _, _, _, review_id = _create_hit_review(monkeypatch)

    response = _confirm(
        review_id,
        account_id,
        selected_candidates=[
            {
                "candidate_index": 0,
                "memory_type": "CONTENT_DIRECTION",
                "content": "   ",
                "evidence": "valid evidence",
                "confidence": "MEDIUM",
            }
        ],
    )

    assert response.status_code == 200
    assert response.json()["status"] == "VALIDATION_ERROR"
    assert response.json()["error_code"] == "EMPTY_CONTENT"


def test_invalid_confidence_returns_validation_error(monkeypatch):
    account_id, _, _, _, _, review_id = _create_hit_review(monkeypatch)

    response = _confirm(
        review_id,
        account_id,
        selected_candidates=[
            {
                "candidate_index": 0,
                "memory_type": "CONTENT_DIRECTION",
                "content": "valid content",
                "evidence": "valid evidence",
                "confidence": "CERTAIN",
            }
        ],
    )

    assert response.status_code == 200
    assert response.json()["status"] == "VALIDATION_ERROR"
    assert response.json()["error_code"] == "INVALID_CONFIDENCE"


def test_confirm_creates_strategy_memory_with_provenance(monkeypatch):
    account_id, _, _, package_id, note_id, review_id = _create_hit_review(monkeypatch)
    before = _counts()

    response = _confirm(review_id, account_id)

    data = response.json()
    assert response.status_code == 200
    assert data["status"] == "SAVED"
    assert len(data["created_memory_ids"]) == 1
    after = _counts()
    assert after["strategy_memory"] == before["strategy_memory"] + 1
    assert after["memory_evidence"] == before["memory_evidence"] + 1
    assert after["review_reports"] == before["review_reports"]
    memory = _memory(data["created_memory_ids"][0])
    assert memory.account_id == account_id
    assert memory.memory_type == "CONTENT_DIRECTION"
    assert memory.status == "VALIDATED"
    assert memory.source_review_report_id == review_id
    assert memory.metadata_payload["source_type"] == "POST_PUBLISH_REVIEW_V0"
    assert memory.metadata_payload["source_review_id"] == review_id
    assert memory.metadata_payload["source_published_note_id"] == note_id
    assert memory.metadata_payload["source_package_id"] == package_id
    assert memory.metadata_payload["source_candidate_index"] == 0


def test_duplicate_confirmation_skips_existing_memory(monkeypatch):
    account_id, _, _, _, _, review_id = _create_hit_review(monkeypatch)
    first = _confirm(review_id, account_id).json()
    before = _counts()

    response = _confirm(review_id, account_id)

    data = response.json()
    assert response.status_code == 200
    assert data["status"] == "SAVED"
    assert data["created_memory_ids"] == []
    assert data["skipped_duplicates"][0]["memory_id"] == first["created_memory_ids"][0]
    assert _counts() == before


def test_unselected_candidate_is_not_written(monkeypatch):
    account_id, _, _, _, _, review_id = _create_hit_review(monkeypatch)

    response = _confirm(review_id, account_id)

    data = response.json()
    assert response.status_code == 200
    assert len(data["candidates"]) == 2
    assert len(data["created_memory_ids"]) == 1
    with SessionLocal() as db:
        memories = db.query(StrategyMemory).filter(StrategyMemory.source_review_report_id == review_id).all()
        assert len(memories) == 1
        assert memories[0].metadata_payload["source_candidate_index"] == 0


def test_confirm_updates_current_state(monkeypatch):
    account_id, _, _, _, _, review_id = _create_hit_review(monkeypatch)
    conversation = _client().post("/agent/conversations", json={"account_id": account_id}).json()

    response = _confirm(review_id, account_id, conversation_id=conversation["id"])

    data = response.json()
    assert response.status_code == 200
    state = _client().get(f"/agent/conversations/{conversation['id']}/state").json()
    assert state["active_account_id"] == account_id
    assert state["current_target_type"] == "STRATEGY_MEMORY"
    assert state["current_target_id"] == data["created_memory_ids"][-1]
    assert state["last_action"] == "CONFIRM_STRATEGY_MEMORY"


def test_b15_does_not_call_forbidden_workflows(monkeypatch):
    account_id, _, _, _, _, review_id = _create_hit_review(monkeypatch)
    before = _counts()

    def forbidden_call(*args, **kwargs):
        raise AssertionError("B15 must not call LLM, external, publish, comment, review generation, or old memory extraction")

    monkeypatch.setattr("app.llm.client.LLMClient.__init__", forbidden_call, raising=False)
    monkeypatch.setattr("app.services.post_publish_sev.PostPublishService.extract_memories", forbidden_call, raising=False)
    monkeypatch.setattr("app.services.post_publish_review_v0_sev.PostPublishReviewV0Service.create_review", forbidden_call, raising=False)
    monkeypatch.setattr("app.services.evidence_refresh_run_sev.EvidenceRefreshRunService.create_run", forbidden_call)
    monkeypatch.setattr("app.services.operation_run_sev.OperationRunService.create_run", forbidden_call)
    monkeypatch.setattr("app.services.content_draft_v2_sev.ContentDraftV2Service.generate_draft", forbidden_call)
    monkeypatch.setattr("app.repositories.post_publish_repo.PostPublishRepository.create_strategy_memory", forbidden_call, raising=False)

    response = _confirm(review_id, account_id)

    assert response.status_code == 200
    after = _counts()
    assert after["strategy_memory"] == before["strategy_memory"] + 1
    assert after["review_reports"] == before["review_reports"]


def test_b7_draft_context_preview_can_read_confirmed_memory(monkeypatch):
    account_id, _, _, _, _, review_id = _create_hit_review(monkeypatch)
    created_memory_id = _confirm(review_id, account_id).json()["created_memory_ids"][0]
    graph = _create_report_graph(account_id)
    experiment_id = _create_b7_experiment(account_id, graph["report_id"], graph["opportunity_id"], status="READY")

    response = _client().post(
        f"/agent/content-experiments/{experiment_id}/draft-context/preview",
        json={"account_id": account_id, "include_strategy_memory": True, "include_comments": True},
    )

    data = response.json()
    assert response.status_code == 200
    assert data["status"] == "READY"
    memory_ids = [item["memory_id"] for item in data["context"]["strategy_memories"]]
    assert created_memory_id in memory_ids


def test_get_candidates_and_list_memories(monkeypatch):
    account_id, _, _, _, _, review_id = _create_hit_review(monkeypatch)
    candidates = _client().get(f"/agent/post-publish-reviews/{review_id}/strategy-memory-candidates")
    created = _confirm(review_id, account_id).json()
    listed = _client().get(f"/agent/accounts/{account_id}/strategy-memories")

    assert candidates.status_code == 200
    assert candidates.json()["status"] == "WAITING_CONFIRMATION"
    assert len(candidates.json()["candidates"]) == 2
    assert listed.status_code == 200
    assert any(item["id"] == created["created_memory_ids"][0] for item in listed.json())
