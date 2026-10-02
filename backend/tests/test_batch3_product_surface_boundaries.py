from pathlib import Path

import pytest

from app.main import app
from app.models.content_draft import ContentDraft
from app.models.content_experiment import ContentExperiment
from app.models.published_note import PublishedNote
from app.repositories.draft_repo import DraftRepository


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
FRONTEND_ROOT = REPOSITORY_ROOT / "frontend" / "src"

REMOVED_FRONTEND_MODULES = (
    "dataSourceConfig",
    "dataRefreshRun",
    "xhsUrlCollect",
    "evidenceRefreshRun",
    "operationRun",
    "operationExperiment",
    "draftContextPreview",
    "draftGeneration",
    "draftReview",
    "draftRevision",
    "draftRevisionApply",
    "publishPackage",
    "manualPublishBackfill",
    "postPublishReview",
    "strategyMemoryConfirmation",
)

REMOVED_ROUTE_PREFIXES = (
    "/data-source-config",
    "/data-refresh-runs",
    "/evidence-refresh-runs",
    "/operation-runs",
    "/operation-experiments",
    "/xhs",
    "/crawler",
    "/keywords",
    "/competitors",
    "/content-experiments",
    "/content-drafts",
    "/drafts",
    "/publish-packages",
    "/published-notes",
    "/post-publish-reviews",
    "/strategy-memories",
)


def _registered_paths() -> set[str]:
    return set(app.openapi()["paths"])


def _require_frontend_mount() -> None:
    if not FRONTEND_ROOT.exists():
        pytest.skip("后端容器未挂载前端目录，前端边界由主机构建验证")


def test_only_current_agent_chat_operation_is_registered():
    paths = _registered_paths()
    assert "/agent/chat/execute-workflow" in paths
    assert "/agent/chat/preview" not in paths
    assert "/agent/chat/execute-readonly" not in paths


def test_legacy_and_workflow_specific_routers_are_not_registered():
    paths = _registered_paths()
    offenders = sorted(path for path in paths if path.startswith(REMOVED_ROUTE_PREFIXES))
    assert offenders == []


def test_current_operational_and_conversation_surfaces_remain_registered():
    paths = _registered_paths()
    assert "/health" in paths
    assert "/accounts" in paths
    assert "/agent/conversations" in paths
    assert "/api/agent-runs" in paths
    assert any(path.startswith("/api/developer/") for path in paths)


def test_legacy_workbench_and_its_private_clients_are_removed():
    _require_frontend_mount()
    assert not (FRONTEND_ROOT / "views" / "AgentWorkbenchLegacy.vue").exists()
    for module in REMOVED_FRONTEND_MODULES:
        assert not (FRONTEND_ROOT / "api" / f"{module}.ts").exists()
        assert not (FRONTEND_ROOT / "types" / f"{module}.ts").exists()


def test_current_agent_chat_uses_only_unified_turn_operation():
    _require_frontend_mount()
    agent_chat_view = (FRONTEND_ROOT / "views" / "AgentChatView.vue").read_text(encoding="utf-8")
    agent_chat_store = (FRONTEND_ROOT / "stores" / "agentChat.ts").read_text(encoding="utf-8")
    unified_agent = (FRONTEND_ROOT / "api" / "unifiedAgent.ts").read_text(encoding="utf-8")

    assert "useAgentChatStore" in agent_chat_view
    assert "sendAgentTurn" not in agent_chat_view
    assert "executeWorkflowAgentChat" not in agent_chat_view
    assert "from '@/api/unifiedAgent'" in agent_chat_store
    assert "sendAgentTurn" in agent_chat_store
    assert "/api/agent/turns" in unified_agent
    assert "/agent/chat/execute-workflow" not in unified_agent
    assert "/agent/chat/preview" not in unified_agent
    assert "/agent/chat/execute-readonly" not in unified_agent


def test_persistent_business_contracts_are_preserved():
    assert ContentDraft.__tablename__ == "content_draft"
    assert ContentExperiment.__tablename__ == "content_experiment"
    assert PublishedNote.__tablename__ == "published_note"
    assert DraftRepository is not None
