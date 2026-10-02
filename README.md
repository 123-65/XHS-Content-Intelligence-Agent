# XHS Content Intelligence Agent

> 面向知识型小红书账号的内容情报、决策与创作 Agent。

XHS Content Intelligence Agent 不是一个单纯的 AI 写作工具。它把用户的个人知识、真实市场情报与账号发布反馈组织成可追踪的内容决策上下文，由 Agent 推动 **Research → Opportunity → Strategy → Draft → Review** 的长期闭环。系统强调真实来源、明确归属、版本谱系和可恢复执行，让每一次选题、创作与复盘都能找到依据。

## 🚀 快速开始

### 1. 克隆

```bash
git clone https://github.com/123-65/XHS-Content-Intelligence-Agent.git
cd XHS-Content-Intelligence-Agent
```

### 2. 准备环境变量

PowerShell：

```powershell
Copy-Item backend/.env.example .env
```

Bash：

```bash
cp backend/.env.example .env
```

编辑根目录 `.env`，至少配置真实的 `LLM_PROVIDER`、`LLM_API_KEY`、`LLM_BASE_URL` 和 `LLM_MODEL`。不要提交 `.env`、Cookie 或任何密钥。小红书真实只读采集还需要可用的 XHS MCP 服务；未配置时相关 Research 能力会明确不可用或失败，不应视为真实数据验证。

### 3. 启动

需要 Docker Desktop 与 Docker Compose：

```bash
docker compose up --build
```

启动后：

- Web：<http://localhost:5173>
- Backend API：<http://localhost:8000>
- Health：<http://localhost:8000/health>
- OpenAPI：<http://localhost:8000/docs>

PostgreSQL 数据保存在 Docker volume 中。普通重启不需要删除 volume。

### 4. 验证

```bash
curl http://localhost:8000/health
```

前端测试与构建：

```bash
cd frontend
npm install
npm test
npm run build
```

Backend 测试建议在独立虚拟环境中执行：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend/requirements.txt
$env:PYTHONPATH = "backend"
.\.venv\Scripts\python.exe -m pytest backend/tests -q
```

## 核心闭环

```text
个人知识 ─────┐
市场 Profile ─┼─> Research -> Opportunity -> Strategy -> Draft -> Review
公开 Note ────┤                                      │          │
账号反馈 ─────┘                                      └──────────┘
```

- **Research**：基于用户授权的 Profile、Note 和账号上下文收集真实证据。
- **Opportunity**：从证据中形成可追踪的内容机会，而不是直接生成文章。
- **Strategy**：结合账号定位与研究结果制定内容策略。
- **Draft**：围绕明确 Opportunity/Strategy 创建草稿并保留版本谱系。
- **Review**：基于精确发布版本和可用指标复盘，产出后续策略候选。

## 关键能力

- Pydantic AI Conversational Agent 作为统一自然语言入口。
- ExecutionGate 区分普通对话与业务行动。
- Canonical Turn Context 汇总当前材料、Workspace、Pending 与近期业务对象。
- 基于服务器已验证事实的 Tool Eligibility，再由 LLM 在合法候选中做语义选择。
- 五条独立 Workflow：Research、Strategy、Creation、Refinement、Post-publish Review。
- Durable Run、跨请求 Resume、操作账本、幂等与 execution lease。
- Research / Strategy / Draft / Publication / Review 的 Account-scoped 产品读取。
- Draft append-only version lineage 与 PublishedNote 精确版本绑定。
- 真实 XHS MCP 只读采集边界与来源标记。

## 系统架构

```text
Vue 3 / TypeScript
        |
        v
FastAPI Product API
        |
        v
Pydantic AI Conversational Agent
  | ExecutionGate
  | CanonicalTurnContext
  | Tool Eligibility + Semantic Selection
  v
Durable Workflow Runtime
  |-- Research
  |-- Content Strategy
  |-- Content Creation
  |-- Content Refinement
  `-- Post-publish Review
        |
        +--> PostgreSQL / Artifact Lineage / Operation Ledger
        +--> Qwen-compatible LLM Provider
        `--> XHS MCP Read-only Evidence

