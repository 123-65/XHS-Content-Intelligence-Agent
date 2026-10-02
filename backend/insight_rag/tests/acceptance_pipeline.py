from __future__ import annotations

import hashlib
import math
import re
import time
from dataclasses import dataclass, field
from pathlib import Path


SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".xlsx", ".png", ".jpg", ".jpeg", ".md", ".txt"}


@dataclass
class Source:
    file_name: str
    page: int | None = None
    row: int | None = None
    image_name: str | None = None
    sheet: str | None = None


@dataclass
class Chunk:
    id: int
    kb_id: str
    document_id: int
    content: str
    metadata: dict
    embedding: list[float] = field(default_factory=list)
    score: float = 0.0


@dataclass
class Document:
    id: int
    kb_id: str
    file_name: str
    file_type: str
    status: str
    text: str
    metadata: dict
    chunks: list[Chunk] = field(default_factory=list)


class MockEnterpriseRAG:
    """Offline acceptance double for the planned GraphRAG + multimodal stack."""

    def __init__(self, dim: int = 16) -> None:
        self.dim = dim
        self.documents: dict[int, Document] = {}
        self.knowledge_bases: dict[str, dict] = {}
        self.entities: dict[str, list[dict]] = {}
        self.relations: dict[str, list[dict]] = {}
        self.assets: dict[int, dict] = {}
        self.chunks: list[Chunk] = []
        self._doc_id = 0
        self._chunk_id = 0

    def create_knowledge_base(self, kb_id: str) -> dict:
        self.knowledge_bases[kb_id] = {"id": kb_id, "status": "ready", "index_version": 1}
        return self.knowledge_bases[kb_id]

    def delete_knowledge_base(self, kb_id: str) -> None:
        self.documents = {k: v for k, v in self.documents.items() if v.kb_id != kb_id}
        self.chunks = [chunk for chunk in self.chunks if chunk.kb_id != kb_id]
        self.entities.pop(kb_id, None)
        self.relations.pop(kb_id, None)
        self.knowledge_bases.pop(kb_id, None)

    def rebuild_index(self, kb_id: str) -> dict:
        self.knowledge_bases[kb_id]["index_version"] += 1
        self.knowledge_bases[kb_id]["status"] = "indexed"
        return self.knowledge_bases[kb_id]

    def upload(self, kb_id: str, file_path: Path, content: str | bytes | None = None) -> Document:
        if kb_id not in self.knowledge_bases:
            self.create_knowledge_base(kb_id)
        ext = file_path.suffix.lower()
        if ext not in SUPPORTED_EXTENSIONS:
            raise ValueError(f"Unsupported file type: {ext}")

        raw_text = self._parse(file_path, content)
        self._doc_id += 1
        doc = Document(
            id=self._doc_id,
            kb_id=kb_id,
            file_name=file_path.name,
            file_type=ext.lstrip("."),
            status="parsed",
            text=raw_text,
            metadata=self._metadata(file_path, raw_text),
        )
        if ext in {".png", ".jpg", ".jpeg"}:
            doc.status = "multimodal_indexed"
            self.assets[doc.id] = {
                "document_id": doc.id,
                "asset_type": "image",
                "image_name": file_path.name,
                "ocr_text": raw_text,
            }
        doc.chunks = self.chunk(doc)
        vectors = self.embed([chunk.content for chunk in doc.chunks])
        for chunk, vector in zip(doc.chunks, vectors, strict=True):
            chunk.embedding = vector
        self.documents[doc.id] = doc
        self.chunks.extend(doc.chunks)
        self._extract_graph(kb_id, doc)
        return doc

    def chunk(self, doc: Document, size: int = 36, overlap: int = 6) -> list[Chunk]:
        words = doc.text.split()
        if not words:
            return []
        chunks: list[Chunk] = []
        start = 0
        while start < len(words):
            part = " ".join(words[start : start + size])
            self._chunk_id += 1
            chunks.append(
                Chunk(
                    id=self._chunk_id,
                    kb_id=doc.kb_id,
                    document_id=doc.id,
                    content=part,
                    metadata={
                        "file_name": doc.file_name,
                        "page": 1 if doc.file_type == "pdf" else None,
                        "row": 2 if doc.file_type == "xlsx" else None,
                        "sheet": "Revenue" if doc.file_type == "xlsx" else None,
                        "image_name": doc.file_name if doc.file_type in {"png", "jpg", "jpeg"} else None,
                        "updated_rank": doc.id,
                    },
                )
            )
            if start + size >= len(words):
                break
            start += max(1, size - overlap)
        return chunks

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [self._hash_vector(text) for text in texts]

    def retrieve(self, kb_id: str, query: str, mode: str = "rag", top_k: int = 5, rerank: bool = False) -> list[Chunk]:
        query_terms = set(self._terms(query))
        query_vec = self._hash_vector(query)
        candidates = [chunk for chunk in self.chunks if chunk.kb_id == kb_id]
        scored: list[Chunk] = []
        for chunk in candidates:
            bm25_like = len(query_terms.intersection(self._terms(chunk.content)))
            dense = self._cosine(query_vec, chunk.embedding)
            graph_bonus = 0.3 if mode == "graphrag" and self._uses_graph(kb_id, query, chunk.content) else 0.0
            multimodal_bonus = 0.4 if mode == "multimodal" and chunk.metadata.get("image_name") else 0.0
            recency_bonus = chunk.metadata.get("updated_rank", 0) * 0.001
            fused = (bm25_like * 2.0) + dense + self._rrf([bm25_like, dense * 10]) + graph_bonus + multimodal_bonus + recency_bonus
            if rerank:
                fused += 0.2 if any(term in chunk.content.lower() for term in query_terms) else 0
            clone = Chunk(**{**chunk.__dict__, "score": fused})
            scored.append(clone)
        return sorted(scored, key=lambda item: item.score, reverse=True)[:top_k]

    def answer(self, kb_id: str, question: str, mode: str = "rag") -> dict:
        hits = self.retrieve(kb_id, question, mode=mode, top_k=5, rerank=True)
        citations = [self._citation(hit) for hit in hits]
        used_graph = mode == "graphrag" and any(self._uses_graph(kb_id, question, hit.content) for hit in hits)
        return {
            "answer": " ".join(hit.content for hit in hits[:5]),
            "citations": citations,
            "used_graph": used_graph,
            "hits": hits,
        }

    def _parse(self, file_path: Path, content: str | bytes | None) -> str:
        ext = file_path.suffix.lower()
        if isinstance(content, bytes):
            content = content.decode("utf-8", errors="ignore")
        text = content or file_path.stem.replace("_", " ")
        if ext == ".xlsx":
            return "Sheet Revenue row 2 column Product ARR retention. ACME Q2 revenue 42 million and churn 3 percent."
        if ext in {".png", ".jpg", ".jpeg"}:
            return f"OCR image {file_path.name}: architecture diagram shows Milvus, PostgreSQL Citus coordinator, worker nodes, GraphRAG entities."
        if ext == ".pdf":
            return f"Page 1 {text} GraphRAG uses entities and relations. Milvus hybrid retrieval prefers latest uploaded documents."
        if ext == ".docx":
            return f"{text} Word policy explains asyncpg conversation memory and rerank workflow."
        return str(text)

    def _metadata(self, file_path: Path, text: str) -> dict:
        ext = file_path.suffix.lower()
        if ext == ".xlsx":
            return {"sheets": [{"name": "Revenue", "rows": 2, "columns": ["Product", "ARR", "Retention"]}]}
        return {"length": len(text)}

    def _extract_graph(self, kb_id: str, doc: Document) -> None:
        entities = self.entities.setdefault(kb_id, [])
        relations = self.relations.setdefault(kb_id, [])
        for name in ["GraphRAG", "Milvus", "PostgreSQL", "Citus", "ACME"]:
            if name.lower() in doc.text.lower():
                entities.append({"name": name, "document_id": doc.id, "summary": f"{name} appears in {doc.file_name}"})
        if "GraphRAG" in doc.text and "relations" in doc.text:
            relations.append({"head": "GraphRAG", "relation": "USES", "tail": "relations", "document_id": doc.id})
        if "Citus" in doc.text and "worker" in doc.text.lower():
            relations.append({"head": "Citus", "relation": "DISTRIBUTES_TO", "tail": "worker nodes", "document_id": doc.id})

    def _uses_graph(self, kb_id: str, query: str, content: str) -> bool:
        graph_terms = {item["name"].lower() for item in self.entities.get(kb_id, [])}
        graph_terms.update(rel["head"].lower() for rel in self.relations.get(kb_id, []))
        terms = set(self._terms(query + " " + content))
        return bool(graph_terms.intersection(terms))

    def _citation(self, hit: Chunk) -> dict:
        return {
            "file_name": hit.metadata["file_name"],
            "page": hit.metadata.get("page"),
            "row": hit.metadata.get("row"),
            "sheet": hit.metadata.get("sheet"),
            "image_name": hit.metadata.get("image_name"),
            "score": hit.score,
        }

    def _hash_vector(self, text: str) -> list[float]:
        digest = hashlib.sha256(text.encode("utf-8")).digest()
        return [((digest[i % len(digest)] / 255.0) * 2) - 1 for i in range(self.dim)]

    @staticmethod
    def _terms(text: str) -> list[str]:
        return re.findall(r"[a-z0-9]+", text.lower())

    @staticmethod
    def _cosine(left: list[float], right: list[float]) -> float:
        dot = sum(a * b for a, b in zip(left, right, strict=True))
        denom = math.sqrt(sum(a * a for a in left)) * math.sqrt(sum(b * b for b in right))
        return dot / denom if denom else 0.0

    @staticmethod
    def _rrf(scores: list[float], k: int = 60) -> float:
        ranked = sorted(enumerate(scores), key=lambda item: item[1], reverse=True)
        return sum(1 / (k + rank + 1) for rank, _ in enumerate(ranked))


