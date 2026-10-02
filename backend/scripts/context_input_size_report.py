from __future__ import annotations

import json
import math
import re
from collections import Counter
from pathlib import Path
from typing import Any


STAGE = "5.2_context_input_size_baseline"

DOMAIN_TERMS = [
    "大学生",
    "双非",
    "27届",
    "小白",
    "新手",
    "零基础",
    "Agent",
    "AI Agent",
    "编程",
    "项目",
    "实战",
    "简历",
    "面试",
    "上岸",
    "求职",
    "学习路线",
    "源码",
    "github",
    "课程",
    "普通本科",
    "转码",
    "应届生",
]

CONTEXT_KEYWORDS = [
    "context",
    "generation_context",
    "review_context",
    "ContextManager",
    "ContextSlot",
    "ContextSnapshot",
    "PromptRunLog",
    "prompt_key",
    "prompt_version",
    "system_prompt",
    "user_prompt",
    "strategy_memory",
    "account_snapshot",
    "experiment_snapshot",
    "opportunity_snapshot",
]

EXCLUDED_PARTS = {"__pycache__", ".pytest_cache", ".venv", "migrations"}

P0_ENTRIES = {
    "draft_generation": {
        "files": [
            "backend/app/services/draft_generation_sev.py",
            "backend/app/schemas/draft.py",
            "backend/app/context/context_builder.py",
            "backend/app/context/context_slots.py",
            "backend/app/context/context_budget.py",
            "backend/app/context/context_snapshot.py",
        ],
        "service_file": "backend/app/services/draft_generation_sev.py",
        "prompt_files": [],
        "schema_model": "DraftContent",
        "system_prompt_source": "backend/app/services/draft_generation_sev.py",
        "user_prompt_source": "backend/app/services/draft_generation_sev.py",
        "context_source": "DraftGenerationInput",
        "why_p0": "Canonical Draft Generation Owner，直接生成用户可见草稿",
        "needs_slot_split_5_3": True,
        "needs_token_budget_5_4": True,
    },
    "review_report": {
        "files": [
            "backend/app/services/draft_review_sev.py",
            "backend/app/schemas/draft.py",
        ],
        "service_file": "backend/app/services/draft_review_sev.py",
        "prompt_files": [],
        "schema_model": "DraftReviewLLMResult",
        "system_prompt_source": "backend/app/services/draft_review_sev.py",
        "user_prompt_source": "backend/app/services/draft_review_sev.py",
        "context_source": "DraftReviewInput",
        "why_p0": "审核报告直接调用 LLM structured，影响发布前风险和修改建议",
        "needs_slot_split_5_3": True,
        "needs_token_budget_5_4": True,
    },
}

P1_SOURCES = {
    "competitor_report": {
        "files": ["backend/app/services/competitor_report_sev.py"],
        "possible_outputs": [
            "persona_patterns",
            "content_pillars",
            "top_tags",
            "title_patterns",
            "cover_patterns",
            "content_structures",
            "comment_demands",
            "conversion_signals",
            "risk_points",
            "high_performance_notes",
            "content_insights",
            "suggestions",
            "viral_note_breakdowns",
            "content_opportunities",
        ],
        "affected_downstream": ["content_experiment", "content_experiment_v2", "content_draft", "content_draft_v2"],
        "why_p1": "当前不直接调用 LLM，但输出进入草稿上下文，并存在硬编码领域词",
    },
    "competitor_analysis": {
        "files": ["backend/app/services/competitor_analysis_sev.py"],
        "possible_outputs": ["top_tags", "title_patterns", "high_performance_notes", "content_insights", "suggestions", "summary"],
        "affected_downstream": ["content_experiment", "content_draft"],
        "why_p1": "旧竞品分析结果会进入实验和旧草稿 generation_context",
    },
    "content_strategy": {
        "files": ["backend/app/services/content_strategy_sev.py"],
        "possible_outputs": ["strategy_goal", "target_audience", "content_directions", "rationale", "evidence_refs", "opportunities"],
        "affected_downstream": ["future_content_creation"],
        "why_p1": "正式 Strategy Contract 将作为未来内容创作的上游输入",
    },
    "comment_insight": {
        "files": ["backend/app/services/competitor_report_sev.py"],
        "possible_outputs": ["comment_demands", "conversion_signals", "risk_points", "comment_examples"],
        "affected_downstream": ["competitor_report", "content_opportunity", "content_strategy", "content_draft_v2"],
        "why_p1": "当前主要嵌在 competitor_report 的评论需求识别中，会影响机会和草稿角度",
    },
    "strategy_memory": {
        "files": ["backend/app/services/startup_strategy_sev.py", "backend/app/agent/tools/local_registry.py"],
        "possible_outputs": ["memory_type", "summary", "pattern", "confidence", "usage_snapshot", "usage_reason"],
        "affected_downstream": ["content_draft_v2", "agent_runtime"],
        "why_p1": "策略记忆会进入 STRATEGY_MEMORY context slot 或 Agent tool output",
    },
    "context_engineering": {
        "files": [
            "backend/app/context/context_builder.py",
            "backend/app/context/context_slots.py",
            "backend/app/context/context_budget.py",
            "backend/app/context/context_snapshot.py",
            "backend/app/context/context_usage_logger.py",
            "backend/app/context/context_compressor.py",
            "backend/app/context/context_sanitizer.py",
        ],
        "possible_outputs": ["BuiltContext", "BuiltContextSlot", "ContextSnapshot", "ContextSlotLog", "truncation_summary", "sanitizer_summary"],
        "affected_downstream": ["content_draft_v2"],
        "why_p1": "承载 context slot、预算、快照和日志，影响第 5.3/5.4 设计",
    },
}


