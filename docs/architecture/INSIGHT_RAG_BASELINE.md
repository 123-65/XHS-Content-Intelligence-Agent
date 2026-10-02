# InsightRAG Baseline

Date: 2026-10-02

Source: `123-65/InsightRAG-Studio`, branch `master`, commit `de1bb56f61b16bf18468f62b8a00eb833cf47c4e`.

## Product Role

InsightRAG 是 XHS Content Intelligence Agent 内部、可持续演进的 Knowledge Retrieval Engine。它负责把用户授权的个人知识资料转换为可追踪的检索结果，未来为内容研究与决策提供知识证据。

它不负责主 Conversational Agent、Workflow routing、小红书市场研究、内容策略、草稿生成或账号效果分析。顶层 Agent 仍是现有 Pydantic AI Conversational Agent。本轮只完成代码迁入与 baseline 验证，没有新增 Agent Tool，也没有连接任何现有 Workflow。

## Imported Scope

保留：

- RAG 后端 Python 源码：core、models、schemas、services、knowledge API；
- parser、chunker、embedding client、Milvus vector store、hybrid retrieval；
- 文档/Chunk/Embedding/来源元数据模型；
- 上游依赖版本参考；
- 具备回归价值的单元测试与 mock acceptance tests。

未迁入：

- 嵌套 `.git`、`.github` 和 submodule；
- Vue UI、截图和前端构建产物；
- Demo seed 脚本；
- `.env`、API Key、Cookie 或 Credential；
- 上传文件、PostgreSQL 数据、Milvus index、对象存储、日志和缓存。

上游 Chat、Graph 与 API 文件随完整后端 baseline 保留，但属于遗留能力，不是主项目对该模块的新职责，也没有注册到主应用。

## Current Architecture

```text
File upload
  -> extension validation
  -> parser / PDF page extraction
  -> text cleaning and noise filtering
  -> paragraph + sentence-aware chunking
  -> PostgreSQL chunk/source metadata
  -> OpenAI-compatible batch embedding
  -> Milvus HNSW/COSINE vector index
  -> Dense retrieval + in-process BM25
  -> Reciprocal Rank Fusion
  -> lexical-overlap rerank
  -> SearchHit with source metadata
```

Document text and citation metadata live in PostgreSQL. Milvus stores vectors plus identifiers used to join back to PostgreSQL.

## Current Technology

The following is derived from source code, not the upstream README:

| Area | Actual baseline |
| --- | --- |
| Runtime | Python 3.11 in upstream Dockerfile |
| API | FastAPI 0.115.6 / Uvicorn 0.34.0 |
| Settings | pydantic-settings 2.7.1 |
| Metadata DB | SQLAlchemy 2.0.36 with PostgreSQL/psycopg; asyncpg also declared |
| Vector store | Milvus via pymilvus 2.5.10 |
| Vector index | HNSW by default, COSINE metric, `M=16`, `efConstruction=200` |
| Embedding | OpenAI-compatible async client; default Qwen `text-embedding-v3`, dimension 1024 |
| Parser | native text/Markdown, PyMuPDF with pypdf fallback, python-docx, openpyxl |
| Object storage | MinIO/S3-compatible boto3, Alibaba OSS, or local storage |
| Retrieval | Milvus dense search + custom in-process BM25 + RRF |
| Rerank | query/chunk lexical overlap boost; not a learned reranker |
| Graph layer | LangGraph exists for upstream answer generation, but is outside the new module role |

Supported extensions in code: `.txt`, `.md`, `.pdf`, `.docx`, `.xlsx`, `.png`, `.jpg`, `.jpeg`, `.webp`. Image extensions are accepted by the upload route through the multimodal path; `parse_document` itself handles only the text/document formats.

## Parsing and Chunk Strategy

