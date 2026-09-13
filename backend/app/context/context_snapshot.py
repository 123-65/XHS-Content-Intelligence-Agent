import hashlib
import json
import re
from dataclasses import dataclass
from typing import Any


SENSITIVE_KEYWORDS = {
    "api_key",
    "apikey",
    "authorization",
    "cookie",
    "password",
    "secret",
    "token",
    "access_token",
    "refresh_token",
    "phone",
    "mobile",
    "email",
}

SENSITIVE_PATTERNS = [
    re.compile(r"sk-[A-Za-z0-9_-]{12,}"),
    re.compile(r"Bearer\s+[A-Za-z0-9._-]+", re.IGNORECASE),
    re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+"),
    re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)"),
]


@dataclass(frozen=True)
class TraceRetentionRule:
    """追踪日志表的存储保留策略。"""

    log_table: str
    retention_days: int
    max_raw_chars: int
    summary_chars: int
    raw_payload_policy: str = "summary_hash_when_long"
    hash_algorithm: str = "sha256"
    redact_sensitive: bool = True


DEFAULT_TRACE_RETENTION_POLICIES: dict[str, TraceRetentionRule] = {
    "agent_step": TraceRetentionRule("agent_step", retention_days=30, max_raw_chars=8000, summary_chars=1200),
    "prompt_run_log": TraceRetentionRule("prompt_run_log", retention_days=14, max_raw_chars=6000, summary_chars=1600),
    "mcp_tool_call_log": TraceRetentionRule("mcp_tool_call_log", retention_days=14, max_raw_chars=6000, summary_chars=1200),
    "context_snapshot": TraceRetentionRule("context_snapshot", retention_days=30, max_raw_chars=10000, summary_chars=2000),
}


class TracePayloadGovernor:
    """在持久化前对追踪 payload 做脱敏、摘要和 hash。"""

    def policy_for(self, log_table: str) -> TraceRetentionRule:
        """返回某个追踪表的保留策略。"""
        return DEFAULT_TRACE_RETENTION_POLICIES.get(log_table, DEFAULT_TRACE_RETENTION_POLICIES["agent_step"])

    def govern_payload(self, payload: Any, log_table: str) -> Any:
        """治理结构化 payload 的存储内容。"""
        rule = self.policy_for(log_table)
        redacted = self.redact(payload) if rule.redact_sensitive else payload
        raw_text = self._to_json(redacted)
        if len(raw_text) <= rule.max_raw_chars:
            return redacted
        return {
            "storage_policy": "summary_only",
            "summary": raw_text[: rule.summary_chars],
            "raw_hash": self.hash_text(raw_text),
            "raw_length": len(raw_text),
            "truncated": True,
        }

    def govern_text(self, text: str | None, log_table: str) -> str | None:
        """治理纯文本的存储内容。"""
        if text is None:
            return None
        rule = self.policy_for(log_table)
        redacted = self.redact_text(text) if rule.redact_sensitive else text
        if len(redacted) <= rule.max_raw_chars:
            return redacted
        return (
            "[SUMMARY_ONLY]\n"
            f"raw_hash={self.hash_text(redacted)}\n"
            f"raw_length={len(redacted)}\n"
            f"summary={redacted[: rule.summary_chars]}"
        )

    def redact(self, value: Any) -> Any:
        """对字典、列表和字符串中的敏感值做脱敏。"""
        if isinstance(value, dict):
            return {key: self._redact_value(key, item) for key, item in value.items()}
        if isinstance(value, list):
            return [self.redact(item) for item in value]
        if isinstance(value, str):
            return self.redact_text(value)
        return value

    def redact_text(self, value: str) -> str:
        """对字符串里的敏感模式做脱敏。"""
        redacted = value
        for pattern in SENSITIVE_PATTERNS:
            redacted = pattern.sub("[REDACTED]", redacted)
        return redacted

    def hash_text(self, text: str) -> str:
        """返回文本的 sha256 hash。"""
        return hashlib.sha256(text.encode("utf-8")).hexdigest()

    def policies_as_dicts(self) -> list[dict[str, Any]]:
        """返回可公开展示的保留策略明细。"""
        return [
            {
                **rule.__dict__,
                "sensitive_fields": sorted(SENSITIVE_KEYWORDS),
                "redact_patterns": ["api keys", "bearer tokens", "emails", "mainland China mobile numbers"],
            }
            for rule in DEFAULT_TRACE_RETENTION_POLICIES.values()
        ]

    def _redact_value(self, key: str, value: Any) -> Any:
        lowered = key.lower()
        if any(keyword in lowered for keyword in SENSITIVE_KEYWORDS):
            return "[REDACTED]"
        return self.redact(value)

    def _to_json(self, value: Any) -> str:
        return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)
