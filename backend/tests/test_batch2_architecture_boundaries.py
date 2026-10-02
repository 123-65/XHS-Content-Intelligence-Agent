from pathlib import Path

from app.collectors.xhs.xiaohongshu_mcp_provider import XiaohongshuMcpProvider
from app.models.agent_run import AgentRun
from app.models.agent_step import AgentStep
from app.models.mcp_server_config import MCPServerConfig
from app.models.mcp_tool_binding import MCPToolBinding
from app.models.mcp_tool_call_log import MCPToolCallLog
from app.repositories.agent_run_repo import AgentRunRepository


BACKEND_ROOT = Path(__file__).resolve().parents[1]
APP_ROOT = BACKEND_ROOT / "app"

REMOVED_PATHS = (
    "agent/runtime.py",
    "agent/workflows/content_experiment.py",
    "agent/tools/base.py",
    "agent/tools/local_registry.py",
    "agent/tools/mcp_registry.py",
    "agent/tools/fallback_registry.py",
    "agent/policies/guardrail.py",
    "agent/policies/stop.py",
    "agent/policies/fallback.py",
    "mcp/gateway.py",
)

FORBIDDEN_PRODUCTION_REFERENCES = (
    "app.agent.runtime",
    "app.agent.policies",
    "app.mcp.gateway",
    "ContentExperimentWorkflow",
    "MCPToolRegistry",
    "FallbackToolRegistry",
    "MCPToolGateway",
)


def test_failed_runtime_files_are_removed():
    assert [path for path in REMOVED_PATHS if (APP_ROOT / path).exists()] == []


def test_production_has_no_old_runtime_import_or_symbol_reference():
    offenders = []
    for path in APP_ROOT.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        if any(token in text for token in FORBIDDEN_PRODUCTION_REFERENCES):
            offenders.append(str(path.relative_to(BACKEND_ROOT)))
    assert offenders == []


def test_product_entry_does_not_reference_old_runtime_subgraph():
    product_entry = APP_ROOT / "agent" / "product_entry"
    offenders = []
    for path in product_entry.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        if any(token in text for token in FORBIDDEN_PRODUCTION_REFERENCES):
            offenders.append(str(path.relative_to(BACKEND_ROOT)))
    assert offenders == []


def test_canonical_xhs_mcp_provider_is_preserved():
    assert XiaohongshuMcpProvider.provider_name == "xiaohongshu_mcp"
    assert (APP_ROOT / "collectors" / "xhs" / "xiaohongshu_mcp_provider.py").is_file()


def test_trace_and_mcp_history_contracts_are_preserved():
    assert AgentRun.__tablename__ == "agent_run"
    assert AgentStep.__tablename__ == "agent_step"
    assert MCPToolCallLog.__tablename__ == "mcp_tool_call_log"
    assert MCPServerConfig.__tablename__ == "mcp_server_config"
    assert MCPToolBinding.__tablename__ == "mcp_tool_binding"
    assert AgentRunRepository is not None