- PDF: PyMuPDF text extraction first, pypdf fallback; page markers preserve page number.
- TXT/Markdown: UTF-8 variants followed by GB18030/GBK fallback.
- DOCX: paragraph text.
- XLSX: worksheet title plus tab-separated rows.
- Cleaning removes configured trial/watermark/page/URL patterns.
- Default chunk size is 800 characters with 120-character overlap.
- Paragraphs are preferred, then sentence punctuation; very long units are hard-sliced by character count.
- Token count is only a rough Chinese-character/other-character estimate.

## Retrieval Baseline

Default query flow requests `max(top_k * 4, 20)` dense and keyword candidates, merges them with reciprocal rank fusion (`k=60`), optionally applies a lexical-overlap boost, filters noise chunks, and returns `top_k` (default API value 5).

Returned `SearchHit` contains chunk ID, document ID, knowledge-base ID, content, fused score, dense score, BM25 score and metadata. Metadata includes filename, file type, page number, heading/sheet/row fields when available, source type and document update time. This is a useful starting point for future `KnowledgeSearchHit` design.

## Current Strengths

- Clear separation between PostgreSQL source metadata and Milvus vectors.
- Stable chunk/document/knowledge-base identities and embedding hashes.
- Idempotent indexing skips unchanged, already indexed chunks.
- Dense and keyword result deduplication through RRF.
- Page, filename, object-key and source-type metadata paths exist.
- PDF noise cleaning and deleted-chunk filtering have tests.
- Vector collection schema validation fails clearly on outdated numeric identifier schemas.
- Imported baseline test suite passes: `56 passed` on the current project environment.

## Current Problems

The user has already identified that retrieval quality is not good enough. Code inspection shows several likely causes:

- Chunk boundaries use character length rather than model tokens or document structure; long units may be hard-cut.
- The default 800/120 strategy is global and not adapted by file type, heading, table or knowledge domain.
- Chinese BM25 tokenization uses a regex that can treat a long contiguous Chinese sequence as one term; recall can be weak.
- BM25 loads at most the latest 1000 database rows and calculates statistics in application memory per query.
- The “rerank” step is only exact lexical overlap, not a cross-encoder or LLM reranker.
- No explicit relevance threshold is applied after fusion/reranking.
- Dense embedding errors and Milvus search errors can silently degrade to keyword-only retrieval.
- Query embedding contains a second-call fallback using duplicated query input; failure/fallback observability is insufficient.
- Embedding dimension rejection triggers a retry without `dimensions`, which changes request semantics.
- Scores from dense, BM25, RRF and overlap boost are not normalized into one interpretable confidence contract.
- Source metadata is rich in the data model but depends on each ingestion path populating it consistently.
- Image OCR and caption functions fall back to mock text when unavailable, which is unsafe for production evidence without explicit provenance.
- Tests prove deterministic code paths with fakes/mocks; they do not establish real Chinese retrieval quality, real Milvus behavior or real remote embedding quality.

## Baseline Verification

Command:

```powershell
$env:PYTHONPATH = "backend"
.\.venv\Scripts\python.exe -m pytest backend/insight_rag/tests -q
```

Result: `56 passed in 1.80s`.

This verifies migration/import integrity and the upstream unit/mock behavior. It does not claim live PostgreSQL, Milvus, object storage, OCR, embedding provider or end-to-end retrieval acceptance.

## Optimization Plan

Proceed in this order:

1. **RAG Baseline Eval** — freeze a Chinese dataset, queries, relevance labels, Recall@K/MRR/nDCG, citation completeness and latency.
2. **Chunk Optimization** — evaluate structure-aware and file-type-aware segmentation against the frozen set.
3. **Hybrid Retrieval** — replace regex tokenization with a measured Chinese lexical path; define fusion and failure semantics.
4. **Rerank** — introduce an independently evaluated domestic/local reranker and explicit relevance threshold.
5. **Retrieval Evaluation** — add regression gates, source-traceability assertions, fallback telemetry and cost/latency budgets.
6. **Agent Integration** — only after the independent engine is stable, define a narrow provider contract and then consider a Pydantic AI knowledge tool.

No algorithm optimization or Agent integration was performed during this import.
