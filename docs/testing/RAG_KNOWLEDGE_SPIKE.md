# RAG Knowledge Spike Report

Date: 2026-10-01

## 1. Embedding Provider

Alibaba Cloud Model Studio, using the project's existing credential and compatible base configuration without copying either value.

Configuration presence checked: `LLM_API_KEY=present`, `LLM_BASE_URL=present`, `DASHSCOPE_API_KEY=absent`, explicit workspace ID variables absent, and explicit region variables absent. No secret or full endpoint is recorded.

## 2. Model

`qwen3.7-text-embedding`. The direct response reported the same model identifier.

## 3. Region

Beijing. This was derived from the existing configured compatible endpoint, not inferred from machine geography. No Singapore endpoint was used.

## 4. Endpoint Type

Official Alibaba Model Studio regional OpenAI-compatible `/embeddings` API. The full endpoint and credential are intentionally omitted.

## 5. Dimension

Requested: `1024`. Actual returned vector length: `1024`.

## 6. Embedding Smoke Test

PASS. An independent Python 3.11 process submitted the specified sentence to the real model and received HTTP 200, the exact requested model, and a non-empty vector. This was not a mock and did not use fallback.

## 7. Chatchat Runtime

PASS for service startup only. `langchain-chatchat==0.3.1.3` ran in an isolated Python 3.11 container, and its API documentation endpoint returned HTTP 200. It was not installed in the backend Python 3.12 environment.

Runtime configuration resolved `qwen3.7-text-embedding` through Chatchat's documented model-platform settings with `platform_type=openai`. Credentials were injected from the existing read-only environment at process startup and were not written to YAML.

## 8. Knowledge Base

PARTIAL. The metadata row `knowledge_boundary_spike` exists with `vs_type=faiss`, `embed_model=qwen3.7-text-embedding`, and `file_count=0`. The initial empty-document FAISS initialization failed, so no usable index was created.

## 9. Test Document

Prepared fixture: `knowledge-rag/spike/test.md`, containing `RAG-KB-TEST-92817` and `KnowledgeBoundaryAlpha`. Upload was not attempted after the prerequisite KB index initialization failed.

## 10. Parsing

NOT EXECUTED. No parse result can be claimed.

## 11. Chunking

NOT EXECUTED. No chunk identity or count exists.

## 12. Embedding

Direct provider embedding: PASS.

Chatchat embedding: FAIL. Chatchat 0.3.1.3 pins `langchain-openai==0.0.6`; its `OpenAIEmbeddings` length-safe path converts the input string into token-ID arrays. Model Studio returned HTTP 400 because `qwen3.7-text-embedding` requires an array of strings. Chatchat's official embedding factory supplies only model, base URL, API key, and proxy.

Constructor verification then proved that this installed `OpenAIEmbeddings` version has neither a `check_embedding_ctx_length` signature parameter nor a Pydantic field. The authorized one-parameter fix is therefore unavailable in this version.

No custom adapter was written, as required by the spike instructions.

## 13. Retrieval

NOT EXECUTED. Status: `RETRIEVAL_FAILED` as a downstream consequence of `CHATCHAT_CONFIG_BLOCKED`; no positive query result is claimed.

## 14. Top-K Evidence

Unavailable. `KnowledgeBoundaryAlpha` was not retrieved because ingestion and index creation did not complete.

## 15. Source Traceability

Unavailable. Intended source filename was `test.md`; actual returned source, chunk/document identity, score, and page are all `null / unavailable` because no retrieval response exists.

## 16. Negative Query

NOT EXECUTED. No behavior for `法国首都是什么？` is claimed and no threshold result was fabricated.

## 17. Vector Retrieval

NOT VERIFIED. The knowledge-base metadata selected FAISS, but the FAISS index initialization failed before a searchable index existed.

## 18. Hybrid Retrieval

NOT VERIFIED. The installed FAISS service source routes successful searches through the ensemble retriever, but this runtime never reached a search. Source presence plus configuration is insufficient runtime evidence, so BM25 + FAISS KNN is not claimed as verified.

## 19. Mock / Fallback

Mock calls: `0`. Fallback calls: `0`. The failed Chatchat call used the exact configured embedding model and did not silently select another model.

## 20. LLM Calls

Generation-model calls: `0`. Only the embedding endpoint and Chatchat knowledge-base management endpoints were called. No chat-completion or generated answer was used as evidence.

