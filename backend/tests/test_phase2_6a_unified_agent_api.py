from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.agent.control.conversation_context import ConversationTurnContextOwner
from app.agent.control.turn_contracts import TurnContextState
from app.agent.schemas.execution import AgentTurnResult, RuntimeAction, WorkflowStatus
from app.agent.schemas.semantic import Intent
from app.api.unified_agent import get_unified_agent_service
from app.core.database import SessionLocal
from app.main import app
from app.models.account import AccountProfile
from app.schemas.agent_conversation import ConversationCreate
from app.schemas.unified_agent import AgentRunResponse, AgentTurnRequest, AgentTurnResponse
from app.services.agent_conversation_sev import AgentConversationService
from app.services.unified_agent_sev import UnifiedAgentError, UnifiedAgentService


class FakeOrchestrator:
    def __init__(self, result=None):
        self.calls = []
        self.result = result or AgentTurnResult(action=RuntimeAction.RESPOND, intent=Intent.GENERAL_CHAT, message="你好", status=WorkflowStatus.SUCCESS)

    def handle_turn(self, turn, execution_context, workspace_selection=None):
        self.calls.append((turn, execution_context, workspace_selection))
        return self.result


class FakeRuntime:
    def __init__(self, result): self.result = result; self.get_calls = []
    def get_run(self, run_ref): self.get_calls.append(run_ref); return self.result


@pytest.fixture
def accounts():
    with SessionLocal() as db:
        first = AccountProfile(account_name="Unified A", positioning="A", target_audience="A")
        second = AccountProfile(account_name="Unified B", positioning="B", target_audience="B")
        db.add_all([first, second]); db.commit(); db.refresh(first); db.refresh(second)
        return first.id, second.id


def request(account, **updates):
    value = {"account_ref": account, "text": "你好", "client_request_id": "req-1"}
    value.update(updates)
    return AgentTurnRequest(**value)


def test_service_creates_persistent_conversation_and_calls_only_orchestrator(accounts):
    with SessionLocal() as db:
        orchestrator = FakeOrchestrator()
        service = UnifiedAgentService(db, orchestrator=orchestrator, runtime=FakeRuntime(None))
        response = service.handle_turn(request(accounts[0]))
        conversation = AgentConversationService(db).get_conversation(response.conversation_id)
        messages = AgentConversationService(db).list_messages(response.conversation_id)
        assert conversation.account_id == accounts[0]
        assert response.turn.action == RuntimeAction.RESPOND
        assert len(orchestrator.calls) == 1
        assert [item.role for item in messages] == ["USER", "ASSISTANT"]


def test_service_normalizes_plain_chat_url_before_orchestrator_and_collection_scope(accounts):
    url = "https://www.xiaohongshu.com/explore/note-1?xsec_token=keep&xsec_source=pc_search&source=feed"
    with SessionLocal() as db:
        orchestrator = FakeOrchestrator()
        service = UnifiedAgentService(db, orchestrator=orchestrator, runtime=FakeRuntime(None))
        service.handle_turn(request(accounts[0], text=f"分析这篇：\n{url}", client_request_id="raw-material-1"))

        turn, context, _ = orchestrator.calls[0]
        assert turn.note_urls == [url]
        assert turn.profile_urls == []
        assert context.collection_access_scope.allowed_note_urls == (url,)


def test_same_client_request_id_replays_without_second_orchestrator_call(accounts):
    with SessionLocal() as db:
        orchestrator = FakeOrchestrator()
        service = UnifiedAgentService(db, orchestrator=orchestrator, runtime=FakeRuntime(None))
        first = service.handle_turn(request(accounts[0], client_request_id="same-1"))
        second = service.handle_turn(request(accounts[0], client_request_id="same-1"))
        assert first == second
        assert len(orchestrator.calls) == 1


def test_same_request_id_with_different_payload_is_rejected(accounts):
    with SessionLocal() as db:
        service = UnifiedAgentService(db, orchestrator=FakeOrchestrator(), runtime=FakeRuntime(None))
        service.handle_turn(request(accounts[0], client_request_id="mismatch-1"))
        with pytest.raises(UnifiedAgentError) as exc:
            service.handle_turn(request(accounts[0], client_request_id="mismatch-1", text="不同内容"))
        assert exc.value.code == "REQUEST_IDENTITY_MISMATCH"


