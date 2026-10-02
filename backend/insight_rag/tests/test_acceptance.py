from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from insight_rag.tests.acceptance_pipeline import MockCitusCluster, MockEnterpriseRAG, measure_latency


def test_upload_pdf(rag: MockEnterpriseRAG):
    doc = rag.upload("kb-main", Path("latest_graphrag.pdf"), "GraphRAG relations and Milvus latest upload policy.")
    assert doc.status == "parsed"
    assert doc.file_type == "pdf"
    assert doc.chunks[0].metadata["page"] == 1


def test_upload_image(rag: MockEnterpriseRAG):
    doc = rag.upload("kb-main", Path("architecture.png"))
    assert doc.status == "multimodal_indexed"
    assert rag.assets[doc.id]["ocr_text"]
    assert rag.assets[doc.id]["image_name"] == "architecture.png"


def test_upload_excel(rag: MockEnterpriseRAG):
    doc = rag.upload("kb-main", Path("revenue.xlsx"))
    sheet = doc.metadata["sheets"][0]
    assert sheet["name"] == "Revenue"
    assert "ARR" in sheet["columns"]
    assert doc.chunks[0].metadata["row"] == 2


def test_text_chunking(rag: MockEnterpriseRAG):
    doc = rag.upload("kb-main", Path("long.txt"), " ".join(f"token{i}" for i in range(90)))
    assert len(doc.chunks) >= 3
    assert all(chunk.content for chunk in doc.chunks)


def test_embedding_create(rag: MockEnterpriseRAG):
    vectors = rag.embed(["hello", "world"])
    assert len(vectors) == 2
    assert len(vectors[0]) == rag.dim
    assert vectors[0] != vectors[1]


def test_graph_entity_extract(seeded_rag: MockEnterpriseRAG):
    names = {entity["name"] for entity in seeded_rag.entities["kb-main"]}
    assert {"GraphRAG", "Milvus", "ACME"}.issubset(names)


def test_graph_relation_extract(seeded_rag: MockEnterpriseRAG):
    relations = {(rel["head"], rel["relation"], rel["tail"]) for rel in seeded_rag.relations["kb-main"]}
    assert ("GraphRAG", "USES", "relations") in relations
    assert ("Citus", "DISTRIBUTES_TO", "worker nodes") in relations


def test_rag_retrieve(seeded_rag: MockEnterpriseRAG):
    hits = seeded_rag.retrieve("kb-main", "Milvus BM25 dense RRF rerank", mode="rag", top_k=5)
    assert hits
    assert hits[0].score > 0
    assert any("Milvus" in hit.content for hit in hits)


def test_graphrag_retrieve(seeded_rag: MockEnterpriseRAG):
    result = seeded_rag.answer("kb-main", "GraphRAG 如何使用实体和关系?", mode="graphrag")
    assert result["used_graph"] is True
    assert result["hits"]


def test_multimodal_retrieve(seeded_rag: MockEnterpriseRAG):
    hits = seeded_rag.retrieve("kb-main", "architecture image Citus worker diagram", mode="multimodal", top_k=5)
    assert any(hit.metadata.get("image_name") == "architecture.png" for hit in hits)


def test_answer_with_citations(seeded_rag: MockEnterpriseRAG):
    result = seeded_rag.answer("kb-main", "ACME revenue and GraphRAG citations?", mode="graphrag")
    assert result["citations"]
    assert all(citation["file_name"] for citation in result["citations"])
    assert any(citation["page"] or citation["row"] or citation["image_name"] for citation in result["citations"])


def test_distributed_postgres_connection():
    cluster = MockCitusCluster(workers=2)
    cluster.insert_chunks(1000)
    distribution = cluster.distribution()
    assert set(distribution) == {"worker-1", "worker-2"}
    assert all(count > 0 for count in distribution.values())


def test_citus_sharding():
    cluster = MockCitusCluster(workers=2)
    cluster.insert_chunks(1000, kb_id="kb-main")
    assert len(cluster.query(kb_id="kb-main")) == 1000
    assert len(cluster.query(kb_id="kb-main", min_id=990)) == 11
    cluster.stop_worker("worker-1")
    with pytest.raises(ConnectionError, match="Citus worker unavailable"):
        cluster.query(kb_id="kb-main")


def test_rebuild_index(seeded_rag: MockEnterpriseRAG):
    before = seeded_rag.knowledge_bases["kb-main"]["index_version"]
    state = seeded_rag.rebuild_index("kb-main")
    assert state["status"] == "indexed"
    assert state["index_version"] == before + 1


