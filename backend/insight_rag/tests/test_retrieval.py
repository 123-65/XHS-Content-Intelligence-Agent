from __future__ import annotations

import asyncio

from insight_rag.services.vector_store import VectorSearchHit


class FakeVectorStore:
    def __init__(self, hits):
        self.hits = hits

    def search(self, query_embedding, knowledge_base_id, top_k, filters=None):
        return [hit for hit in self.hits if hit.knowledge_base_id == knowledge_base_id][:top_k]


class FailingVectorStore:
    def search(self, query_embedding, knowledge_base_id, top_k, filters=None):
        raise RuntimeError("Milvus unavailable")


def test_hybrid_retrieval_joins_postgres_and_filters_deleted(monkeypatch):
    asyncio.run(_test_hybrid_retrieval_joins_postgres_and_filters_deleted(monkeypatch))


async def _test_hybrid_retrieval_joins_postgres_and_filters_deleted(monkeypatch):
    from insight_rag.services import retrieval_service

    monkeypatch.setattr(retrieval_service, "embed_texts", lambda texts: _async_result([[0.1, 0.2, 0.3, 0.4]]))

    db, kb, doc, live_chunk, deleted_chunk = _sqlite_fixture()
    store = FakeVectorStore(
        [
            VectorSearchHit(live_chunk.id, doc.id, kb.id, "live", "text", 0.9, "v-live"),
            VectorSearchHit(deleted_chunk.id, doc.id, kb.id, "deleted", "text", 0.8, "v-deleted"),
        ]
    )

    hits = await retrieval_service.retrieve_chunks(db, kb.id, "milvus hybrid live", top_k=5, vector_store=store)

    assert [hit.chunk_id for hit in hits].count(live_chunk.id) == 1
    assert deleted_chunk.id not in {hit.chunk_id for hit in hits}
    assert hits[0].content == "milvus hybrid live chunk"
    assert hits[0].metadata["filename"] == "live.txt"


def test_retrieval_falls_back_to_keyword_when_milvus_fails(monkeypatch):
    asyncio.run(_test_retrieval_falls_back_to_keyword_when_milvus_fails(monkeypatch))


async def _test_retrieval_falls_back_to_keyword_when_milvus_fails(monkeypatch):
    from insight_rag.services import retrieval_service

    monkeypatch.setattr(retrieval_service, "embed_texts", lambda texts: _async_result([[0.1, 0.2, 0.3, 0.4]]))
    db, kb, _doc, live_chunk, _deleted_chunk = _sqlite_fixture()

    hits = await retrieval_service.retrieve_chunks(
        db,
        kb.id,
        "milvus hybrid live",
        top_k=5,
        vector_store=FailingVectorStore(),
    )

    assert hits
    assert hits[0].chunk_id == live_chunk.id
    assert hits[0].bm25_score is not None


def test_retrieval_filters_noise_chunks(monkeypatch):
    asyncio.run(_test_retrieval_filters_noise_chunks(monkeypatch))


async def _test_retrieval_filters_noise_chunks(monkeypatch):
    from insight_rag.models.chunk import Chunk
    from insight_rag.services import retrieval_service

    monkeypatch.setattr(retrieval_service, "embed_texts", lambda texts: _async_result([[0.1, 0.2, 0.3, 0.4]]))
    db, kb, doc, _live_chunk, _deleted_chunk = _sqlite_fixture()
    noise = Chunk(
        document_id=doc.id,
        knowledge_base_id=kb.id,
        content="# Page 5 此为试读,需要完整PDF请访问: www.ertongbook.com",
        chunk_text="# Page 5 此为试读,需要完整PDF请访问: www.ertongbook.com",
        chunk_hash="noise",
        chunk_index=2,
        source_type="pdf",
        token_count=5,
        deleted=False,
    )
    db.add(noise)
    db.commit()
    store = FakeVectorStore([VectorSearchHit(noise.id, doc.id, kb.id, "noise", "pdf", 0.99, "v-noise")])

    hits = await retrieval_service.retrieve_chunks(db, kb.id, "ertongbook Page 5", top_k=5, vector_store=store)

    assert all("ertongbook" not in hit.content for hit in hits)


def test_multimodal_retrieval_returns_image_url(monkeypatch):
    asyncio.run(_test_multimodal_retrieval_returns_image_url(monkeypatch))


async def _test_multimodal_retrieval_returns_image_url(monkeypatch):
    from insight_rag.models.chunk import Chunk
    from insight_rag.services import retrieval_service

    monkeypatch.setattr(retrieval_service, "embed_texts", lambda texts: _async_result([[0.1, 0.2, 0.3, 0.4]]))
    db, kb, doc, _live_chunk, _deleted_chunk = _sqlite_fixture()
    image_chunk = Chunk(
        document_id=doc.id,
        knowledge_base_id=kb.id,
        content="image caption shows China geography map",
        chunk_text="image caption shows China geography map",
        chunk_hash="image",
        chunk_index=2,
        source_type="image",
        token_count=8,
        deleted=False,
        meta={"public_url": "http://localhost:9000/insightrag/k.png", "object_key": "knowledge-bases/1/documents/1/images/page_5/image_1.png"},
    )
    db.add(image_chunk)
    db.commit()
    store = FakeVectorStore([VectorSearchHit(image_chunk.id, doc.id, kb.id, "image", "image", 0.99, "v-image")])

    hits = await retrieval_service.retrieve_chunks(db, kb.id, "China geography map", top_k=5, vector_store=store)

    assert hits[0].metadata["public_url"] == "http://localhost:9000/insightrag/k.png"