## 21. Remaining Limitations

- Chatchat 0.3.1.3 does not expose an embedding-factory hook for this behavior.
- Its pinned `langchain-openai==0.0.6` does not implement `check_embedding_ctx_length`, so the authorized constructor-flag override cannot be applied.
- A broader raw-string embedding subclass/factory, dependency upgrade, alternate officially supported domestic provider, or local BGE path requires a separate architectural decision.
- Chatchat's Loguru handling raises a secondary error when the upstream message contains `<400>`, making the original provider error less visible.
- Ingestion, positive and negative retrieval, source traceability, vector retrieval, and hybrid retrieval remain unverified.
- The failed attempt retained a metadata-only KB row with zero files; no database or volume was deleted.

## 22. Files Changed

- `docs/architecture/DOMESTIC_RAG_SELECTION_COMPATIBILITY.md`
- `docs/testing/RAG_KNOWLEDGE_SPIKE.md`
- `knowledge-rag/spike/Dockerfile`
- `knowledge-rag/spike/.dockerignore`
- `knowledge-rag/spike/.gitignore`
- `knowledge-rag/spike/embedding_smoke.py`
- `knowledge-rag/spike/run_chatchat.py`

Previously prepared spike files remain `knowledge-rag/spike/README.md`, `knowledge-rag/spike/requirements.txt`, and `knowledge-rag/spike/test.md`.

No backend application dependency, database migration, frontend, Agent, workflow, or production provider file was changed.

## 23. Git

No `git add`, commit, reset, restore, clean, or stash command was run. The pre-existing dirty worktree was preserved.

## 24. Final Status

```text
RAG KNOWLEDGE SPIKE = COMPATIBILITY_OVERRIDE_UNSUPPORTED
```

Passing evidence: real embedding API, exact model, 1024 dimensions, isolated Python 3.11 Chatchat service, zero mocks, zero fallbacks, and zero generation-model calls.

Blocking evidence: the official Chatchat 0.3.1.3 OpenAI embedding path sends token-ID arrays while the selected Model Studio embedding endpoint accepts string arrays, and its pinned client lacks the authorized disable flag. Therefore the required real ingestion and retrieval acceptance criteria are not yet met.

## Embedding Compatibility Fix

### 1. Root Cause

Chatchat 0.3.1.3 constructs `langchain-openai==0.0.6` `OpenAIEmbeddings`. That client takes the length-safe path and converts strings into token-ID arrays, but the selected Model Studio endpoint requires a string array.

### 2. Override Location

No override file was created. The proposed location was the project-owned `knowledge-rag/compatibility/` layer, but constructor validation failed before implementation.

### 3. Why No Upstream Modification

Editing `site-packages/langchain_openai` or `site-packages/chatchat` was prohibited and would create an untraceable fork. Neither directory was modified.

### 4. Before Request Shape

Observed through the real Chatchat call: `input` became a token-ID array and was rejected with HTTP 400. Secrets and the full endpoint were not logged in this report.

### 5. After Request Shape

Not available. The installed constructor does not support `check_embedding_ctx_length=False`, so no altered request was sent and no result was fabricated.

### 6. Real Embedding Verification

The earlier independent raw-string call remains PASS: real `qwen3.7-text-embedding`, HTTP 200, non-empty 1024-dimensional vector, mock 0, fallback 0. No second call was made because the required override could not be constructed.

### 7. Ingestion

NOT EXECUTED after compatibility validation. The retained KB metadata row still has zero files.

### 8. Chunking

NOT EXECUTED.

### 9. Indexing

NOT VERIFIED. FAISS initialization previously failed on the first Chatchat embedding request.

### 10. Retrieval

NOT EXECUTED. Neither positive nor negative retrieval was run.

### 11. Source Traceability

NOT AVAILABLE. No actual source filename, document ID, chunk ID, score, or locator was returned by retrieval.

### 12. Hybrid Status

`VECTOR RETRIEVAL = NOT VERIFIED`. `HYBRID RETRIEVAL = NOT VERIFIED`.

### 13. Remaining Limitations

The exact authorized fix exists in newer API surfaces but not in the pinned client. Continuing would require a second, broader patch: overriding `embed_documents`/the length-safe method, changing the dependency set, selecting another provider, or using local BGE. Per the stop condition, none was attempted.
