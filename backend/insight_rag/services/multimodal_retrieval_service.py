from __future__ import annotations

from collections import Counter

from sqlalchemy.orm import Session

from insight_rag.schemas.chat import SearchHit
from insight_rag.services.retrieval_service import _rerank, retrieve_chunks
from insight_rag.services.vector_store import MilvusVectorStore


MULTIMODAL_SOURCE_GROUPS = {
    "text": ["text", "graph_summary"],
    "image": ["image_caption"],
    "ocr": ["ocr"],
    "table": ["table", "table_image"],
}


async def retrieve_multimodal_chunks(
    db: Session,
    knowledge_base_id: int,
    query: str,
    top_k: int = 5,
    rerank: bool = True,
    filters: dict | None = None,
    vector_store: MilvusVectorStore | None = None,
) -> list[SearchHit]:
    filters = filters or {}
    per_group_limit = max(top_k * 3, 12)
    ranked_lists: list[list[SearchHit]] = []
    for mode, source_types in MULTIMODAL_SOURCE_GROUPS.items():
        mode_filters = {**filters, "source_types": source_types}
        hits = await retrieve_chunks(
            db,
            knowledge_base_id,
            query,
            top_k=per_group_limit,
            rerank=False,
            filters=mode_filters,
            vector_store=vector_store,
        )
        for hit in hits:
            hit.retrieval_mode = mode
        ranked_lists.append(hits)

    fused = _rrf_fuse_lists(ranked_lists)
    if rerank:
        fused = _rerank(query, fused)
    return fused[:top_k]


def _rrf_fuse_lists(ranked_lists: list[list[SearchHit]], k: int = 60) -> list[SearchHit]:
    by_chunk: dict[int, SearchHit] = {}
    scores: Counter[int] = Counter()
    ranks: dict[int, dict[str, int]] = {}
    for hits in ranked_lists:
        for rank, hit in enumerate(hits, start=1):
            current = by_chunk.get(hit.chunk_id)
            if current is None:
                by_chunk[hit.chunk_id] = hit
            else:
                current.dense_score = current.dense_score or hit.dense_score
                current.bm25_score = current.bm25_score or hit.bm25_score
            label = hit.metadata.get("source_type") or hit.retrieval_mode
            scores[hit.chunk_id] += 1 / (k + rank)
            ranks.setdefault(hit.chunk_id, {})[str(label)] = rank

    for chunk_id, hit in by_chunk.items():
        hit.score = scores[chunk_id]
        hit.metadata = {**hit.metadata, "multimodal_rrf_score": scores[chunk_id], "multimodal_rrf_ranks": ranks.get(chunk_id, {})}
    return sorted(by_chunk.values(), key=lambda hit: hit.score or 0, reverse=True)

