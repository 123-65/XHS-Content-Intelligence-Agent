# insight_rag

`insight_rag` 是从作者自己的 [InsightRAG-Studio](https://github.com/123-65/InsightRAG-Studio) 迁入的独立知识检索模块。它作为后续优化基线存在，目前没有接入主 Conversational Agent 或业务 Workflow。

当前职责：文档解析、分块、Embedding、Milvus 向量索引、BM25 + Dense 融合检索与来源元数据。上游遗留的 Chat/API 代码为基线快照，不代表该模块在主项目中的产品职责；顶层对话与工作流仍由主项目 Pydantic AI Agent 负责。

## Baseline verification

从项目根目录执行：

```powershell
$env:PYTHONPATH = "backend"
.\.venv\Scripts\python.exe -m pytest backend/insight_rag/tests -q
```

迁入时结果：`56 passed`。

测试使用 SQLite、fake vector store 与 mock acceptance pipeline，不证明真实 PostgreSQL、Milvus、对象存储或远程模型已经部署。

## Dependency boundary

`requirements.upstream.txt` 只记录上游依赖基线。不要直接覆盖主 backend 依赖；其中的 OpenAI、FastAPI、LangChain、Milvus 与存储依赖需要在正式部署设计阶段重新做兼容性审计。

来源版本见 [UPSTREAM.md](./UPSTREAM.md)，详细能力与问题见 [INSIGHT_RAG_BASELINE.md](../../docs/architecture/INSIGHT_RAG_BASELINE.md)。
