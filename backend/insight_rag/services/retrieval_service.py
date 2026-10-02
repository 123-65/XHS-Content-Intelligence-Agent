from __future__ import annotations

import math
import re
from collections import Counter

from sqlalchemy.orm import Session

from insight_rag.models.chunk import Chunk
from insight_rag.models.document import Document
from insight_rag.schemas.chat import SearchHit
from insight_rag.services.llm import embed_texts
from insight_rag.services.parser import is_noise_chunk
from insight_rag.services.vector_store import MilvusVectorStore, VectorSearchHit, get_vector_store


TOKEN_RE = re.compile(r"[\w\u4e00-\u9fff]+", re.UNICODE)


async def retrieve_chunks(
    db: Session,
    knowledge_base_id: int,
    query: str,
    top_k: int = 5,
    rerank: bool = True,
    filters: dict | None = None,
    vector_store: MilvusVectorStore | None = None,
) -> list[SearchHit]:
    vector_store = vector_store or get_vector_store()
    vector_hits: list[VectorSearchHit] = []
    query_embedding = await _embed_query_with_fallback(query)
    if query_embedding is not None:
        try:
            vector_hits = vector_store.search(query_embedding, knowledge_base_id, max(top_k * 4, 20), filters=filters)
        except Exception:
            vector_hits = []
    dense_hits = _hydrate_vector_hits(db, vector_hits)
    keyword_hits = _keyword_search(db, knowledge_base_id, query, max(top_k * 4, 20), filters=filters)
    fused = _rrf_fuse(dense_hits, keyword_hits)
    if rerank:
        fused = _rerank(query, fused)
    return [hit for hit in fused if not is_noise_chunk(hit.content)][:top_k]


def _hydrate_vector_hits(db: Session, vector_hits: list[VectorSearchHit]) -> list[SearchHit]:
    if not vector_hits:
        return []
    vector_by_chunk = {hit.chunk_id: hit for hit in vector_hits}
    rows = (
        db.query(Chunk, Document)
        .join(Document, Chunk.document_id == Document.id)
        .filter(Chunk.id.in_(vector_by_chunk), Chunk.deleted.is_(False))
        .all()
    )
    hits: list[SearchHit] = []
    for chunk, document in rows:
        if is_noise_chunk(_chunk_text(chunk)):
            continue
        vector_hit = vector_by_chunk[chunk.id]
        hits.append(_to_search_hit(chunk, document, dense_score=vector_hit.score))
    return sorted(hits, key=lambda hit: hit.dense_score or 0, reverse=True)


def _keyword_search(db: Session, knowledge_base_id: int, query: str, limit: int, filters: dict | None = None) -> list[SearchHit]:
    terms = _terms(query)
    if not terms:
        return []
    db_query = (
        db.query(Chunk, Document)
        .join(Document, Chunk.document_id == Document.id)
        .filter(Chunk.knowledge_base_id == knowledge_base_id, Chunk.deleted.is_(False))
    )
    filters = filters or {}
    if filters.get("document_id") is not None:
        db_query = db_query.filter(Chunk.document_id == filters["document_id"])
    if filters.get("source_types"):
        db_query = db_query.filter(Chunk.source_type.in_(filters["source_types"]))
    elif filters.get("source_type"):
        db_query = db_query.filter(Chunk.source_type == filters["source_type"])
    rows = db_query.order_by(Document.updated_at.desc(), Chunk.id.desc()).limit(1000).all()
    corpus = [_chunk_text(chunk) for chunk, _ in rows]
    doc_freq = Counter(term for text in corpus for term in set(_terms(text)))
    avg_len = sum(len(_terms(text)) for text in corpus) / max(len(corpus), 1)
    scored: list[SearchHit] = []
    for chunk, document in rows:
        if is_noise_chunk(_chunk_text(chunk)):
            continue
        score = _bm25_score(terms, _chunk_text(chunk), doc_freq, len(corpus), avg_len)
        if score <= 0:
            continue
        scored.append(_to_search_hit(chunk, document, bm25_score=score))
    return sorted(scored, key=lambda hit: hit.bm25_score or 0, reverse=True)[:limit]


