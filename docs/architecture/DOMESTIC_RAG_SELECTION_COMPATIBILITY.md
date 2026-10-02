# Domestic RAG Selection & Compatibility Report

Date: 2026-10-01

Decision: use LangChain-Chatchat as an isolated retrieval service candidate. Do not install it into the existing backend environment.

## 1. Previous R2R Status

R2R is abandoned and must not be used, configured, started, or integrated.

The expected sibling directory `../R2R` was not present during this inspection, and no R2R references were found in `xhs-growth-agent`. No directory was deleted by this work. Because the directory does not exist, no marker was written inside it. If an external ZIP extraction is restored later, it must be treated as `ABANDONED / NOT USED` until the user explicitly decides whether to delete it.

## 2. Selected Framework

Selected candidate: `chatchat-space/Langchain-Chatchat`.

Its role is limited to document ingestion, parsing, chunking, embedding, knowledge-base management, vector/BM25 retrieval, and source-bearing retrieval results. Chatchat Agent, WebUI, Streamlit UI, database agent, search agent, and answer generation are out of scope.

## 3. Domestic Origin

The official repository describes a Chinese-scenario-friendly, locally deployable knowledge-base solution and is maintained under the `chatchat-space` organization. This report uses "domestic" as a project-selection classification, not as a supply-chain guarantee: transitive Python dependencies remain international open-source packages.

Official project: <https://github.com/chatchat-space/Langchain-Chatchat>

## 4. License

Apache License 2.0, as declared by the official repository.

License: <https://github.com/chatchat-space/Langchain-Chatchat/blob/master/LICENSE>

## 5. Current Version

- Latest PyPI package observed: `langchain-chatchat==0.3.1.3`
- PyPI upload date: 2024-07-23
- Latest GitHub release label: `v0.3.1`
- Repository package metadata on `master` still reports `0.3.1.3`

Sources: <https://pypi.org/project/langchain-chatchat/> and <https://github.com/chatchat-space/Langchain-Chatchat/releases>

## 6. Maintenance Status

The repository is not archived. GitHub reported the last push and latest commit at `2025-11-10T09:27:42Z`. As of this report, the packaged release is old and the default branch has had no push for roughly eleven months. Classification: usable for a pinned spike, but maintenance cadence is low and production adoption requires an exit plan.

Do not track `master` implicitly. Pin the package version and validate every upgrade.

## 7. Python Compatibility

Official documentation says Python 3.8-3.11. Current repository metadata narrows the supported range to Python `>=3.10,<3.12`; PyPI metadata also explicitly excludes Python 3.12.

The isolated dependency resolution and package/CLI smoke test succeeded on `python:3.11-slim` with `langchain-chatchat==0.3.1.3`.

Result: Python 3.11 is the required baseline for this project.

## 8. Existing Backend Compatibility

Observed backend container:

- Python `3.12.14`
- FastAPI `0.141.1`
- Pydantic `2.13.5`
- pydantic-settings `2.15.0`
- OpenAI SDK `3.19.2`
- Pydantic AI `2.51.0`
- LangChain packages: not installed

Observed local `.venv`: Python `3.13.5` with the same main application package versions.

Chatchat `0.3.1.3` resolves, among other pins, FastAPI `<0.110`, Pydantic `<2.8`, LangChain `0.1.17`, langchain-community `0.0.36`, langchain-openai `0.0.6`, NumPy `<1.25`, and HTTP/parser/UI dependencies. A clean Python 3.11 CLI smoke test also emitted an internal `wheel`/`packaging` incompatibility warning and a Requests dependency warning.

Conclusion: sharing the backend Python environment is rejected. The backend must not be downgraded.

## 9. Deployment Mode

Use an independent `knowledge-rag` Python 3.11 process/container. Install from PyPI first:

```text
langchain-chatchat==0.3.1.3
```

The official CLI provides `chatchat init`, `chatchat kb`, and `chatchat start`. Source checkout is not needed for the initial spike.

Chatchat and any model-serving framework must also remain in separate environments. The official documentation explicitly recommends this separation.

## 10. Knowledge APIs

The official server code exposes functions/routes for:

- create, list, update, and delete knowledge bases;
- upload, list, download, update, and delete knowledge-base documents;
- rebuild a vector store;
- direct `search_docs` retrieval using query, knowledge-base name, top-k, score threshold, optional filename, and first-level metadata filters.

For integration, `ChatchatKnowledgeProvider` must be the only component that knows Chatchat HTTP shapes. Vue must never call Chatchat directly.

## 11. Supported File Types