class MockCitusCluster:
    def __init__(self, workers: int = 2) -> None:
        self.workers = {f"worker-{index}": True for index in range(1, workers + 1)}
        self.rows: list[dict] = []

    def insert_chunks(self, count: int, kb_id: str = "kb-main") -> None:
        for index in range(count):
            worker = list(self.workers)[index % len(self.workers)]
            self.rows.append({"id": index + 1, "knowledge_base_id": kb_id, "worker": worker, "content": f"chunk {index}"})

    def distribution(self) -> dict[str, int]:
        return {worker: sum(1 for row in self.rows if row["worker"] == worker) for worker in self.workers}

    def query(self, kb_id: str | None = None, min_id: int | None = None) -> list[dict]:
        down = [worker for worker, alive in self.workers.items() if not alive]
        if down:
            raise ConnectionError(f"Citus worker unavailable: {', '.join(down)}")
        rows = self.rows
        if kb_id:
            rows = [row for row in rows if row["knowledge_base_id"] == kb_id]
        if min_id:
            rows = [row for row in rows if row["id"] >= min_id]
        return rows

    def stop_worker(self, worker: str) -> None:
        self.workers[worker] = False


def measure_latency(func, limit_seconds: float) -> float:
    start = time.perf_counter()
    func()
    elapsed = time.perf_counter() - start
    assert elapsed <= limit_seconds
    return elapsed