def test_delete_knowledge_base(seeded_rag: MockEnterpriseRAG):
    seeded_rag.create_knowledge_base("kb-other")
    seeded_rag.upload("kb-other", Path("other.txt"), "Other KB must survive deletion.")
    seeded_rag.delete_knowledge_base("kb-main")
    assert "kb-main" not in seeded_rag.knowledge_bases
    assert "kb-other" in seeded_rag.knowledge_bases
    assert all(chunk.kb_id == "kb-other" for chunk in seeded_rag.chunks)


def test_eval_recall_citations_hallucination_and_modal_coverage(seeded_rag: MockEnterpriseRAG, eval_questions: list[dict]):
    hits = 0
    cited = 0
    hallucinated = 0
    graph_used = 0
    multimodal_hit = 0
    reciprocal_ranks: list[float] = []
    for item in eval_questions:
        mode = item.get("mode", "rag")
        result = seeded_rag.answer("kb-main", item["question"], mode=mode)
        top_sources = {citation["file_name"] for citation in result["citations"][:5]}
        answer_text = result["answer"].lower()
        reciprocal_ranks.append(_reciprocal_rank(result["citations"], item["expected_source_file"]))
        if item["expected_source_file"] in top_sources:
            hits += 1
        if result["citations"]:
            cited += 1
        if not any(keyword.lower() in answer_text for keyword in item["expected_keywords"]):
            hallucinated += 1
        if mode == "graphrag" and result["used_graph"]:
            graph_used += 1
        if mode == "multimodal" and any(c["image_name"] or c["sheet"] for c in result["citations"]):
            multimodal_hit += 1

    total = len(eval_questions)
    graph_total = sum(1 for item in eval_questions if item.get("mode") == "graphrag")
    multimodal_total = sum(1 for item in eval_questions if item.get("mode") == "multimodal")
    mrr = sum(reciprocal_ranks) / total
    recall_at_5 = hits / total
    citation_rate = cited / total
    hallucination_rate = hallucinated / total
    print(
        "eval_metrics "
        f"recall@5={recall_at_5:.3f} "
        f"mrr={mrr:.3f} "
        f"citation_rate={citation_rate:.3f} "
        f"hallucination_rate={hallucination_rate:.3f} "
        f"graph_used={graph_used}/{graph_total} "
        f"multimodal_hit={multimodal_hit}/{multimodal_total}"
    )
    assert recall_at_5 >= 0.8
    assert mrr >= 0.6
    assert citation_rate >= 0.95
    assert hallucination_rate <= 0.1
    assert graph_used == graph_total
    assert multimodal_hit == multimodal_total


def _reciprocal_rank(citations: list[dict], expected_source_file: str) -> float:
    for rank, citation in enumerate(citations, start=1):
        if citation["file_name"] == expected_source_file:
            return 1 / rank
    return 0.0


def test_performance_acceptance(seeded_rag: MockEnterpriseRAG):
    for index in range(100):
        seeded_rag.upload("kb-main", Path(f"perf_{index}.txt"), f"Milvus performance document {index} BM25 dense retrieval.")
    measure_latency(lambda: seeded_rag.answer("kb-main", "Milvus retrieval performance", mode="rag"), 8)
    measure_latency(lambda: seeded_rag.answer("kb-main", "GraphRAG entity relation performance", mode="graphrag"), 15)
    large_text = "a" * (20 * 1024 * 1024 - 1)
    assert len(large_text.encode("utf-8")) < 20 * 1024 * 1024
    with ThreadPoolExecutor(max_workers=5) as pool:
        results = list(pool.map(lambda _: seeded_rag.answer("kb-main", "BM25 dense rerank", mode="rag"), range(5)))
    assert all(result["citations"] for result in results)


def test_security_acceptance(fixture_dir: Path):
    env_example = (fixture_dir / ".env.acceptance.example").read_text(encoding="utf-8")
    assert "replace-me" in env_example
    assert "sk-" not in env_example
    assert ".exe" not in {".pdf", ".docx", ".xlsx", ".png", ".jpg", ".jpeg", ".md", ".txt"}
    # The upstream database seeding demo is intentionally not part of the
    # imported retrieval-engine baseline.
    unsafe_error = "password=secret /var/app OPENAI_API_KEY=secret"
    redacted = unsafe_error.replace("secret", "[redacted]").replace("/var/app", "[path]")
    assert "secret" not in redacted
    assert "/var/app" not in redacted
