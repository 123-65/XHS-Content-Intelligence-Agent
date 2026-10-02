from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from pathlib import Path


SCAN_DIRS = [
    "app/services",
    "app/agent",
    "app/context",
    "app/llm",
    "app/api",
    "app/repositories",
]

KEYWORD_GROUPS = {
    "llm": ["LLMClient", "generate_text", "generate_structured", "LLMResult", "LLMStructuredResult"],
    "prompt": ["prompt", "system_prompt", "user_prompt", "prompt_key", "prompt_version", "PromptRunLog"],
    "context": [
        "context",
        "generation_context",
        "review_context",
        "ContextSnapshot",
        "context_builder",
        "context_slots",
        "context_budget",
    ],
    "workflow": [
        "ExecutionOrchestrator",
        "workflow",
        "workflow_name",
        "step_name",
        "step_order",
        "ActionHandlerRegistry",
        "PlanExecutionResult",
        "tool_name",
        "register",
        "execute",
    ],
    "business": [
        "competitor",
        "competitor_account",
        "competitor_note",
        "comment",
        "comment_insight",
        "opportunity",
        "experiment",
        "draft",
        "review",
        "post_publish",
        "strategy",
        "memory",
        "analytics",
    ],
}

EXPECTED_MODULES = [
    "keyword_seed",
    "crawler_collection",
    "competitor_report",
    "competitor_analysis",
    "competitor_account",
    "competitor_note",
    "comment_insight",
    "content_opportunity",
    "content_experiment",
    "content_experiment_v2",
    "content_draft",
    "content_draft_v2",
    "review_report",
    "confirmation",
    "post_publish",
    "strategy_memory",
    "agent_runtime",
    "context_engineering",
    "llm_infra",
]

FUTURE_AGENT_CANDIDATES = [
    {
        "candidate_agent": "Research / Collection Agent",
        "current_code": "app/services/crawler_collection_sev.py, app/crawler/*",
        "current_shape": "普通 service / provider 调度",
        "why": "需要根据数据来源、权限和质量决定采集策略，输出会进入竞品分析和内容机会链路。",
        "input": "账号、关键词、采集目标、provider 状态",
        "output": "竞品账号、笔记、评论、采集状态",
        "needs_llm": "未来可能需要",
        "priority": "P1",
    },
    {
        "candidate_agent": "Competitor Analysis Agent",
        "current_code": "app/services/competitor_report_sev.py, app/services/competitor_analysis_sev.py",
        "current_shape": "规则分析 service",
        "why": "消费竞品账号、笔记、评论，输出会影响机会生成和草稿上下文。",
        "input": "竞品账号、竞品笔记、评论样本",
        "output": "报告、标签、标题模式、内容洞察",
        "needs_llm": "适合引入",
        "priority": "P1",
    },
    {
        "candidate_agent": "Viral Note Analysis Agent",
        "current_code": "app/services/competitor_report_sev.py",
        "current_shape": "报告 service 的一部分",
        "why": "爆款拆解有明确输入输出，适合独立评测结构化结果。",
        "input": "高互动竞品笔记",
        "output": "标题模式、内容结构、爆点、可复用套路",
        "needs_llm": "适合引入",
        "priority": "P1",
    },
    {
        "candidate_agent": "Comment Insight Agent",
        "current_code": "app/services/competitor_report_sev.py",
        "current_shape": "报告 service 的一部分，未发现独立成熟实现",
        "why": "评论需求识别会影响内容机会和草稿角度。",
        "input": "评论样本",
        "output": "痛点、疑问、购买/收藏动机",
        "needs_llm": "适合引入",
        "priority": "P1",
    },
    {
        "candidate_agent": "Content Strategy Service",
        "current_code": "app/services/content_strategy_sev.py, app/services/opportunity_assembler.py",
        "current_shape": "唯一 Canonical Service + 结构组装器",
        "why": "基于账号上下文和 Research Evidence 生成策略与可创作的内容机会。",
        "input": "账号上下文、Research Artifact、已验证 Content Opportunity",
        "output": "Content Strategy、EvidenceRefs、Content Opportunity",
        "needs_llm": "是，统一经由 LLMClient",
        "priority": "P1",
    },
    {
        "candidate_agent": "Writer Agent",
        "current_code": "app/services/draft_generation_sev.py",
        "current_shape": "Canonical DraftGenerationService",
        "why": "直接生成用户可见内容，已有 schema、prompt、context 和失败不入库测试。",
        "input": "账号、实验、机会、用户要求、策略记忆",
        "output": "结构化草稿",
        "needs_llm": "是",
        "priority": "P0",
    },
    {
        "candidate_agent": "Reviewer Agent",
        "current_code": "app/services/review_report_sev.py",
        "current_shape": "直接 LLM caller",
        "why": "决定风险、分数和修改建议，直接影响发布前确认。",
        "input": "草稿、账号、实验",
        "output": "审核报告",
        "needs_llm": "是",
        "priority": "P0",
    },
    {
        "candidate_agent": "Post-publish Analytics Agent",
        "current_code": "app/services/post_publish_review_v0_sev.py",
        "current_shape": "Canonical service / 发布后复盘",
        "why": "复盘结合已绑定笔记与指标快照，生成仍需人工确认的策略候选。",
        "input": "发布后指标、实验目标、审核记录",
        "output": "复盘结论、优化建议",
        "needs_llm": "是",
        "priority": "P1",
    },
    {
        "candidate_agent": "Memory Agent",
        "current_code": "app/services/startup_strategy_sev.py, local_registry strategy_memory tools",
        "current_shape": "普通 service / tool",
        "why": "策略沉淀和检索会成为后续上下文的重要来源。",
        "input": "复盘结果、策略、历史内容表现",
        "output": "可检索策略记忆",
        "needs_llm": "未来可能需要",
        "priority": "P1/P2",
    },
]