The current loader registry includes HTML/MHTML, Markdown, JSON/JSONL, CSV, PDF, DOCX, PPT/PPTX, common images, EML/MSG, RST, RTF, TXT, XML, EPUB, ODT, TSV, XLS/XLSX, IPYNB, Python, SRT, TOML, and ENEX.

The first project phase remains limited to user-approved PDF, DOCX, Markdown, TXT, papers, industry material, project reviews, technical notes, personal experience, and historical original content. Loader support does not expand the business domain automatically.

## 12. Chunking

The upload API accepts `chunk_size`, `chunk_overlap`, and `zh_title_enhance`. Chatchat stores document chunks with metadata and vector-store identity.

Chunking defaults must be pinned in the future provider configuration; they must not be scattered through the business layer.

## 13. Embedding

Frozen provider/model for the first spike:

- provider: Alibaba Cloud Model Studio;
- model: `qwen3.7-text-embedding`;
- dimensions: `1024`;
- region: Beijing, derived from the existing project configuration;
- endpoint type: official regional OpenAI-compatible `/embeddings` endpoint.

The independent Python 3.11 request succeeded against the real endpoint and returned the requested model with a non-empty 1024-dimensional vector. No credential, full endpoint, workspace identifier, or token was copied into this report or into Chatchat YAML.

The official Chatchat 0.3.1.3 `platform_type=openai` path is not directly compatible with this endpoint. Its pinned `langchain-openai==0.0.6` `OpenAIEmbeddings` client performs length-safe tokenization and submits token-ID arrays. Model Studio rejected that payload because this model requires `input` to be an array of strings.

The proposed one-parameter override was checked against the actual installed constructor before implementation. In `langchain-openai==0.0.6`, `OpenAIEmbeddings` has no `check_embedding_ctx_length` constructor parameter or Pydantic field. Its relevant controls are `tiktoken_enabled`, token limits, chunk size, retry, and client fields; none is the authorized parameter. Passing the newer-version field would therefore be an unsupported guess rather than a valid compatibility fix.

This is now a confirmed provider-adapter compatibility boundary, not an environment or credential blocker. Per the spike constraint, no custom adapter was added.

## 14. Vector Retrieval

The default knowledge-base vector store is FAISS. Other service implementations exist for Milvus, PostgreSQL/PGVector, Elasticsearch, ChromaDB, Relyt, and Zilliz.

For the spike, use the default FAISS path to minimize infrastructure. Do not introduce an external vector database.

## 15. BM25/KNN

The default FAISS knowledge-base search calls the official `ensemble` retriever. That retriever combines:

- FAISS similarity search with score threshold;
- `BM25Retriever` with `jieba.lcut_for_search`;
- weights `0.5 / 0.5`.

Therefore the selected version already supplies BM25 + KNN hybrid retrieval, and the project must not reimplement BM25, cosine similarity, or a vector-search engine.

Known risk: the official implementation constructs BM25 from all documents currently loaded in the FAISS docstore on each retriever construction, and an empty docstore has produced a reported unpacking error. The spike must test empty-KB behavior and non-empty retrieval separately.

## 16. Source Metadata

Direct search results are returned as document dictionaries with page content, metadata, and vector-store document ID. Upload/add operations also return generated IDs with metadata. The stored metadata includes source information used by deletion and citation paths.

Spike acceptance requires all of:

- retrieved text contains `KnowledgeBoundaryAlpha`;
- source filename is `test.md`;
- a stable returned document/chunk identity is present;
- no answer-generation LLM is invoked.

## 17. Comparison With

### RAGFlow

RAGFlow has stronger document processing and a broad RAG/Agent platform, but its official deployment recommends at least 4 CPU, 16 GB RAM, and 50 GB disk and includes multiple storage/messaging services. It is too heavy for this MVP baseline.

### QAnything

QAnything provides complete BM25 + embedding hybrid retrieval and Chinese-oriented deployment, but its official v2 deployment calls for at least 20 GB RAM and a Docker-based full system. It is not the lightweight choice for this project.

### MaxKB

MaxKB is an enterprise Agent platform with RAG pipelines, workflow engine, function library, and MCP tooling. Those responsibilities overlap the existing Pydantic AI Agent and workflow architecture.

### FastGPT

FastGPT is an AI Agent/workflow platform with its own orchestration and knowledge-base product surface. It has good hybrid retrieval, but its TypeScript/platform stack and product responsibilities overlap the current Python application.

LangChain-Chatchat is selected because it is Python/FastAPI-based, can be package-installed, exposes knowledge-management and retrieval capabilities, supports Chinese scenarios and BGE embeddings, and can be isolated behind a narrow provider adapter.

## 18. Final Architecture

