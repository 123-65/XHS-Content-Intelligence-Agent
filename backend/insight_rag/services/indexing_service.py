from __future__ import annotations

import hashlib

from sqlalchemy.orm import Session

from insight_rag.core.config import settings
from insight_rag.models.chunk import Chunk
from insight_rag.models.document import Document
from insight_rag.models.embedding import EmbeddingRecord
from insight_rag.services.llm import embed_texts
from insight_rag.services.vector_store import MilvusVectorStore, get_vector_store


def chunk_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def embedding_hash(text: str, model: str, dim: int) -> str:
    return hashlib.sha256(f"{model}:{dim}:{text}".encode("utf-8")).hexdigest()


async def index_document(db: Session, document_id: int, vector_store: MilvusVectorStore | None = None) -> int:
    doc = db.get(Document, document_id)
    if not doc:
        raise ValueError("Document not found")

    vector_store = vector_store or get_vector_store()
    chunks = (
        db.query(Chunk)
        .filter(Chunk.document_id == document_id, Chunk.deleted.is_(False))
        .order_by(Chunk.chunk_index.asc())
        .all()
    )
    pending: list[Chunk] = []
    for chunk in chunks:
        text = _chunk_text(chunk)
        current_chunk_hash = chunk.chunk_hash or chunk_hash(text)
        current_embedding_hash = embedding_hash(text, settings.active_embedding_model, settings.active_embedding_dim)
        chunk.chunk_hash = current_chunk_hash
        chunk.chunk_text = text
        record = (
            db.query(EmbeddingRecord)
            .filter(
                EmbeddingRecord.chunk_id == chunk.id,
                EmbeddingRecord.embedding_hash == current_embedding_hash,
                EmbeddingRecord.embedding_model == settings.active_embedding_model,
                EmbeddingRecord.embedding_dim == settings.active_embedding_dim,
                EmbeddingRecord.embedding_status == "indexed",
            )
            .first()
        )
        if record:
            chunk.embedded = True
            continue
        pending.append(chunk)

    if not pending:
        db.commit()
        return 0

    texts = [_chunk_text(chunk) for chunk in pending]
    vectors = await embed_texts(texts)
    if len(vectors) != len(pending):
        raise ValueError(f"Embedding returned {len(vectors)} vectors for {len(pending)} chunks")

    items = [
        {
            "knowledge_base_id": chunk.knowledge_base_id,
            "document_id": chunk.document_id,
            "chunk_id": chunk.id,
            "chunk_hash": chunk.chunk_hash or chunk_hash(_chunk_text(chunk)),
            "source_type": chunk.source_type or "text",
            "embedding": vector,
        }
        for chunk, vector in zip(pending, vectors, strict=True)
    ]

    try:
        vector_ids = vector_store.upsert_embeddings(items)
    except Exception:
        for chunk in pending:
            _upsert_embedding_record(db, chunk, "", "failed")
        db.commit()
        raise

    for chunk, vector_id in zip(pending, vector_ids, strict=True):
        chunk.embedded = True
        _upsert_embedding_record(db, chunk, vector_id, "indexed")
    doc.status = "embedded"
    doc.error_message = None
    db.commit()
    return len(pending)


def delete_document_embeddings(db: Session, document_id: int, vector_store: MilvusVectorStore | None = None) -> None:
    vector_store = vector_store or get_vector_store()
    vector_store.delete_by_document_id(document_id)
    (
        db.query(EmbeddingRecord)
        .filter(EmbeddingRecord.document_id == document_id)
        .update({EmbeddingRecord.embedding_status: "deleted"}, synchronize_session=False)
    )


def delete_knowledge_base_embeddings(
    db: Session,
    knowledge_base_id: int,
    vector_store: MilvusVectorStore | None = None,
) -> None:
    vector_store = vector_store or get_vector_store()
    vector_store.delete_by_knowledge_base_id(knowledge_base_id)
    (
        db.query(EmbeddingRecord)
        .filter(EmbeddingRecord.knowledge_base_id == knowledge_base_id)
        .update({EmbeddingRecord.embedding_status: "deleted"}, synchronize_session=False)
    )


def _upsert_embedding_record(db: Session, chunk: Chunk, vector_id: str, status: str) -> None:
    text = _chunk_text(chunk)
    current_embedding_hash = embedding_hash(text, settings.active_embedding_model, settings.active_embedding_dim)
    record = db.query(EmbeddingRecord).filter(EmbeddingRecord.chunk_id == chunk.id).first()
    if not record:
        record = EmbeddingRecord(
            knowledge_base_id=chunk.knowledge_base_id,
            document_id=chunk.document_id,
            chunk_id=chunk.id,
            milvus_collection=settings.active_milvus_collection,
            milvus_vector_id=vector_id,
            embedding_model=settings.active_embedding_model,
            embedding_dim=settings.active_embedding_dim,
            embedding_hash=current_embedding_hash,
            embedding_status=status,
        )
        db.add(record)
        return
    record.milvus_collection = settings.active_milvus_collection
    record.milvus_vector_id = vector_id or record.milvus_vector_id
    record.embedding_model = settings.active_embedding_model
    record.embedding_dim = settings.active_embedding_dim
    record.embedding_hash = current_embedding_hash
    record.embedding_status = status


def _chunk_text(chunk: Chunk) -> str:
    return chunk.chunk_text or chunk.content

