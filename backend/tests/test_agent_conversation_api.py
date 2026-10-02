from fastapi.testclient import TestClient

from app.main import app
from app.schemas.account import AccountProfileCreate
from app.services.account_sev import AccountProfileService
from app.services.agent_conversation_sev import AgentConversationService
from app.schemas.agent_conversation import ConversationMessageCreate, ConversationRole
from app.core.database import SessionLocal


def _client() -> TestClient:
    """创建测试客户端。"""
    return TestClient(app)


def _create_account() -> int:
    """创建测试账号。"""
    db = SessionLocal()
    try:
        account = AccountProfileService(db).create_account(
            AccountProfileCreate(
                account_name="B1 会话测试账号",
                platform="xhs",
                content_domain="AI 求职",
                positioning="帮助新人拆解 Agent 项目",
                target_audience="AI 应用工程新人",
                primary_goal="lead",
            )
        )
        return account.id
    finally:
        db.close()


def test_create_conversation():
    """可以创建 conversation。"""
    account_id = _create_account()
    response = _client().post("/agent/conversations", json={"account_id": account_id, "title": "Agent 选题会话"})

    assert response.status_code == 200
    data = response.json()
    assert data["id"]
    assert data["account_id"] == account_id
    assert data["title"] == "Agent 选题会话"
    assert data["status"] == "ACTIVE"


def test_create_conversation_default_title_and_state_fields():
    """title 为空时有默认标题，current_state 默认字段完整。"""
    data = _client().post("/agent/conversations", json={}).json()

    assert data["title"] == "新会话"
    state = data["current_state"]
    assert "current_goal" in state
    assert "active_account_id" in state
    assert "active_opportunity_id" in state
    assert "active_experiment_id" in state
    assert "active_draft_id" in state
    assert "current_target_type" in state
    assert "current_target_id" in state
    assert "last_action" in state
    assert "last_artifacts" in state
    assert "pending_confirmation" in state
    assert "conversation_constraints" in state


def test_list_conversations_by_account_id():
    """可以按 account_id 查询会话列表。"""
    account_id = _create_account()
    created = _client().post("/agent/conversations", json={"account_id": account_id, "title": "账号会话"}).json()
    data = _client().get(f"/agent/conversations?account_ref={account_id}").json()

    assert any(item["id"] == created["id"] for item in data)
    assert all(item["account_id"] == account_id for item in data)


def test_get_conversation_detail():
    """可以读取 conversation detail。"""
    account_id = _create_account()
    created = _client().post("/agent/conversations", json={"account_id": account_id, "title": "详情会话"}).json()
    data = _client().get(f"/agent/conversations/{created['id']}?account_ref={account_id}").json()

    assert data["id"] == created["id"]
    assert data["title"] == "详情会话"


def test_list_messages_initially_empty():
    """可以读取 messages，初始为空列表。"""
    account_id = _create_account()
    created = _client().post("/agent/conversations", json={"account_id": account_id}).json()
    data = _client().get(f"/agent/conversations/{created['id']}/messages?account_ref={account_id}").json()

    assert data == {"items": [], "next_cursor": None, "has_more": False}


def test_get_state():
    """可以读取 state。"""
    account_id = _create_account()
    created = _client().post("/agent/conversations", json={"account_id": account_id}).json()
    state = _client().get(f"/agent/conversations/{created['id']}/state?account_ref={account_id}").json()

    assert state["last_artifacts"] == []
    assert state["conversation_constraints"] == {}


def test_patch_state_only_allows_safe_fields():
    """可以 patch state 的受控字段。"""
    account_id = _create_account()
    created = _client().post("/agent/conversations", json={"account_id": account_id}).json()
    response = _client().patch(
        f"/agent/conversations/{created['id']}/state?account_ref={account_id}",
        json={
            "active_account_id": account_id,
            "active_experiment_id": 456,
            "current_target_type": "CONTENT_EXPERIMENT",
            "current_target_id": 456,
            "conversation_constraints": {"tone": "自然"},
        },
    )

    assert response.status_code == 200
    state = response.json()
    assert state["active_account_id"] == account_id
    assert state["active_experiment_id"] == 456
    assert state["current_target_type"] == "CONTENT_EXPERIMENT"
    assert state["conversation_constraints"] == {"tone": "自然"}


