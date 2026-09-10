from __future__ import annotations

import json
from pathlib import Path


def project_root() -> Path:
    """Locate the repository root from the repo root or backend directory."""
    current = Path.cwd()
    if (current / "backend").exists():
        return current
    if current.name == "backend":
        return current.parent
    return current


def read_text(path: Path) -> str:
    """Read a UTF-8 text file; return an empty string when it is missing."""
    return path.read_text(encoding="utf-8") if path.exists() else ""


def contains_all(text: str, keywords: list[str]) -> bool:
    """Return whether every keyword exists in the given text."""
    return all(keyword in text for keyword in keywords)


def main() -> int:
    """Print the current project engineering metrics baseline."""
    root = project_root()
    backend = root / "backend"
    files = {
        "provider_status": backend / "app" / "schemas" / "provider_status.py",
        "llm_smoke_test": backend / "scripts" / "llm_smoke_test.py",
        "llm_client": backend / "app" / "llm" / "client.py",
        "mcp_gateway": backend / "app" / "mcp" / "gateway.py",
        "crawler_provider_factory": backend / "app" / "crawler" / "providers" / "factory.py",
        "content_draft_tests": backend / "tests" / "test_content_draft.py",
        "review_report_tests": backend / "tests" / "test_review_report.py",
    }
    texts = {name: read_text(path) for name, path in files.items()}
    failure_keywords = ["LLM_CONFIG_MISSING", "LLM_OUTPUT_PARSE_FAILED", "LLM_SCHEMA_INVALID"]
    report = {
        "python_test_baseline": {
            "passed": 115,
            "warning": 1,
            "note": "记录自第 4.4 阶段全量测试结果；本脚本不运行 pytest。",
        },
        "files_exist": {name: path.exists() for name, path in files.items()},
        "provider_status_file_exists": files["provider_status"].exists(),
        "provider_status_enums": contains_all(
            texts["provider_status"],
            ["DataStatus", "ProviderSourceType", "ProviderErrorCode"],
        ),
        "llm_smoke_test_exists": files["llm_smoke_test"].exists(),
        "llm_smoke_test_ready": files["llm_smoke_test"].exists() and "--provider" in texts["llm_smoke_test"],
        "mock_seed_isolation_checks": {
            "mcp_gateway_requires_allow_mock": "allow_mock" in texts["mcp_gateway"],
            "crawler_factory_has_demo_provider_names": "DEMO_PROVIDER_NAMES" in texts["crawler_provider_factory"],
            "crawler_factory_has_production_order": "PRODUCTION_PROVIDER_ORDER" in texts["crawler_provider_factory"],
            "content_draft_use_mock_defaults_false": "use_mock: bool = Field(default=False" in texts["content_draft_tests"]
            or "use_mock: bool = Field(default=False" in read_text(backend / "app" / "schemas" / "content_draft.py"),
            "review_report_use_mock_defaults_false": "use_mock: bool = Field(default=False" in texts["review_report_tests"]
            or "use_mock: bool = Field(default=False" in read_text(backend / "app" / "schemas" / "review_report.py"),
        },
        "structured_llm_tests_keywords": {
            "content_draft_failure_tests": {
                keyword: keyword in texts["content_draft_tests"] for keyword in failure_keywords
            },
            "review_report_failure_tests": {
                keyword: keyword in texts["review_report_tests"] for keyword in failure_keywords
            },
        },
        "structured_llm_checks": {
            "llm_client_has_parse_error_code": "LLM_OUTPUT_PARSE_FAILED" in texts["llm_client"],
            "llm_client_has_schema_error_code": "LLM_SCHEMA_INVALID" in texts["llm_client"],
            "content_draft_failure_tests": contains_all(texts["content_draft_tests"], failure_keywords),
            "review_report_failure_tests": contains_all(texts["review_report_tests"], failure_keywords),
        },
        "known_engineering_capabilities": [
            "Agent Trace 可观测字段记录",
            "Mock / Seed 生产默认链路隔离",
            "Provider 状态码统一枚举",
            "LLM 结构化输出强校验",
            "草稿生成失败不入库",
            "审核报告失败不入库",
        ],
        "future_metrics_to_collect": [
            "平均输入 token",
            "上下文压缩率",
            "LLM 调用延迟",
            "结构化输出 Schema 通过率",
            "输出解析成功率",
            "Agent 失败定位耗时",
        ],
    }
    print(json.dumps(report, ensure_ascii=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
