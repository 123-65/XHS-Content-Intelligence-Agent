# LangChain-Chatchat retrieval spike

This directory is a disposable compatibility fixture. It is not the production `KnowledgeService`, does not expose a project API, and is not connected to the Agent, workflow, frontend, or database.

Pinned baseline:

- Python 3.11
- `langchain-chatchat==0.3.1.3`
- embedding: `BAAI/bge-m3` through a user-approved domestic API
- vector store: FAISS
- retrieval: Chatchat's built-in BM25 + FAISS ensemble

Acceptance query:

```text
RAG-KB-TEST-92817 的验证短语是什么？
```

Required direct retrieval evidence:

- content includes `KnowledgeBoundaryAlpha`;
- metadata source identifies `test.md`;
- result includes a document/chunk ID;
- no generation LLM call occurs;
- runtime configuration uses exactly `BAAI/bge-m3` and does not silently fall back.

Current state: package resolution and CLI smoke test passed in a one-time Python 3.11 container. Real ingestion/retrieval is blocked because no embedding API endpoint or credential is configured. Do not place secrets in this directory.