```text
Vue
  -> existing FastAPI
    -> KnowledgeService
      -> ChatchatKnowledgeProvider
        -> isolated LangChain-Chatchat service
          -> parser/chunker
          -> remote domestic embedding API
          -> FAISS + BM25 ensemble retrieval
```

The existing Pydantic AI Conversational Agent remains the top-level agent. Future generation remains Pydantic AI + Qwen. External XHS Profile/Note/Comment/Public Metrics remain on `XHS MCP -> Research Evidence` and must never be ingested automatically.

## 19. Integration Risks

- Old PyPI release and slow upstream maintenance cadence.
- Hard dependency pins conflict with the current backend.
- Package installs WebUI/OCR/Agent dependencies even when this project does not use them.
- Clean-environment smoke test emitted `packaging` and Requests dependency warnings.
- Alibaba Model Studio compatibility is proven for a direct string-array request but fails through Chatchat 0.3.1.3's pinned OpenAI embedding wrapper because that wrapper sends token-ID arrays.
- The authorized `check_embedding_ctx_length=False` override is unavailable in the pinned `langchain-openai==0.0.6` constructor. It was not implemented or smuggled through `model_kwargs`.
- A working project-owned solution would require a broader adapter that bypasses `_get_len_safe_embeddings` and calls the provider with raw strings, or a separately validated dependency upgrade/provider change. Either is outside this authorization and needs a new decision.
- Chatchat defaults may silently select another embedding name if the configured model is unavailable; the provider must fail closed and verify the active embedding model.
- Chatchat's error logger interprets the provider message prefix `<400>` as a Loguru color tag and raises a secondary `ValueError`, obscuring the original 400 unless the nested traceback is inspected.
- Hybrid retrieval implementation has empty-store and scaling risks.
- API contracts are not treated as stable across unpinned releases.

## 20. Recommended Embedding

Primary selection remains frozen as Alibaba Cloud Model Studio `qwen3.7-text-embedding` with 1024 dimensions. The direct real API call passed, so changing provider or model is not justified by this result.

The next decision is whether to authorize a minimal isolated Chatchat embedding factory override that disables token-ID input conversion. Do not change the backend environment and do not introduce a second provider account.

## 21. Spike Plan

Executed:

- isolated Python 3.11 dependency/runtime: PASS;
- real Model Studio embedding smoke test: PASS, model identity and 1024 dimensions verified;
- Chatchat API service and docs endpoint: PASS;
- runtime model declaration: PASS, exact embedding model selected and no fallback configured;
- test knowledge-base metadata row: created with FAISS and the exact embedding model;
- FAISS initialization embedding: FAIL due to token-array versus string-array payload incompatibility;
- document upload, parsing, chunking, index creation, retrieval, source traceability, and hybrid runtime verification: not executed because the prerequisite index creation failed;
- mocks: 0; fallback: 0; generation-model calls: 0.

The authorized constructor-flag approach is unsupported by the pinned dependency, so execution stopped before code changes or further provider calls. Reassess one of: a broader project-owned raw-string adapter, a Chatchat-compatible domestic embedding provider, a local BGE embedding, or whether to retain Chatchat. Do not begin formal business integration.

## 22. Files Changed

- `docs/architecture/DOMESTIC_RAG_SELECTION_COMPATIBILITY.md`
- `knowledge-rag/spike/README.md`
- `knowledge-rag/spike/Dockerfile`
- `knowledge-rag/spike/.dockerignore`
- `knowledge-rag/spike/.gitignore`
- `knowledge-rag/spike/embedding_smoke.py`
- `knowledge-rag/spike/run_chatchat.py`
- `knowledge-rag/spike/requirements.txt`
- `knowledge-rag/spike/test.md`
- `docs/testing/RAG_KNOWLEDGE_SPIKE.md`

No backend application, frontend, database, migration, workflow, Agent, or R2R file was changed.

## 23. Git

No `git add`, commit, reset, restore, clean, or stash command was run. Existing dirty worktree changes were left untouched.

## 24. Final Status

```text
RAG KNOWLEDGE SPIKE = COMPATIBILITY_OVERRIDE_UNSUPPORTED
```

Compatibility: PASS with mandatory process/environment isolation.

Real Model Studio embedding acceptance: PASS (`qwen3.7-text-embedding`, 1024 dimensions).

Real Chatchat ingestion/retrieval acceptance: BLOCKED before ingestion because the official Chatchat 0.3.1.3 OpenAI embedding path transforms strings to token-ID arrays that this endpoint rejects, while its pinned embedding constructor does not support the authorized disable flag. No compatibility code or custom adapter was added.

