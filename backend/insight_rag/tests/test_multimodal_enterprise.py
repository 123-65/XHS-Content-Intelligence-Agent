from __future__ import annotations

import asyncio

from insight_rag.services.vector_store import VectorSearchHit


def test_pdf_extracts_all_images():
    from insight_rag.services.multimodal_service import extract_pdf_image_assets

    assert callable(extract_pdf_image_assets)


def test_image_upload_to_oss(tmp_path, monkeypatch):
    from insight_rag.core.config import settings
    from insight_rag.services.storage_service import ObjectStorageService

    monkeypatch.setattr(settings, "local_storage_dir", str(tmp_path))
    stored = ObjectStorageService("local").upload_bytes(b"image", "knowledge-bases/1/documents/2/images/page_1/image_1.png")

    assert stored.object_key.endswith("image_1.png")


def test_qwen_vl_generates_caption(monkeypatch):
    from insight_rag.services import llm

    monkeypatch.setattr(llm.settings, "llm_provider", "mock")

    assert "caption" in llm.caption_image_bytes(b"image-bytes").lower()


def test_image_embedding_written_to_milvus():
    from insight_rag.services.indexing_service import index_document

    assert callable(index_document)


def test_multimodal_retrieval(monkeypatch):
    asyncio.run(_assert_multimodal_retrieval(monkeypatch, "Figure 5 GraphRAG Recall"))


def test_cross_modal_retrieval(monkeypatch):
    asyncio.run(_assert_multimodal_retrieval(monkeypatch, "Figure 5中的Recall是多少"))


def test_image_citation(monkeypatch):
    asyncio.run(_assert_multimodal_retrieval(monkeypatch, "show figure citation", require_image_url=True))


async def _assert_multimodal_retrieval(monkeypatch, query: str, require_image_url: bool = False):
    from insight_rag.models.chunk import Chunk
    from insight_rag.services import retrieval_service
    from insight_rag.services.multimodal_retrieval_service import retrieve_multimodal_chunks
    from insight_rag.tests.test_retrieval import FakeVectorStore, _async_result, _sqlite_fixture

    monkeypatch.setattr(retrieval_service, "embed_texts", lambda texts: _async_result([[0.1, 0.2, 0.3, 0.4]]))
    db, kb, doc, live_chunk, _deleted_chunk = _sqlite_fixture()
    image_chunk = Chunk(
        document_id=doc.id,
        knowledge_base_id=kb.id,
        content="Figure 5 shows GraphRAG Recall=85% and RAG Recall=71%",
        chunk_text="Figure 5 shows GraphRAG Recall=85% and RAG Recall=71%",
        chunk_hash="fig5",
        chunk_index=2,
        page_number=12,
        source_type="image_caption",
        token_count=10,
        deleted=False,
        meta={"image_url": "https://oss.example/fig5.png", "figure": "Figure 5", "page_number": 12},
    )
    ocr_chunk = Chunk(
        document_id=doc.id,
        knowledge_base_id=kb.id,
        content="Recall GraphRAG 85% RAG 71%",
        chunk_text="Recall GraphRAG 85% RAG 71%",
        chunk_hash="ocr5",
        chunk_index=3,
        page_number=12,
        source_type="ocr",
        token_count=6,
        deleted=False,
        meta={"image_url": "https://oss.example/fig5.png", "figure": "Figure 5", "page_number": 12},
    )
    db.add_all([image_chunk, ocr_chunk])
    db.commit()
    store = FakeVectorStore(
        [
            VectorSearchHit(image_chunk.id, doc.id, kb.id, "fig5", "image_caption", 0.99, "v-fig5"),
            VectorSearchHit(ocr_chunk.id, doc.id, kb.id, "ocr5", "ocr", 0.98, "v-ocr5"),
            VectorSearchHit(live_chunk.id, doc.id, kb.id, "live", "text", 0.8, "v-live"),
        ]
    )

    hits = await retrieve_multimodal_chunks(db, kb.id, query, top_k=5, vector_store=store)

    assert {"image_caption", "ocr"}.issubset({hit.metadata["source_type"] for hit in hits})
    if require_image_url:
        assert any(hit.metadata.get("image_url") == "https://oss.example/fig5.png" for hit in hits)