def test_image_citation_contains_page_and_object_key(monkeypatch):
    asyncio.run(_test_image_citation_contains_page_and_object_key(monkeypatch))


async def _test_image_citation_contains_page_and_object_key(monkeypatch):
    from insight_rag.models.chunk import Chunk
    from insight_rag.services import retrieval_service

    monkeypatch.setattr(retrieval_service, "embed_texts", lambda texts: _async_result([[0.1, 0.2, 0.3, 0.4]]))
    db, kb, doc, _live_chunk, _deleted_chunk = _sqlite_fixture()
    image_chunk = Chunk(
        document_id=doc.id,
        knowledge_base_id=kb.id,
        content="OCR text for regional map figure",
        chunk_text="OCR text for regional map figure",
        chunk_hash="ocr",
        chunk_index=2,
        page_number=5,
        source_type="ocr",
        token_count=8,
        deleted=False,
        meta={"object_key": "knowledge-bases/1/documents/1/images/page_5/image_1.png", "image_index": 1},
    )
    db.add(image_chunk)
    db.commit()
    store = FakeVectorStore([VectorSearchHit(image_chunk.id, doc.id, kb.id, "ocr", "ocr", 0.99, "v-ocr")])

    hits = await retrieval_service.retrieve_chunks(db, kb.id, "regional map figure", top_k=5, vector_store=store)

    assert hits[0].metadata["page_number"] == 5
    assert hits[0].metadata["image_index"] == 1
    assert hits[0].metadata["object_key"].endswith("image_1.png")


def test_cross_modal_query_recalls_text_and_image(monkeypatch):
    asyncio.run(_test_cross_modal_query_recalls_text_and_image(monkeypatch))


async def _test_cross_modal_query_recalls_text_and_image(monkeypatch):
    from insight_rag.models.chunk import Chunk
    from insight_rag.services import retrieval_service

    monkeypatch.setattr(retrieval_service, "embed_texts", lambda texts: _async_result([[0.1, 0.2, 0.3, 0.4]]))
    db, kb, doc, live_chunk, _deleted_chunk = _sqlite_fixture()
    image_chunk = Chunk(
        document_id=doc.id,
        knowledge_base_id=kb.id,
        content="map image caption about China geography",
        chunk_text="map image caption about China geography",
        chunk_hash="image-cross",
        chunk_index=2,
        source_type="image",
        token_count=8,
        deleted=False,
        meta={"public_url": "http://localhost:9000/insightrag/map.png"},
    )
    db.add(image_chunk)
    db.commit()
    store = FakeVectorStore(
        [
            VectorSearchHit(image_chunk.id, doc.id, kb.id, "image-cross", "image", 0.99, "v-image"),
            VectorSearchHit(live_chunk.id, doc.id, kb.id, "live", "text", 0.8, "v-live"),
        ]
    )

    hits = await retrieval_service.retrieve_chunks(db, kb.id, "hybrid China geography map", top_k=5, vector_store=store)
    source_types = {hit.metadata["source_type"] for hit in hits}

    assert {"text", "image"}.issubset(source_types)


def test_hybrid_retrieval_deduplicates_dense_and_keyword():
    from insight_rag.services.retrieval_service import _rrf_fuse
    from insight_rag.schemas.chat import SearchHit

    dense = SearchHit(chunk_id=1, document_id=1, knowledge_base_id=1, content="same", metadata={}, dense_score=0.8)
    keyword = SearchHit(chunk_id=1, document_id=1, knowledge_base_id=1, content="same", metadata={}, bm25_score=2.0)
    fused = _rrf_fuse([dense], [keyword])
    assert len(fused) == 1
    assert fused[0].dense_score == 0.8
    assert fused[0].bm25_score == 2.0


def _async_result(value):
    async def inner(_texts=None):
        return value

    return inner()


def _sqlite_fixture():
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from insight_rag.core.db import Base
    from insight_rag.models.chunk import Chunk
    from insight_rag.models.document import Document
    from insight_rag.models.knowledge_base import KnowledgeBase

    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    db = Session()
    kb = KnowledgeBase(name="kb")
    db.add(kb)
    db.commit()
    doc = Document(knowledge_base_id=kb.id, filename="live.txt", file_type="txt", storage_path="fixture://live", status="embedded")
    db.add(doc)
    db.commit()
    live = Chunk(
        document_id=doc.id,
        knowledge_base_id=kb.id,
        content="milvus hybrid live chunk",
        chunk_text="milvus hybrid live chunk",
        chunk_hash="live",
        chunk_index=0,
        source_type="text",
        token_count=4,
        deleted=False,
    )
    deleted = Chunk(
        document_id=doc.id,
        knowledge_base_id=kb.id,
        content="milvus hybrid deleted chunk",
        chunk_text="milvus hybrid deleted chunk",
        chunk_hash="deleted",
        chunk_index=1,
        source_type="text",
        token_count=4,
        deleted=True,
    )
    db.add_all([live, deleted])
    db.commit()
    return db, kb, doc, live, deleted

