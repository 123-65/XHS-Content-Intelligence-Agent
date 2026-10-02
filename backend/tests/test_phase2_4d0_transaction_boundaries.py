import ast
from pathlib import Path

from app.agent.tools.definitions import ToolName
from app.agent.tools.execution_context import ToolExecutionContext
from app.agent.tools.implementation_registry import build_tool_handler


BACKEND_ROOT = Path(__file__).resolve().parents[1]

TARGETS = {
    "app/repositories/competitor_report_repo.py": ("create_report_bundle",),
    "app/repositories/content_strategy_repo.py": ("create_strategy_bundle",),
    "app/repositories/draft_repo.py": ("create_agent_draft_root", "append_agent_draft_version"),
    "app/repositories/publication_repo.py": ("create_post_review", "create_strategy_candidate"),
}


def _method_calls(path: Path, method_name: str) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    method = next(node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef) and node.name == method_name)
    return {
        node.func.attr
        for node in ast.walk(method)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    }


def test_six_canonical_repository_writes_are_flush_only():
    for relative_path, methods in TARGETS.items():
        path = BACKEND_ROOT / relative_path
        for method in methods:
            calls = _method_calls(path, method)
            assert "flush" in calls, f"{relative_path}:{method} must flush"
            assert "commit" not in calls, f"{relative_path}:{method} must not commit"
            assert "rollback" not in calls, f"{relative_path}:{method} must not rollback"


def test_artifact_handlers_keep_tool_execution_context_session_identity():
    class SessionProbe:
        pass

    session = SessionProbe()
    context = ToolExecutionContext(db=session)
    for name in (
        ToolName.CREATE_RESEARCH_ARTIFACT,
        ToolName.CREATE_CONTENT_STRATEGY_ARTIFACT,
        ToolName.CREATE_DRAFT_VERSION,
        ToolName.CREATE_POST_PUBLISH_REVIEW_ARTIFACT,
        ToolName.CREATE_STRATEGY_CANDIDATE,
    ):
        handler = build_tool_handler(name, context)
        assert handler.db is session
        assert handler.repository.db is session


def test_application_owner_can_commit_or_rollback_business_and_future_runtime_rows_together():
    class TransactionProbe:
        def __init__(self):
            self.pending = []
            self.durable = []

        def flush(self):
            return None

        def commit(self):
            self.durable.extend(self.pending)
            self.pending.clear()

        def rollback(self):
            self.pending.clear()

    session = TransactionProbe()
    session.pending.extend(["BUSINESS_WRITE", "FUTURE_OPERATION_LEDGER_WRITE"])
    session.flush()
    session.rollback()
    assert session.durable == []

    session.pending.extend(["BUSINESS_WRITE", "FUTURE_OPERATION_LEDGER_WRITE"])
    session.flush()
    session.commit()
    assert session.durable == ["BUSINESS_WRITE", "FUTURE_OPERATION_LEDGER_WRITE"]