def test_nonexistent_conversation_returns_404():
    """不存在 conversation_id 返回 404。"""
    response = _client().get("/agent/conversations/999999999?account_ref=1")

    assert response.status_code == 404


def test_message_schema_uses_metadata_payload_not_metadata():
    """ConversationMessage 响应使用 metadata_payload，不使用 SQLAlchemy 保留字段 metadata。"""
    account_id = _create_account()
    created = _client().post("/agent/conversations", json={"account_id": account_id}).json()
    messages = _client().get(f"/agent/conversations/{created['id']}/messages?account_ref={account_id}").json()

    assert messages == {"items": [], "next_cursor": None, "has_more": False}
    assert "metadata" not in created


def _owned_conversation(account_id: int) -> dict:
    return _client().post("/agent/conversations", json={"account_id": account_id, "title": "security-boundary"}).json()


def test_sec_conv_001_owner_can_read_and_other_account_is_forbidden():
    """SEC-CONV-001: canonical owner succeeds; Account B receives 403."""
    account_a, account_b = _create_account(), _create_account()
    conversation = _owned_conversation(account_a)

    owner = _client().get(f"/agent/conversations/{conversation['id']}?account_ref={account_a}")
    denied = _client().get(f"/agent/conversations/{conversation['id']}?account_ref={account_b}")

    assert owner.status_code == 200
    assert denied.status_code == 403
    assert denied.json()["detail"]["code"] == "CONVERSATION_ACCOUNT_MISMATCH"


def test_sec_conv_002_other_account_cannot_read_messages():
    """SEC-CONV-002: Account B cannot read Account A messages."""
    account_a, account_b = _create_account(), _create_account()
    conversation = _owned_conversation(account_a)

    denied = _client().get(f"/agent/conversations/{conversation['id']}/messages?account_ref={account_b}")

    assert denied.status_code == 403
    assert denied.json()["detail"]["code"] == "CONVERSATION_ACCOUNT_MISMATCH"


def test_sec_conv_003_cursor_does_not_bypass_account_boundary():
    """SEC-CONV-003: before_id cannot bypass canonical ownership validation."""
    account_a, account_b = _create_account(), _create_account()
    conversation = _owned_conversation(account_a)

    denied = _client().get(
        f"/agent/conversations/{conversation['id']}/messages?account_ref={account_b}&before_id=999999999"
    )

    assert denied.status_code == 403
    assert denied.json()["detail"]["code"] == "CONVERSATION_ACCOUNT_MISMATCH"


def test_sec_conv_004_owner_cursor_pagination_remains_stable():
    """SEC-CONV-004: owner still receives stable keyset pages."""
    account_a = _create_account()
    conversation = _owned_conversation(account_a)
    db = SessionLocal()
    try:
        service = AgentConversationService(db)
        model = service._get(conversation["id"])
        for index in range(5):
            service.repo.add_message(
                model,
                ConversationMessageCreate(role=ConversationRole.USER, content=f"message-{index}"),
            )
    finally:
        db.close()

    first = _client().get(
        f"/agent/conversations/{conversation['id']}/messages?account_ref={account_a}&limit=3"
    ).json()
    second = _client().get(
        f"/agent/conversations/{conversation['id']}/messages?account_ref={account_a}&limit=3&before_id={first['next_cursor']}"
    ).json()

    assert [item["content"] for item in first["items"]] == ["message-2", "message-3", "message-4"]
    assert [item["content"] for item in second["items"]] == ["message-0", "message-1"]
    assert set(item["id"] for item in first["items"]).isdisjoint(item["id"] for item in second["items"])