def _rrf_fuse(dense_hits: list[SearchHit], keyword_hits: list[SearchHit], k: int = 60) -> list[SearchHit]:
    by_chunk: dict[int, SearchHit] = {}
    scores: Counter[int] = Counter()
    ranks: dict[int, dict[str, int]] = {}
    for source, hits in (("dense", dense_hits), ("bm25", keyword_hits)):
        for rank, hit in enumerate(hits, start=1):
            current = by_chunk.get(hit.chunk_id)
            if current is None:
                by_chunk[hit.chunk_id] = hit
            else:
                current.dense_score = current.dense_score or hit.dense_score
                current.bm25_score = current.bm25_score or hit.bm25_score
            scores[hit.chunk_id] += 1 / (k + rank)
            ranks.setdefault(hit.chunk_id, {})[source] = rank

    for chunk_id, hit in by_chunk.items():
        recency = float(hit.metadata.get("document_updated_ts") or 0)
        hit.score = scores[chunk_id] + recency * 0.000000001
        hit.metadata = {**hit.metadata, "rrf_score": scores[chunk_id], "rrf_ranks": ranks.get(chunk_id, {})}
    return sorted(by_chunk.values(), key=lambda hit: hit.score or 0, reverse=True)


def _rerank(query: str, hits: list[SearchHit]) -> list[SearchHit]:
    query_terms = set(_terms(query))
    for hit in hits:
        overlap = len(query_terms.intersection(_terms(hit.content)))
        hit.score = (hit.score or 0) + overlap * 0.05
        hit.metadata = {**hit.metadata, "rerank_overlap": overlap}
    return sorted(hits, key=lambda hit: hit.score or 0, reverse=True)


def _to_search_hit(
    chunk: Chunk,
    document: Document,
    dense_score: float | None = None,
    bm25_score: float | None = None,
) -> SearchHit:
    metadata = {
        **(chunk.meta or {}),
        "filename": document.filename,
        "file_type": document.file_type,
        "page_number": chunk.page_number,
        "heading_path": chunk.heading_path,
        "sheet_name": chunk.sheet_name,
        "row_start": chunk.row_start,
        "row_end": chunk.row_end,
        "source_type": chunk.source_type,
        "document_updated_at": document.updated_at.isoformat() if document.updated_at else None,
        "document_updated_ts": document.updated_at.timestamp() if document.updated_at else 0,
    }
    return SearchHit(
        chunk_id=chunk.id,
        document_id=chunk.document_id,
        knowledge_base_id=chunk.knowledge_base_id,
        content=_chunk_text(chunk),
        metadata=metadata,
        score=dense_score or bm25_score,
        dense_score=dense_score,
        bm25_score=bm25_score,
    )


def _bm25_score(query_terms: list[str], content: str, doc_freq: Counter, doc_count: int, avg_len: float) -> float:
    content_terms = _terms(content)
    if not content_terms:
        return 0.0
    term_freq = Counter(content_terms)
    score = 0.0
    k1 = 1.5
    b = 0.75
    for term in query_terms:
        if term not in term_freq:
            continue
        idf = math.log(1 + (doc_count - doc_freq[term] + 0.5) / (doc_freq[term] + 0.5))
        numerator = term_freq[term] * (k1 + 1)
        denominator = term_freq[term] + k1 * (1 - b + b * len(content_terms) / max(avg_len, 1))
        score += idf * numerator / denominator
    return score


def _terms(text: str) -> list[str]:
    return TOKEN_RE.findall(text.lower())


def _chunk_text(chunk: Chunk) -> str:
    return chunk.chunk_text or chunk.content


async def _embed_query_with_fallback(query: str) -> list[float] | None:
    try:
        vectors = await embed_texts([query])
        if vectors:
            return vectors[0]
    except Exception:
        pass
    try:
        vectors = await embed_texts([query, query])
        if vectors:
            return vectors[0]
    except Exception:
        return None
    return None