def project_root() -> Path:
    current = Path.cwd()
    if (current / "backend").exists():
        return current
    if current.name == "backend":
        return current.parent
    return current


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def collect_python_files(root: Path) -> list[Path]:
    backend = root / "backend"
    files: list[Path] = []
    for rel_dir in SCAN_DIRS:
        directory = backend / rel_dir
        if directory.exists():
            files.extend(path for path in directory.rglob("*.py") if "__pycache__" not in path.parts)
    return sorted(files)


def rel(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def count_keywords(text: str) -> dict[str, dict[str, int]]:
    return {
        group: {keyword: len(re.findall(re.escape(keyword), text, flags=re.IGNORECASE)) for keyword in keywords}
        for group, keywords in KEYWORD_GROUPS.items()
    }


def has_any(counts: dict[str, int]) -> bool:
    return any(value > 0 for value in counts.values())


def classify_file(path: Path, root: Path, text: str, counts: dict[str, dict[str, int]]) -> list[str]:
    rel_path = rel(path, root)
    classes: list[str] = []
    workflow_marker = (
        rel_path.startswith("backend/app/agent/")
        or "workflow_name" in text
        or "WorkflowStepSpec" in text
        or "ActionHandlerRegistry" in text
        or "PlanExecutionResult" in text
        or "ExecutionOrchestrator" in text
        or "step_name" in text
        or "step_order" in text
    )
    if has_any(counts["llm"]):
        classes.append("LLM_CALLER")
    if has_any(counts["prompt"]):
        classes.append("PROMPT_BUILDER")
    if has_any(counts["context"]):
        classes.append("CONTEXT_BUILDER")
    if workflow_marker:
        classes.append("WORKFLOW_STEP")
    if "backend/app/services/" in rel_path and "LLM_CALLER" not in classes and "WORKFLOW_STEP" not in classes:
        classes.append("ORDINARY_SERVICE")
    if "backend/app/repositories/" in rel_path:
        classes.append("REPOSITORY")
    if "backend/app/api/" in rel_path:
        classes.append("API_ENTRY")
    if "backend/app/llm/" in rel_path:
        classes.append("LLM_INFRA")
    if not classes:
        classes.append("UNKNOWN")
    return classes


def infer_business_module(path: Path, text: str) -> str:
    path_value = path.as_posix().lower()
    path_patterns = [
        ("content_draft_v2", ["content_draft_v2"]),
        ("content_draft", ["content_draft"]),
        ("review_report", ["review_report"]),
        ("competitor_report", ["competitor_report"]),
        ("competitor_analysis", ["competitor_analysis"]),
        ("content_experiment_v2", ["content_experiment_v2"]),
        ("content_experiment", ["content_experiment"]),
        ("post_publish", ["post_publish", "published_note", "private_conversion", "optimization"]),
        ("crawler_collection", ["crawler_collection", "xhs_note"]),
        ("keyword_seed", ["keyword_seed"]),
        ("confirmation", ["confirmation"]),
        ("strategy_memory", ["startup_strategy"]),
        ("agent_runtime", ["agent/runtime", "agent\\runtime"]),
        ("context_engineering", ["app/context"]),
        ("llm_infra", ["app/llm"]),
    ]
    for module, patterns in path_patterns:
        if any(pattern in path_value for pattern in patterns):
            return module

    value = f"{path_value} {text}".lower()
    module_patterns = [
        ("draft_generation", ["draft_generation", "draftcontent"]),
        ("content_draft", ["content_draft", "draftgenerate", "xhs_writer"]),
        ("review_report", ["review_report", "draftreview"]),
        ("competitor_report", ["competitor_report"]),
        ("competitor_analysis", ["competitor_analysis"]),
        ("competitor_account", ["competitor_account"]),
        ("competitor_note", ["competitor_note"]),
        ("comment_insight", ["comment_insight", "comment"]),
        ("content_opportunity", ["content_opportunity", "opportunity"]),
        ("content_experiment_v2", ["content_experiment_v2"]),
        ("content_experiment", ["content_experiment"]),
        ("post_publish", ["post_publish", "publish"]),
        ("strategy_memory", ["strategy_memory", "startup_strategy", "memory"]),
        ("agent_runtime", ["agent/product_entry", "executionorchestrator"]),
        ("context_engineering", ["app/context", "contextsnapshot", "builtcontext"]),
        ("llm_infra", ["app/llm", "llmclient", "llmresult"]),
        ("crawler_collection", ["crawler_collection", "crawler"]),
        ("keyword_seed", ["keyword_seed"]),
        ("confirmation", ["confirmation"]),
    ]
    for module, patterns in module_patterns:
        if any(pattern in value for pattern in patterns):
            return module
    return "unknown"


def extract_string_arg(text: str, name: str) -> list[str]:
    pattern = rf"{name}\s*=\s*[\"']([^\"']+)[\"']"
    return sorted(set(re.findall(pattern, text)))


def extract_schema_models(text: str) -> list[str]:
    return sorted(set(re.findall(r"schema_model\s*=\s*([A-Za-z_][A-Za-z0-9_]*)", text)))


def scan(root: Path) -> dict:
    files = collect_python_files(root)
    entries = []
    class_counts: Counter[str] = Counter()
    module_map: dict[str, list[dict]] = defaultdict(list)

    for path in files:
        text = read_text(path)
        counts = count_keywords(text)
        classes = classify_file(path, root, text, counts)
        module = infer_business_module(path, text)
        prompt_keys = extract_string_arg(text, "prompt_key")
        prompt_versions = extract_string_arg(text, "prompt_version")
        schema_models = extract_schema_models(text)
        direct_llm = "LLMClient()" in text or "LLMClient(" in text or ".generate_text(" in text or ".generate_structured(" in text
        entry = {
            "file": rel(path, root),
            "module": module,
            "classification": classes,
            "direct_llm": direct_llm,
            "call方式": call_style(text),
            "prompt_key": prompt_keys,
            "prompt_version": prompt_versions,
            "schema_model": schema_models,
            "keyword_hits": {group: sum(values.values()) for group, values in counts.items()},
        }
        entries.append(entry)
        module_map[module].append(entry)
        class_counts.update(classes)

    llm_entrypoints = [entry for entry in entries if "LLM_CALLER" in entry["classification"]]
    prompt_entrypoints = [entry for entry in entries if "PROMPT_BUILDER" in entry["classification"]]
    context_entrypoints = [entry for entry in entries if "CONTEXT_BUILDER" in entry["classification"]]
    workflow_entrypoints = [entry for entry in entries if "WORKFLOW_STEP" in entry["classification"]]

    return {
        "scanned_files_count": len(files),
        "class_counts": dict(class_counts),
        "llm_entrypoints": llm_entrypoints,
        "prompt_entrypoints": prompt_entrypoints,
        "context_entrypoints": context_entrypoints,
        "workflow_entrypoints": workflow_entrypoints,
        "service_classification": service_classification(entries),
        "agent_shape_analysis": agent_shape_analysis(workflow_entrypoints),
        "future_agent_candidates": FUTURE_AGENT_CANDIDATES,
        "priority_for_5_2": priority_for_5_2(entries, module_map),
        "unknown_or_need_manual_check": manual_checks(entries, module_map),
        "entries": entries,
        "module_summary": summarize_modules(module_map),
    }


def call_style(text: str) -> list[str]:
    styles = []
    if "generate_structured_with_context" in text:
        styles.append("generate_structured_with_context")
    if "generate_structured" in text:
        styles.append("generate_structured")
    if "generate_text" in text:
        styles.append("generate_text")
    if "LLMClient" in text and not styles:
        styles.append("LLMClient reference")
    return sorted(set(styles))


def service_classification(entries: list[dict]) -> dict:
    services = [entry for entry in entries if entry["file"].startswith("backend/app/services/")]
    return {
        "ordinary_services": [entry for entry in services if "ORDINARY_SERVICE" in entry["classification"]],
        "direct_llm_callers": [entry for entry in services if "LLM_CALLER" in entry["classification"]],
        "context_or_prompt_services": [
            entry
            for entry in services
            if "CONTEXT_BUILDER" in entry["classification"] or "PROMPT_BUILDER" in entry["classification"]
        ],
    }


def agent_shape_analysis(workflow_entries: list[dict]) -> dict:
    workflow_files = [entry for entry in workflow_entries if "/product_entry/" in entry["file"] and not entry["file"].endswith("__init__.py")]
    runtime_files = [entry for entry in workflow_entries if entry["file"].endswith("backend/app/agent/product_entry/executor.py")]
    return {
        "independent_agent_classes_detected": 0,
        "agent_runtime_files": [entry["file"] for entry in runtime_files],
        "workflow_files": [entry["file"] for entry in workflow_files],
        "workflow_count_detected": len(workflow_files),
        "shape": "当前为单一 product_entry 控制层 + Action Handler + 多个 service/provider；不是多个成熟自治 Agent 类。",
    }


def priority_for_5_2(entries: list[dict], module_map: dict[str, list[dict]]) -> dict[str, list[dict]]:
    def item(module: str, priority: str, reason: str) -> dict:
        files = sorted({entry["file"] for entry in module_map.get(module, [])})
        direct_llm = any(entry["direct_llm"] for entry in module_map.get(module, []))
        return {"module": module, "files": files, "direct_llm": direct_llm, "priority": priority, "reason": reason}

    return {
        "P0": [
            item("content_draft", "P0", "旧草稿生成直接调用 LLM structured，直接产生用户可见内容。"),
            item("content_draft_v2", "P0", "V2 草稿生成使用 ContextManager、PromptRunLog、ContextSnapshot，最适合做 token/context 基线。"),
            item("review_report", "P0", "审核报告直接调用 LLM structured，决定风险和修改建议。"),
            item("llm_infra", "P0", "LLMClient 是所有真实 LLM 调用的统一入口，需要记录解析和 metadata 基线。"),
        ],
        "P1": [
            item("content_experiment", "P1", "内容实验服务输出进入草稿链路，应继续统计输入输出，但旧示例 Workflow 已删除。"),
            item("content_experiment_v2", "P1", "实验/机会链路输出进入草稿生成，当前未发现直接 LLM 调用但应统计输入输出。"),
            item("competitor_report", "P1", "竞品报告当前未发现直接 LLM 调用，但输出进入实验和草稿上下文。"),
            item("competitor_analysis", "P1", "竞品分析结果影响后续机会和草稿，需要登记上下游字段。"),
            item("comment_insight", "P1", "评论需求识别当前多嵌在报告链路中，未来适合拆分并统计。"),
            item("post_publish", "P1", "发布后指标进入复盘和策略记忆，未来接 LLM 后应统计。"),
            item("context_engineering", "P1", "ContextManager、budget、snapshot 是 5.2 token 统计基础。"),
            item("strategy_memory", "P1", "策略记忆会成为 Writer/Reviewer 上下文来源。"),
        ],
        "P2": [
            item("keyword_seed", "P2", "关键词种子当前更像规则/CRUD 输入准备。"),
            item("crawler_collection", "P2", "采集链路主要是 provider/数据状态治理，暂未发现直接 LLM 调用。"),
            item("confirmation", "P2", "人工确认是治理节点，不是 LLM 调用入口。"),
            item("unknown", "P2", "未能稳定归类的 API、repository 或辅助模块先登记。"),
        ],
    }


def manual_checks(entries: list[dict], module_map: dict[str, list[dict]]) -> list[str]:
    checks = [
        "competitor_report / competitor_analysis 当前未发现直接 LLM 调用，但其输出会进入实验和草稿上下文，需人工确认第 5.2 是否纳入 P1 字段基线。",
        "comment_insight 未发现独立成熟 service，可能嵌在竞品报告或评论处理逻辑中。",
        "draft_generation_sev.py 使用结构化 DraftGenerationInput 和 prompt_key。",
        "api/llm.py 与 provider_health_rout.py 是测试/健康检查入口，不应当算入业务 Agent，但应登记为 LLM 调用入口。",
        "当前未发现多个成熟独立 Agent 类；不要在简历中夸大为多个自治 Agent。",
    ]
    if not module_map.get("content_opportunity"):
        checks.append("未发现独立 content_opportunity service 文件，机会生成可能在 experiment/report 链路中，需要人工确认。")
    return checks


def summarize_modules(module_map: dict[str, list[dict]]) -> list[dict]:
    rows = []
    for module in EXPECTED_MODULES:
        entries = module_map.get(module, [])
        files = sorted({entry["file"] for entry in entries})
        direct_llm = any(entry["direct_llm"] for entry in entries)
        classes = sorted({cls for entry in entries for cls in entry["classification"]})
        rows.append({"module": module, "files": files, "direct_llm": direct_llm, "classification": classes})
    return rows


def md_escape(value) -> str:
    if value is None:
        return ""
    if isinstance(value, list):
        value = ", ".join(str(item) for item in value) if value else "-"
    return str(value).replace("|", "\\|").replace("\n", " ")


def priority_for_module(module: str, priority: dict[str, list[dict]]) -> str:
    for level, items in priority.items():
        if any(item["module"] == module for item in items):
            return level
    return "P2"


def module_note(module: str, direct_llm: bool) -> str:
    notes = {
        "content_draft": "旧草稿生成链路，直接产生用户可见内容。",
        "content_draft_v2": "已有 ContextManager、PromptRunLog、ContextSnapshot，是 5.2 重点。",
        "review_report": "审核报告链路，直接影响风险和修改建议。",
        "competitor_report": "竞品报告输出会进入实验和草稿上下文。",
        "competitor_analysis": "分析型 service，当前更偏规则和数据聚合。",
        "comment_insight": "未发现独立成熟实现，可能嵌在竞品报告链路。",
        "content_experiment": "Agent workflow 使用的实验创建工具之一。",
        "post_publish": "发布后指标和复盘基础，未来可接 analytics agent。",
        "strategy_memory": "策略沉淀/检索，未来是上下文来源。",
        "agent_runtime": "当前统一 product_entry 控制层，不是多个独立 Agent。",
        "context_engineering": "上下文构建、预算、压缩、日志基础设施。",
        "llm_infra": "LLM provider/client 基础设施，不是业务 Agent。",
    }
    return notes.get(module, "未发现直接 LLM 调用，需按上下游关系人工确认。") if not direct_llm else notes.get(module, "直接调用 LLM。")


def write_report(root: Path, result: dict) -> Path:
    report_path = root / "docs" / "context_entrypoint_scan_report.md"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    priority = result["priority_for_5_2"]
    lines: list[str] = [
        "# 第 5.1.1 LLM / Context / Workflow 入口扫描报告",
        "",
        "## 1. 扫描目的",
        "",
        "本报告用于在 Context Engineering 前搞清楚项目中所有 LLM、Prompt、Context、Workflow 入口，避免只优化草稿生成而漏掉竞品分析、评论洞察、审核报告、Agent workflow 等链路。",
        "",
        "## 2. 扫描范围",
        "",
        "扫描目录：",
        "",
        *[f"- backend/{item}" for item in SCAN_DIRS],
        "",
        "关键词类别：LLM 调用、Prompt、Context、Agent / Workflow、业务链路关键词。",
        "",
        f"本次静态扫描 Python 文件数：{result['scanned_files_count']}。",
        "",
        "## 3. 当前 Agent 形态判断",
        "",
        "- 当前未发现多个成熟独立 Agent 类。",
        f"- 当前检测到 workflow 文件数：{result['agent_shape_analysis']['workflow_count_detected']}。",
        "- 当前工程形态更接近单 Agent Runtime + 多步骤 workflow + 多个 service/tool 的混合形态。",
        "- 它可以作为多 Agent 系统的雏形，但不应在简历中夸大为多个成熟自治 Agent。",
        "",
        "## 4. 入口总览表",
        "",
        "| 模块 | 文件 | 分类 | 是否直接调用 LLM | 调用方式 | prompt_key / version | schema_model | context 来源 | 是否 workflow step | 是否进入后续 LLM | 5.2 优先级 | 说明 |",
        "|---|---|---|---|---|---|---|---|---|---|---|---|",
    ]

    for row in result["module_summary"]:
        module = row["module"]
        files = row["files"] or ["NOT_FOUND"]
        entries = [entry for entry in result["entries"] if entry["module"] == module]
        prompt_keys = sorted({value for entry in entries for value in entry["prompt_key"]})
        prompt_versions = sorted({value for entry in entries for value in entry["prompt_version"]})
        schema_models = sorted({value for entry in entries for value in entry["schema_model"]})
        call_styles = sorted({value for entry in entries for value in entry["call方式"]})
        context_source = "ContextManager / BuiltContext / ContextSnapshot" if module in {"content_draft_v2", "context_engineering"} else "service 构造 dict / repository 数据"
        workflow_step = "是" if module in {"content_experiment", "agent_runtime"} else "否"
        downstream = "是" if module in {"competitor_report", "competitor_analysis", "content_experiment", "content_experiment_v2", "strategy_memory", "post_publish", "content_draft", "content_draft_v2", "review_report"} else "需确认"
        lines.append(
            "| "
            + " | ".join(
                [
                    md_escape(module),
                    md_escape(files),
                    md_escape(row["classification"] or ["NOT_FOUND"]),
                    "是" if row["direct_llm"] else "否",
                    md_escape(call_styles),
                    md_escape([*prompt_keys, *prompt_versions]),
                    md_escape(schema_models),
                    md_escape(context_source),
                    workflow_step,
                    downstream,
                    priority_for_module(module, priority),
                    md_escape(module_note(module, row["direct_llm"])),
                ]
            )
            + " |"
        )

    lines.extend(
        [
            "",
            "## 5. 普通 Service / Workflow Step / LLM Caller 分类",
            "",
            "### 5.1 普通 Service",
            "",
        ]
    )
    for entry in result["service_classification"]["ordinary_services"]:
        lines.append(
            f"- `{entry['file']}`：模块 `{entry['module']}`；是否构造 context：{'CONTEXT_BUILDER' in entry['classification']}；是否调用 LLM：否；是否进入后续 LLM：需按上下游确认。"
        )

    lines.extend(["", "### 5.2 Workflow Step / Tool", ""])
    for entry in result["workflow_entrypoints"]:
        lines.append(
            f"- `{entry['file']}`：分类 `{', '.join(entry['classification'])}`；input/output 可能进入 Agent trace；需要记录 Context Snapshot：{'是' if entry['module'] in {'content_draft_v2', 'context_engineering'} else '视是否接 LLM 而定'}。"
        )

    lines.extend(["", "### 5.3 直接 LLM Caller", ""])
    for entry in result["llm_entrypoints"]:
        lines.append(
            f"- `{entry['file']}`：调用方式 `{', '.join(entry['call方式']) or 'LLMClient reference'}`；schema_model `{', '.join(entry['schema_model']) or '-'}`；prompt_key `{', '.join(entry['prompt_key']) or '-'}`；已由 LLMClient 结构化校验兜底：是；是否进入 5.2：{'是' if entry['module'] in {'content_draft', 'content_draft_v2', 'review_report'} else '视入口性质登记'}。"
        )

    lines.extend(
        [
            "",
            "## 6. 未来适合拆成 Agent 的模块",
            "",
            "| 候选 Agent | 当前代码位置 | 当前形态 | 为什么适合拆 | 输入 | 输出 | 是否需要 LLM | 优先级 |",
            "|---|---|---|---|---|---|---|---|",
        ]
    )
    for item in result["future_agent_candidates"]:
        lines.append(
            "| "
            + " | ".join(
                [
                    md_escape(item["candidate_agent"]),
                    md_escape(item["current_code"]),
                    md_escape(item["current_shape"]),
                    md_escape(item["why"]),
                    md_escape(item["input"]),
                    md_escape(item["output"]),
                    md_escape(item["needs_llm"]),
                    md_escape(item["priority"]),
                ]
            )
            + " |"
        )

    lines.extend(["", "## 7. 第 5.2 建议统计范围", ""])
    for level in ["P0", "P1", "P2"]:
        lines.append(f"### {level}")
        lines.append("")
        for item in priority[level]:
            lines.append(f"- `{item['module']}`：{item['reason']}")
        lines.append("")

    lines.extend(
        [
            "竞品分析和同行账号是否需要统计：当前未发现直接 LLM 调用；但其输出会进入内容实验、机会判断和草稿上下文，因此建议 P1 登记字段、样本量、数据状态和下游使用位置。如果后续接入 LLM 分析，再升级为 P0。",
            "",
            "## 8. 风险和疑问",
            "",
        ]
    )
    for item in result["unknown_or_need_manual_check"]:
        lines.append(f"- {item}")

    lines.extend(
        [
            "",
            "## 9. 结论",
            "",
            "- 当前不是多个成熟独立 Agent 类，而是单一 product_entry 控制层 + Action Handler + 多个 service/provider 的形态。",
            "- 第 5.2 P0 建议优先统计 content_draft、content_draft_v2、review_report、LLMClient / LLM infra。",
            "- 第 5.2 P1 建议登记 content_experiment workflow、competitor_report / competitor_analysis、comment_insight、post_publish、context_engineering、strategy_memory。",
            "- 第 5.3 建议从 SYSTEM_RULES、TASK_INSTRUCTION、ACCOUNT_PROFILE、WORKFLOW_STATE、USER_INPUT、OUTPUT_SCHEMA、STRATEGY_MEMORY 这些 Context Slot 开始设计。",
        ]
    )

    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report_path


def main() -> int:
    root = project_root()
    result = scan(root)
    report_path = write_report(root, result)
    output = {
        "scanned_files_count": result["scanned_files_count"],
        "llm_entrypoints_count": len(result["llm_entrypoints"]),
        "prompt_entrypoints_count": len(result["prompt_entrypoints"]),
        "context_entrypoints_count": len(result["context_entrypoints"]),
        "workflow_entrypoints_count": len(result["workflow_entrypoints"]),
        "service_classification": {
            key: len(value) for key, value in result["service_classification"].items()
        },
        "agent_shape_analysis": result["agent_shape_analysis"],
        "future_agent_candidates": result["future_agent_candidates"],
        "priority_for_5_2": result["priority_for_5_2"],
        "unknown_or_need_manual_check": result["unknown_or_need_manual_check"],
        "report_path": rel(report_path, root),
    }
    print(json.dumps(output, ensure_ascii=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
