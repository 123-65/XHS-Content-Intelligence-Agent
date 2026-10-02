from __future__ import annotations

import asyncio


class RecordingVectorStore:
    def __init__(self):
        self.upserts = []
        self.deleted_documents = []

    def upsert_embeddings(self, items):
        self.upserts.extend(items)
        return [f"kb{item['knowledge_base_id']}_chunk{item['chunk_id']}" for item in items]

    def delete_by_document_id(self, document_id):
        self.deleted_documents.append(document_id)


def test_unchanged_chunk_reuses_existing_milvus_vector(monkeypatch):
    asyncio.run(_test_unchanged_chunk_reuses_existing_milvus_vector(monkeypatch))


async def _test_unchanged_chunk_reuses_existing_milvus_vector(monkeypatch):
    from insight_rag.services import indexing_service

    monkeypatch.setattr(indexing_service, "embed_texts", lambda texts: _async_result([[0.1, 0.2, 0.3, 0.4] for _ in texts]))
    db, doc, chunk = _sqlite_index_fixture()
    store = RecordingVectorStore()

    first = await indexing_service.index_document(db, doc.id, vector_store=store)
    second = await indexing_service.index_document(db, doc.id, vector_store=store)

    assert first == 1
    assert second == 0
    assert len(store.upserts) == 1


def test_modified_chunk_updates_milvus_vector(monkeypatch):
    asyncio.run(_test_modified_chunk_updates_milvus_vector(monkeypatch))


async def _test_modified_chunk_updates_milvus_vector(monkeypatch):
    from insight_rag.services import indexing_service

    monkeypatch.setattr(indexing_service, "embed_texts", lambda texts: _async_result([[0.1, 0.2, 0.3, 0.4] for _ in texts]))
    db, doc, chunk = _sqlite_index_fixture()
    store = RecordingVectorStore()
    await indexing_service.index_document(db, doc.id, vector_store=store)

    chunk.content = "changed chunk text"
    chunk.chunk_text = "changed chunk text"
    chunk.chunk_hash = None
    db.commit()
    changed = await indexing_service.index_document(db, doc.id, vector_store=store)

    assert changed == 1
    assert len(store.upserts) == 2


def test_delete_document_marks_embedding_deleted_and_removes_milvus_vector():
    from insight_rag.models.embedding import EmbeddingRecord
    from insight_rag.services.indexing_service import delete_document_embeddings

    db, doc, chunk = _sqlite_index_fixture()
    record = EmbeddingRecord(
        knowledge_base_id=doc.knowledge_base_id,
        document_id=doc.id,
        chunk_id=chunk.id,
        milvus_collection="insightrag_chunks",
        milvus_vector_id="kb1_chunk1",
        embedding_model="mock",
        embedding_dim=4,
        embedding_hash="hash",
        embedding_status="indexed",
    )
    db.add(record)
    db.commit()
    store = RecordingVectorStore()

    delete_document_embeddings(db, doc.id, vector_store=store)
    db.commit()

    assert store.deleted_documents == [doc.id]
    assert db.query(EmbeddingRecord).first().embedding_status == "deleted"


def _async_result(value):
    async def inner(_texts=None):
        return value

    return inner()


def _sqlite_index_fixture():
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
    kb = KnowledgeBase(name="kb-index")
    db.add(kb)
    db.commit()
    doc = Document(knowledge_base_id=kb.id, filename="doc.txt", file_type="txt", storage_path="fixture://doc", status="parsed")
    db.add(doc)
    db.commit()
    chunk = Chunk(
        document_id=doc.id,
        knowledge_base_id=kb.id,
        content="stable chunk text",
        chunk_text="stable chunk text",
        chunk_index=0,
        source_type="text",
        token_count=3,
        deleted=False,
    )
    db.add(chunk)
    db.commit()
    return db, doc, chunk

