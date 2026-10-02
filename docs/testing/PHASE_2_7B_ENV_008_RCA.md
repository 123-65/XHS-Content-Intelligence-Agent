# ENV-008 Competitor Analysis Timeout RCA

## 1. Failure Call Chain

The real `RESEARCH_V1` path is:

`ResearchWorkflow._run` (`backend/app/agent/workflows/research.py`)
→ `ToolName.ANALYZE_RESEARCH`
→ `AnalyzeResearchTool.execute` (`backend/app/agent/tools/semantic_tools.py`)
→ `LLMStructuredCompetitorAnalyzer.analyze` (`backend/app/analysis/competitor/llm_analyzer.py`)
→ `LLMClient.generate_structured`
→ `QwenProvider` / `OpenAICompatibleProvider.generate_structured`
→ OpenAI-compatible `chat.completions.create`.

There is no Domain Service between the Tool and analyzer on this path. `CompetitorReportService` is not called by `RESEARCH_V1`, and the old Rule baseline is not involved. Prompt key=`competitor_semantic_analysis`, prompt version=`v1`, structured schema=`CompetitorSemanticResult`.

## 2. Actual Provider / Model

OBS 2130/2131 and runtime construction agree: provider=`qwen`, model=`qwen3.8-2.4t-a95b`, `is_mock=false`. `LLMStructuredCompetitorAnalyzer` passes no model override, so the provider default model is used. It also passes no `extra_body`; therefore `enable_thinking` is not explicitly set by this call. This differs from the frozen Control Semantic route, which explicitly uses its flash override and `enable_thinking=false`.

## 3. Retry Ownership

The OpenAI SDK client is constructed with `max_retries=0`. Structured retries are owned by `OpenAICompatibleProvider` through Tenacity, with configured logical attempt total=2. OBS 2130 is attempt 1/2 and OBS 2131 is attempt 2/2; the second has `retry_exhausted=true`. `ResearchWorkflow._call(..., retry=False)` adds no Workflow retry. No nested retry exists.

Attempt latency was 30,872 ms and 30,767 ms. Provider-attempt time totals 61,639 ms; including the configured inter-attempt wait, the analysis wall time is approximately 62.6 seconds.

## 4. Timeout Source

The 30-second value comes from `settings.llm_timeout_seconds`, populated by `LLM_TIMEOUT_SECONDS`, and is passed directly to the OpenAI SDK client constructor. Runtime inspection reports SDK/httpx timeout=`30`. There is no per-call override, `asyncio` timeout, or Workflow-step deadline on the analysis call. The observed exception is therefore the provider HTTP request deadline, not an outer Workflow timeout.

## 5. Analysis Workload Size

Safe metadata from the durable state and local schema:

- Note evidence: 3; unique Note IDs: 3.
- Account context: 1; unique Account IDs: 1.
- Comments: 0; OCR items: 0.
- Evidence JSON: approximately 4,052 characters / 7,830 UTF-8 bytes.
- `CompetitorSemanticResult` schema: approximately 10,609 characters.
- System prompt: 340 characters.
- Approximate complete structured request text: about 15K characters plus small fixed wrapper text.
- Top-level output sections: 10 (`persona`, `content_pillars`, `audience_demands`, `high_performing_patterns`, `content_style`, `follow_recommendation`, `content_opportunities`, `conversion_signals`, `risk_points`, `data_gaps`); 7 are required at the top level.
- No duplicated Note or Account evidence was found.
- OBS token usage is zero because both requests timed out before a response; no synthetic token call was made.

This is materially heavier than Control Semantic in schema and expected output breadth, but the evidence payload itself is bounded and not abnormally duplicated.

## 6. Historical Latency Comparison

- Default strong-model Control Semantic diagnostic: `qwen3.8-2.4t-a95b`, same OpenAI-compatible structured path, approximately 92,482 ms, success only under the isolated 120-second diagnostic boundary.
- Control Semantic flash route: `qwen3.8-flash`, approximately 8,124 ms, success. This route is frozen and unrelated to the analysis fix decision.
- Current Competitor Analysis: default `qwen3.8-2.4t-a95b`, 30,872 ms and 30,767 ms, both request-deadline failures.
- Historical E2E-001 Research: the same three Note IDs and one Account evidence completed analysis and artifact creation, but only total server-chain latency (~486,022 ms) is recoverable. No isolated Competitor Analysis OBS/model latency exists for that historical call, so it cannot be used as an exact analysis latency baseline.

No historical request was replayed.

## 7. Business Latency Requirement

Research Analysis is a high-quality, heavy workflow step and does not share Control Semantic's immediate interactive latency requirement. Tens of seconds may be acceptable, but the product still needs an explicit bounded analysis latency budget. The current universal 30-second provider deadline is not evidence of that business budget; it is a shared client setting. The correct budget must be decided before choosing a model or timeout change.

## 8. Controlled Diagnostic

Not executed. Existing evidence distinguishes normal strong-model latency from a new nested-retry or Workflow-timeout defect sufficiently: the same strong model previously required ~92.5 seconds for a structured workload, both current failures align tightly with the 30-second request deadline, SDK retries remain zero, and no provider HTTP error was returned. A new provider call would add cost without changing the primary classification.

## 9. RCA Classification

Primary: **A. DEFAULT MODEL LATENCY INCOMPATIBLE WITH 30S TIMEOUT**.

Secondary factor: **C. STRUCTURED OUTPUT COMPLEXITY**, with a bounded evidence payload and a ~10.6K-character schema containing ten top-level analytical sections. B is not primary because the evidence payload is only ~4K characters and contains no duplicates. D and F are rejected because retry ownership and Workflow boundaries are functioning as configured. E cannot be proven from these observations and is not needed to explain the exact deadline-aligned failures.

## 10. Minimal Resolution Options

For a separately authorized implementation turn, evaluate in this order:

1. Define the Research Analysis business latency budget.
2. Add a task-specific analysis timeout if the strong model remains required.
3. Consider per-task model routing only after quality/latency evaluation; do not change frozen Control Semantic routing.
4. Profile schema/prompt size and remove only demonstrably redundant representation, without dropping evidence or output contract fields.
5. Keep SDK retry=0 and one observable Adapter retry owner; adjust retry policy only with provider failure-rate evidence.

No option was implemented in this RCA turn.

## 11. Product Defect Registration

No new product defect is registered. The code follows the configured request deadline and retry ownership. `ENV-008 = DEFAULT STRONG MODEL LATENCY INCOMPATIBLE WITH SHARED 30S REQUEST TIMEOUT / RCA COMPLETE / OPEN`.

## 12. E2E-005 Continuation

No. `E2E-005 = BLOCKED BY ENV-008`. No E2E request was executed.

## 13. Pending Failure Observation

Turn 151 consumed and cleared Pending before downstream analysis failed. This remains an observation only. Pending lifecycle was not changed and no defect was registered for it.

## 14. Interview Asset

Updated one existing timeout/model-routing Q&A; added no duplicate Q&A.

## 15. Git

Only RCA documentation was added/updated. No product code, model, timeout, Prompt, Workflow, Provider, route, migration, or database data was changed. No Full Regression was run. No commit was created.