def test_cross_account_conversation_is_rejected(accounts):
    with SessionLocal() as db:
        conversation = AgentConversationService(db).create_conversation(ConversationCreate(account_id=accounts[0]))
        service = UnifiedAgentService(db, orchestrator=FakeOrchestrator(), runtime=FakeRuntime(None))
        with pytest.raises(UnifiedAgentError) as exc:
            service.handle_turn(request(accounts[1], conversation_id=conversation.id, client_request_id="cross-conv"))
        assert exc.value.code == "CONVERSATION_ACCOUNT_MISMATCH"


def test_conversation_context_owner_persists_structured_pending_state(accounts):
    with SessionLocal() as db:
        conversations = AgentConversationService(db)
        conversation = conversations.create_conversation(ConversationCreate(account_id=accounts[0]))
        owner = ConversationTurnContextOwner(conversations)
        state = TurnContextState(active_pending_run_ref="run-pending", active_pending_checkpoint_version=3)
        owner.save(conversation.id, accounts[0], state)
        restored = owner.load(conversation.id, accounts[0])
        assert restored.active_pending_run_ref == "run-pending"
        assert restored.active_pending_checkpoint_version == 3


def test_get_run_uses_runtime_and_enforces_account_boundary(accounts):
    runtime_result = SimpleNamespace(
        run_ref="run-1", workflow_name="RESEARCH_V1", account_ref=accounts[0], status=WorkflowStatus.SUCCESS,
        checkpoint_version=3, pending_interaction=None, result={"ok": True}, warnings=[], error=None,
        created_at=datetime.now(UTC), updated_at=datetime.now(UTC), completed_at=datetime.now(UTC),
        model_dump=lambda include=None: {
            "run_ref": "run-1", "workflow_name": "RESEARCH_V1", "account_ref": accounts[0], "status": "SUCCESS",
            "checkpoint_version": 3, "pending_interaction": None, "result": {"ok": True}, "warnings": [], "error": None,
        },
    )
    with SessionLocal() as db:
        runtime = FakeRuntime(runtime_result)
        service = UnifiedAgentService(db, orchestrator=FakeOrchestrator(), runtime=runtime)
        response = service.get_run("run-1", accounts[0])
        assert response.result == {"ok": True}
        assert "state_snapshot" not in response.model_dump()
        with pytest.raises(UnifiedAgentError): service.get_run("run-1", accounts[1])


class ApiService:
    def handle_turn(self, data):
        return AgentTurnResponse(conversation_id=1, turn_id=2, turn=AgentTurnResult(action=RuntimeAction.RESPOND, intent=Intent.GENERAL_CHAT, message="你好", status=WorkflowStatus.SUCCESS))
    def get_run(self, run_ref, account_ref):
        return AgentRunResponse(run_ref=run_ref, workflow_name="RESEARCH_V1", account_ref=account_ref, status="SUCCESS", checkpoint_version=2)


def test_post_turn_and_get_run_http_contracts_are_public_safe():
    app.dependency_overrides[get_unified_agent_service] = lambda: ApiService()
    try:
        client = TestClient(app)
        response = client.post("/api/agent/turns", json={"account_ref": 7, "text": "你好", "client_request_id": "http-1"})
        assert response.status_code == 200
        assert response.json()["turn"]["intent"] == "GENERAL_CHAT"
        run = client.get("/api/agent/runs/run-1?account_ref=7")
        assert run.status_code == 200
        assert "state_snapshot" not in run.json()
    finally:
        app.dependency_overrides.clear()


@pytest.mark.parametrize("forbidden", ["intent", "workflow", "tool", "state", "operation_key", "execution_token"])
def test_request_schema_forbids_internal_control_fields(forbidden):
    app.dependency_overrides[get_unified_agent_service] = lambda: ApiService()
    try:
        response = TestClient(app).post("/api/agent/turns", json={"account_ref": 7, "text": "你好", "client_request_id": f"bad-{forbidden}", forbidden: "x"})
        assert response.status_code == 422
    finally:
        app.dependency_overrides.clear()


def test_router_architecture_only_delegates_to_service():
    from pathlib import Path
    source = (Path(__file__).resolve().parents[1] / "app" / "api" / "unified_agent.py").read_text(encoding="utf-8")
    forbidden = ("app.llm", "app.agent.tools", "app.agent.workflows", "app.agent.planning", "app.agent.context", "app.repositories", "AgentRuntime(", ".start(")
    assert [token for token in forbidden if token in source] == []
    assert "service.handle_turn(data)" in source