def project_root() -> Path:
    current = Path.cwd()
    if (current / "backend").exists():
        return current
    if current.name == "backend":
        return current.parent
    return current


def rel(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def read_text(root: Path, rel_path: str) -> str:
    path = root / rel_path
    return path.read_text(encoding="utf-8") if path.exists() else ""


def collect_python_files(root: Path) -> list[Path]:
    roots = [root / "backend" / "app", root / "backend" / "tests"]
    files: list[Path] = []
    for directory in roots:
        if not directory.exists():
            continue
        for path in directory.rglob("*.py"):
            if any(part in EXCLUDED_PARTS for part in path.parts):
                continue
            files.append(path)
    return sorted(files)


def rough_token_count(text: str) -> int:
    """粗略估算 token 数，不依赖第三方 tokenizer。"""
    if not text:
        return 0
    cjk_chars = len(re.findall(r"[\u4e00-\u9fff]", text))
    other_chars = len(text) - cjk_chars
    return math.ceil(cjk_chars / 1.5 + other_chars / 4)


def count_occurrences(text: str, terms: list[str]) -> dict[str, int]:
    return {term: len(re.findall(re.escape(term), text, flags=re.IGNORECASE)) for term in terms}


def found_terms(text: str) -> list[str]:
    counts = count_occurrences(text, DOMAIN_TERMS)
    return [term for term, count in counts.items() if count > 0]


def call_methods(text: str) -> list[str]:
    methods = []
    if re.search(r"\.generate_text\s*\(", text):
        methods.append("generate_text")
    if re.search(r"\.generate_structured_with_context\s*\(", text):
        methods.append("generate_structured_with_context")
    if re.search(r"\.generate_structured\s*\(", text):
        methods.append("generate_structured")
    return sorted(set(methods))


def extract_string_arg(text: str, name: str) -> list[str]:
    return sorted(set(re.findall(rf"{name}\s*=\s*[\"']([^\"']+)[\"']", text)))


def extract_schema_models(text: str) -> list[str]:
    return sorted(set(re.findall(r"schema_model\s*=\s*([A-Za-z_][A-Za-z0-9_]*)", text)))


def extract_prompt_constant(text: str, name: str) -> str | None:
    match = re.search(rf"{name}\s*=\s*[\"']([^\"']+)[\"']", text)
    return match.group(1) if match else None


def combined_text(root: Path, rel_paths: list[str]) -> str:
    return "\n".join(read_text(root, item) for item in rel_paths)


def p0_entry(root: Path, module: str, spec: dict[str, Any]) -> dict[str, Any]:
    files = spec["files"]
    service_text = read_text(root, spec["service_file"])
    prompt_text = combined_text(root, spec["prompt_files"])
    all_text = combined_text(root, files)
    prompt_keys = extract_string_arg(service_text, "prompt_key")
    prompt_versions = extract_string_arg(service_text, "prompt_version")
    prompt_name = extract_prompt_constant(prompt_text, "PROMPT_NAME")
    prompt_version = extract_prompt_constant(prompt_text, "PROMPT_VERSION")
    if not prompt_keys and prompt_name:
        prompt_keys = [prompt_name]
    if not prompt_versions and prompt_version:
        prompt_versions = [prompt_version]
    schema_models = extract_schema_models(service_text) or [spec["schema_model"]]
    hardcoded_terms = found_terms(all_text)
    prompt_terms = found_terms(prompt_text)
    service_terms = found_terms(service_text)
    methods = call_methods(service_text)
    uses_context_manager = "ContextManager" in service_text or "generate_structured_with_context" in service_text
    records_prompt_run_log = "create_prompt_run_log" in service_text or "PromptRunLog" in service_text
    records_context_snapshot = "ContextUsageLogger" in service_text or "record_snapshot" in service_text or "ContextSnapshot" in all_text
    return {
        "module": module,
        "files": files,
        "direct_llm_call": "LLMClient" in service_text and bool(methods),
        "call_methods": methods,
        "schema_model": schema_models[0] if len(schema_models) == 1 else schema_models,
        "prompt_key": prompt_keys[0] if len(prompt_keys) == 1 else (prompt_keys or None),
        "prompt_version": prompt_versions[0] if len(prompt_versions) == 1 else (prompt_versions or None),
        "system_prompt_source": spec["system_prompt_source"],
        "user_prompt_source": spec["user_prompt_source"],
        "context_source": spec["context_source"],
        "uses_context_manager": uses_context_manager,
        "records_prompt_run_log": records_prompt_run_log,
        "records_context_snapshot": records_context_snapshot,
        "can_count_slots": uses_context_manager and "ContextSlot" in service_text,
        "template_chars": len(prompt_text),
        "template_rough_tokens": rough_token_count(prompt_text),
        "service_chars": len(service_text),
        "service_rough_tokens": rough_token_count(service_text),
        "context_keyword_counts": count_occurrences(all_text, CONTEXT_KEYWORDS),
        "hardcoded_domain_terms_found": hardcoded_terms,
        "prompt_template_terms_found": prompt_terms,
        "service_terms_found": service_terms,
        "hardcoded_domain_terms_may_enter_llm_input": bool(prompt_terms or service_terms),
        "needs_slot_split_5_3": spec["needs_slot_split_5_3"],
        "needs_token_budget_5_4": spec["needs_token_budget_5_4"],
        "priority": "P0",
        "why_p0": spec["why_p0"],
    }


def p1_source(root: Path, module: str, spec: dict[str, Any]) -> dict[str, Any]:
    text = combined_text(root, spec["files"])
    terms = found_terms(text)
    return {
        "module": module,
        "files": spec["files"],
        "direct_llm_call": any(method in text for method in ["generate_text", "generate_structured", "generate_structured_with_context"]),
        "constructs_structured_outputs": True,
        "possible_outputs": spec["possible_outputs"],
        "output_enters_downstream_context": True,
        "hardcoded_domain_terms_found": terms,
        "hardcoded_domain_terms_affect_outputs": affected_outputs_for(module),
        "affected_downstream": spec["affected_downstream"],
        "needs_domain_profile_5_3": bool(terms) or module in {"competitor_report", "competitor_analysis", "content_experiment_v2"},
        "needs_runtime_sample_stats_5_2": module in {"competitor_report", "competitor_analysis", "content_experiment", "content_experiment_v2"},
        "file_chars": len(text),
        "rough_tokens": rough_token_count(text),
        "context_keyword_counts": count_occurrences(text, CONTEXT_KEYWORDS),
        "priority": "P1",
        "why_p1": spec["why_p1"],
    }


def affected_outputs_for(module: str) -> list[str]:
    return {
        "competitor_report": ["title_patterns", "content_pillars", "comment_demands", "persona_patterns", "opportunities", "suggestions"],
        "competitor_analysis": ["title_patterns", "content_insights", "suggestions"],
        "content_experiment": ["selected_topic", "topic_angle", "hypothesis"],
        "content_experiment_v2": ["content_format", "main_variable", "control_variables", "topic_angle"],
        "comment_insight": ["comment_demands", "conversion_signals", "risk_points"],
        "strategy_memory": ["summary", "pattern"],
        "context_engineering": ["slot_names", "truncation_summary", "memory_usage_summary"],
    }.get(module, [])


def term_summary(root: Path, files: list[Path]) -> dict[str, Any]:
    production_counter: Counter[str] = Counter()
    prompt_counter: Counter[str] = Counter()
    test_demo_counter: Counter[str] = Counter()
    production_locations: dict[str, list[str]] = {term: [] for term in DOMAIN_TERMS}
    prompt_locations: dict[str, list[str]] = {term: [] for term in DOMAIN_TERMS}
    test_demo_locations: dict[str, list[str]] = {term: [] for term in DOMAIN_TERMS}

    for path in files:
        relative = rel(path, root)
        text = path.read_text(encoding="utf-8")
        counts = count_occurrences(text, DOMAIN_TERMS)
        is_prompt = relative.startswith("backend/app/prompts/")
        is_test_demo = (
            relative.startswith("backend/tests/")
            or relative.endswith("backend/app/crawler/providers/seed_sample.py")
            or relative.endswith("backend/app/crawler/mock_provider.py")
            or relative.endswith("backend/app/llm/mock_client.py")
            or "mock_provider.py" in relative
        )
        for term, count in counts.items():
            if count <= 0:
                continue
            if is_test_demo:
                test_demo_counter[term] += count
                test_demo_locations[term].append(relative)
            elif is_prompt:
                prompt_counter[term] += count
                prompt_locations[term].append(relative)
            else:
                production_counter[term] += count
                production_locations[term].append(relative)

    return {
        "production_code_terms": compact_terms(production_counter, production_locations),
        "prompt_template_terms": compact_terms(prompt_counter, prompt_locations),
        "test_or_demo_terms": compact_terms(test_demo_counter, test_demo_locations),
        "note": "测试/demo 可以保留但必须标记；生产 prompt/service 中的领域词后续进入第 5.3 domain_profile 设计；第 5.2 只记录是否影响 context。",
    }


def compact_terms(counter: Counter[str], locations: dict[str, list[str]]) -> dict[str, Any]:
    return {
        term: {"count": counter[term], "files": sorted(set(locations[term]))}
        for term in DOMAIN_TERMS
        if counter[term] > 0
    }


def prompt_size_baseline(entries: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        entry["module"]: {
            "template_chars": entry["template_chars"],
            "template_rough_tokens": entry["template_rough_tokens"],
            "service_chars": entry["service_chars"],
            "service_rough_tokens": entry["service_rough_tokens"],
        }
        for entry in entries
    }


def context_slot_readiness(entries: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        entry["module"]: {
            "uses_context_manager": entry["uses_context_manager"],
            "records_prompt_run_log": entry["records_prompt_run_log"],
            "records_context_snapshot": entry["records_context_snapshot"],
            "can_count_slots": entry["can_count_slots"],
            "readiness": "READY" if entry["can_count_slots"] else "NEEDS_SLOT_DESIGN",
        }
        for entry in entries
    }


def build_report(root: Path, result: dict[str, Any]) -> str:
    p0_rows = "\n".join(p0_markdown_row(entry) for entry in result["p0_llm_context_entries"])
    p1_rows = "\n".join(p1_markdown_row(entry) for entry in result["p1_upstream_context_sources"])
    hardcoded = result["hardcoded_domain_terms_summary"]
    production_terms = ", ".join(hardcoded["production_code_terms"].keys()) or "-"
    prompt_terms = ", ".join(hardcoded["prompt_template_terms"].keys()) or "-"
    test_terms = ", ".join(hardcoded["test_or_demo_terms"].keys()) or "-"
    return f"""# 第 5.2 Context 输入规模统计报告

## 1. 统计目的

本报告用于统计草稿生成、审核报告等真实 LLM 入口的 prompt/context 输入规模，并登记竞品分析、内容实验、策略记忆等上游结构化字段对下游 LLM context 的影响。

本阶段只统计，不优化，不改业务代码。

## 2. 统计范围

### P0：直接 LLM 业务入口

- content_draft_v2
- content_draft
- review_report

### P1：上游 context 来源

- competitor_report
- competitor_analysis
- content_experiment
- content_experiment_v2
- comment_insight
- strategy_memory
- context_engineering

### P2：只登记

- crawler_collection
- keyword_seed
- confirmation
- post_publish
- API route
- repository
- provider_health
- llm_infra

本次静态扫描 Python 文件数：{result["scanned_files_count"]}。

## 3. P0 LLM 入口统计表

| 模块 | 是否直接调用 LLM | 调用方式 | schema_model | prompt_key/version | system_prompt 来源 | context 来源 | 是否 ContextManager | 是否 PromptRunLog | 是否 ContextSnapshot | 模板字符数 | 模板粗略 token | 硬编码领域词 | 5.3 建议 |
|---|---|---|---|---|---|---|---|---|---|---:|---:|---|---|
{p0_rows}

## 4. P1 上游 context 来源统计表

| 模块 | 是否直接调用 LLM | 可能输出字段 | 是否进入下游 LLM context | 影响下游 | 硬编码领域词 | 风险 | 5.3 建议 |
|---|---|---|---|---|---|---|---|
{p1_rows}

## 5. 硬编码领域词进入 context 的风险

- `keyword_seed` 会影响采集源头；如果关键词围绕学习路线、项目、简历、求职生成，后续采集和竞品样本会偏向当前账号赛道。
- `competitor_report` / `competitor_analysis` 会影响标题模式、内容支柱、评论需求、机会生成；这些字段会进入内容实验和草稿上下文。
- `content_experiment` / `content_experiment_v2` 会影响选题、实验变量、成功标准和草稿的 workflow state。
- prompt 模板会直接影响 LLM 输出风格；旧 writer prompt 中的学生/自学者表达应在第 5.3 进入账号画像和领域画像设计。
- mock / seed / tests 中的领域词可保留，但必须标记为 demo/test，不进入生产默认链路。

生产代码命中的领域词：{production_terms}

Prompt 模板命中的领域词：{prompt_terms}

测试/demo 命中的领域词：{test_terms}

## 6. 当前不能写的指标

当前不能写：

- token 降低 xx%
- 延迟降低 xx%
- 成本下降 xx%
- 输出质量提升 xx%

原因：本阶段只统计优化前基线，还没有做 Context Slot、Token Budget 和压缩。

## 7. 后续第 5.3 建议

- 设计 `DOMAIN_PROFILE` slot。
- 区分 `ACCOUNT_PROFILE` 和 `DOMAIN_PROFILE`。
- 把硬编码领域词从生产 prompt / service 中逐步迁移到 `domain_profile`。
- `domain_profile` 需要版本号和人工确认状态。
- `content_draft_v2` 优先接入 slot 统计，因为它已经使用 ContextManager、PromptRunLog 和 ContextSnapshot。
- `competitor_report` 暂时不重构，但要登记哪些输出字段来自硬编码规则。

## 8. 后续第 5.4 建议

- 先给 `content_draft_v2` 设置 token budget。
- 对 competitor evidence 做 Top-K。
- 对 comment insight 做摘要。
- 对 strategy memory 做最近有效策略筛选。
- 对 prompt 中重复的账号定位进行去重。

## 9. 结论

1. 第 5.2 第一版统计对象是 `content_draft_v2`、`content_draft`、`review_report`。
2. `competitor_report` / `competitor_analysis` 当前不直接调用 LLM，但会影响下游 context，必须 P1 登记。
3. 硬编码领域词问题暂不修改，放到第 5.3 `domain_profile` / context slot 设计。
4. 本阶段不产生优化后指标，只产生优化前基线。
"""


def p0_markdown_row(entry: dict[str, Any]) -> str:
    prompt_key = entry["prompt_key"] or "-"
    prompt_version = entry["prompt_version"] or "-"
    return "| " + " | ".join(
        [
            md(entry["module"]),
            "是" if entry["direct_llm_call"] else "否",
            md(entry["call_methods"]),
            md(entry["schema_model"]),
            md(f"{prompt_key} / {prompt_version}"),
            md(entry["system_prompt_source"]),
            md(entry["context_source"]),
            "是" if entry["uses_context_manager"] else "否",
            "是" if entry["records_prompt_run_log"] else "否",
            "是" if entry["records_context_snapshot"] else "否",
            str(entry["template_chars"]),
            str(entry["template_rough_tokens"]),
            md(entry["hardcoded_domain_terms_found"]),
            md("拆分 ACCOUNT_PROFILE / DOMAIN_PROFILE / WORKFLOW_STATE / OUTPUT_SCHEMA / STRATEGY_MEMORY"),
        ]
    ) + " |"


def p1_markdown_row(entry: dict[str, Any]) -> str:
    return "| " + " | ".join(
        [
            md(entry["module"]),
            "是" if entry["direct_llm_call"] else "否",
            md(entry["possible_outputs"]),
            "是" if entry["output_enters_downstream_context"] else "否",
            md(entry["affected_downstream"]),
            md(entry["hardcoded_domain_terms_found"]),
            md(risk_for(entry)),
            md("第 5.3 设计 domain_profile / 字段来源标记" if entry["needs_domain_profile_5_3"] else "登记字段来源和下游位置"),
        ]
    ) + " |"


def risk_for(entry: dict[str, Any]) -> str:
    if entry["module"] in {"competitor_report", "competitor_analysis", "comment_insight"}:
        return "硬编码领域词会影响下游标题、机会和草稿角度"
    if entry["module"].startswith("content_experiment"):
        return "实验选题和变量会进入草稿 context"
    if entry["module"] == "strategy_memory":
        return "历史策略会被注入后续 context，需要置信和版本"
    return "基础设施影响可观测性和 slot 统计"


def md(value: Any) -> str:
    if value is None:
        return "-"
    if isinstance(value, list):
        text = ", ".join(str(item) for item in value) if value else "-"
    else:
        text = str(value)
    return text.replace("|", "\\|").replace("\n", " ")


def run_scan(root: Path) -> dict[str, Any]:
    files = collect_python_files(root)
    p0_entries = [p0_entry(root, module, spec) for module, spec in P0_ENTRIES.items()]
    p1_sources = [p1_source(root, module, spec) for module, spec in P1_SOURCES.items()]
    hardcoded_summary = term_summary(root, files)
    result = {
        "stage": STAGE,
        "scanned_files_count": len(files),
        "p0_llm_context_entries": p0_entries,
        "p1_upstream_context_sources": p1_sources,
        "hardcoded_domain_terms_summary": hardcoded_summary,
        "context_slot_readiness": context_slot_readiness(p0_entries),
        "prompt_size_baseline": prompt_size_baseline(p0_entries),
        "rough_token_baseline": {
            entry["module"]: {
                "template_rough_tokens": entry["template_rough_tokens"],
                "service_rough_tokens": entry["service_rough_tokens"],
            }
            for entry in p0_entries
        },
        "context_risk_findings": [
            "content_draft_v2 已使用 ContextManager / PromptRunLog / ContextSnapshot，可作为第 5.3 slot 设计起点。",
            "content_draft 与 review_report 仍是普通 context dict，无法直接做 slot 级统计。",
            "competitor_report / competitor_analysis 不直接调用 LLM，但输出会进入下游 context，且存在硬编码领域词。",
            "测试/demo/seed/mock 中的领域词可以保留，但必须持续与生产默认链路隔离。",
        ],
        "recommendations_for_5_3": [
            "设计 DOMAIN_PROFILE slot，并与 ACCOUNT_PROFILE 分离。",
            "为 competitor_report 输出字段标记是否来自硬编码规则。",
            "content_draft_v2 优先接入 slot 统计并记录每个 slot 的 token。",
            "domain_profile 需要版本号、生成来源和人工确认状态。",
        ],
        "recommendations_for_5_4": [
            "先给 content_draft_v2 设置 token budget。",
            "对竞品证据做 Top-K。",
            "对 comment insight 做摘要。",
            "对 strategy memory 做最近有效策略筛选。",
            "对 prompt 中重复账号定位做去重。",
        ],
    }
    return result


def main() -> int:
    root = project_root()
    result = run_scan(root)
    report_path = root / "docs" / "context_input_size_baseline.md"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(build_report(root, result), encoding="utf-8")
    result["report_path"] = rel(report_path, root)
    print(json.dumps(result, ensure_ascii=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
