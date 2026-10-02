from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

BACKEND = Path(__file__).parents[2]
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("ASYNC_DATABASE_URL", "sqlite:///:memory:")

from insight_rag.tests.acceptance_pipeline import MockEnterpriseRAG


@pytest.fixture()
def fixture_dir() -> Path:
    return Path(__file__).parent / "fixtures"


@pytest.fixture()
def rag() -> MockEnterpriseRAG:
    engine = MockEnterpriseRAG()
    engine.create_knowledge_base("kb-main")
    return engine


@pytest.fixture()
def seeded_rag(rag: MockEnterpriseRAG) -> MockEnterpriseRAG:
    rag.upload(
        "kb-main",
        Path("latest_graphrag.pdf"),
        "GraphRAG extracts entities, relations, and summaries for ACME. Milvus hybrid retrieval uses BM25 dense RRF and rerank.",
    )
    rag.upload("kb-main", Path("conversation_policy.docx"), "Asyncpg stores every conversation message and can continue or create a new chat.")
    rag.upload("kb-main", Path("revenue.xlsx"))
    rag.upload("kb-main", Path("architecture.png"))
    rag.upload("kb-main", Path("notes.md"), "Markdown runbook says PostgreSQL Citus has coordinator and two worker nodes.")
    return rag


@pytest.fixture()
def eval_questions(fixture_dir: Path) -> list[dict]:
    return json.loads((fixture_dir / "eval_questions.json").read_text(encoding="utf-8"))