Independent baseline:
backend/insight_rag -> Parse / Chunk / Embed / Retrieve
```

确定性层负责 ownership、存在性、前置条件、lineage、幂等和持久化；LLM 负责语言理解、指代消解以及合法工具集合中的语义选择。系统不通过不断追加关键词 `if/else` 充当 Intent Router。

## InsightRAG Knowledge Retrieval Engine

作者自己的 InsightRAG-Studio 已作为独立 baseline 迁入 [`backend/insight_rag`](backend/insight_rag)。它目前负责文档解析、分块、Embedding、Milvus 向量检索、BM25/RRF 融合和来源元数据，尚未接入 Agent 或正式业务 API。

- 上游版本：[UPSTREAM.md](backend/insight_rag/UPSTREAM.md)
- Baseline 与问题：[INSIGHT_RAG_BASELINE.md](docs/architecture/INSIGHT_RAG_BASELINE.md)
- 迁入测试：`56 passed`

该模块将按 Baseline Eval → Chunk Optimization → Hybrid Retrieval → Rerank → Retrieval Evaluation → Agent Integration 的顺序优化。

## 技术栈

| Layer | Technology |
| --- | --- |
| Frontend | Vue 3, TypeScript, Vite, Pinia, Element Plus, ECharts |
| Backend | Python, FastAPI, Pydantic, SQLAlchemy, Alembic |
| Agent | Pydantic AI, structured output, function calling |
| Runtime | Durable workflow runs, checkpoints, operation ledger |
| Data | PostgreSQL 16 |
| LLM | OpenAI-compatible provider interface, current Qwen configuration |
| XHS evidence | External read-only XHS MCP provider |
| RAG baseline | InsightRAG, Milvus, BM25/RRF, OpenAI-compatible embeddings |
| Delivery | Docker Compose |

## 项目结构

```text
.
├── backend/
│   ├── app/                 # 主 FastAPI、Agent、Workflow 与业务模型
│   ├── insight_rag/         # 独立 Knowledge Retrieval Engine baseline
│   ├── alembic/             # 数据库迁移
│   ├── tests/               # 主系统测试
│   └── evals/               # Agent/evaluation assets
├── frontend/                # Vue 产品界面
├── docs/                    # 架构、测试与验收证据
├── tools/                   # 本地集成工具（运行状态不入库）
└── docker-compose.yml
```

## 数据与安全边界

- 只采集和处理用户明确授权的数据。
- External XHS Profile/Note 与内部 PublishedNote 使用不同对象类型，不能混淆。
- API Key、Cookie、`.env`、上传文件、数据库和向量索引均不得提交。
- Mock、fallback 与真实 provider 结果必须明确区分。
- PublishedNote Review 必须绑定精确 DraftVersion，不能默认使用最新草稿。
- RAG baseline 当前不等于正式 Agent 能力；完成独立评测前不会暴露 `retrieve_knowledge` Tool。

## 开发验证

主系统：

```powershell
$env:PYTHONPATH = "backend"
.\.venv\Scripts\python.exe -m pytest backend/tests -q
```

InsightRAG baseline：

```powershell
$env:PYTHONPATH = "backend"
.\.venv\Scripts\python.exe -m pytest backend/insight_rag/tests -q
```

Frontend：

```bash
cd frontend
npm test
npm run build
```

真实 E2E 必须额外确认 `is_mock=false`、provider/model 日志、来源对象、持久化 artifact 与版本 lineage。单元测试通过不能替代真实 provider 验收。

## Roadmap

- 建立 InsightRAG 中文检索基线数据集与 Recall@K/MRR/nDCG。
- 优化结构化 Chunk、中文 BM25、Hybrid fusion、阈值与 reranker。
- 冻结统一的 `KnowledgeSearchHit` 与 source traceability contract。
- 在独立 RAG baseline 稳定后，再设计窄边界 Agent knowledge provider/tool。
- 持续完善真实浏览器 E2E、可观测性与恢复演练。

## Repository

<https://github.com/123-65/XHS-Content-Intelligence-Agent>
