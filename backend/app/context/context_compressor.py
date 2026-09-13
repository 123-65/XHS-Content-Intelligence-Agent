import hashlib
import json
from typing import Any

from app.context.context_budget import estimate_tokens, rough_token_count, trim_to_token_budget


TRUST_RANK = {
    "REAL": 60,
    "MANUAL": 55,
    "MCP": 50,
    "XHS_PUBLIC_READONLY": 45,
    "UNKNOWN": 30,
    "PARTIAL": 20,
}

BLOCKED_DATA_STATUS = {"FAILED", "MOCK", "SEED_SAMPLE"}
BLOCKED_SOURCE_TYPE = {"MOCK", "SEED_SAMPLE", "TEST", "DEMO"}
BLOCKED_PROVIDER_NAME = {"mock", "seed_sample"}
HIGH_RISK_VALUES = {"HIGH", "BLOCKED"}


def select_competitor_evidence_top_k(
    items: list[dict],
    top_k: int = 5,
    query_context: dict | None = None,
) -> tuple[list[dict], dict]:
    """根据可信度、相关性、互动表现、多样性和风险过滤筛选竞品证据 Top-K。"""
    safe_top_k = max(0, int(top_k or 0))
    before_text = _stable_json(items)
    drop_reason: dict[str, int] = {}
    query_keywords = _query_keywords(query_context or {})
    candidates: list[tuple[tuple, int, dict]] = []

    for index, item in enumerate(items):
        copied = dict(item)
        blocked_reason = _blocked_reason(copied)
        if blocked_reason:
            _count_reason(drop_reason, blocked_reason)
            continue
        candidates.append((_score_item(copied, query_keywords), index, copied))

    candidates.sort(key=lambda value: value[0], reverse=True)
    selected: list[dict] = []
    delayed_by_diversity: list[dict] = []
    title_pattern_counts: dict[str, int] = {}
    content_pillar_counts: dict[str, int] = {}
    author_counts: dict[str, int] = {}

    for _, _, item in candidates:
        if len(selected) >= safe_top_k:
            _count_reason(drop_reason, "not_in_top_k")
            continue
        if _hits_diversity_limit(item, title_pattern_counts, content_pillar_counts, author_counts):
            delayed_by_diversity.append(item)
            continue
        selected.append(item)
        _record_diversity_keys(item, title_pattern_counts, content_pillar_counts, author_counts)

    for item in delayed_by_diversity:
        if len(selected) < safe_top_k:
            selected.append(item)
            continue
        _count_reason(drop_reason, "diversity_limit")

    after_text = _stable_json(selected)
    warning = None
    if delayed_by_diversity:
        warning = "部分候选证据命中多样性限制；如果候选不足，会回填少量重复类型证据"

    compression_meta = {
        "compressed": True,
        "truncated": False,
        "compression_method": "deterministic_top_k",
        "before_chars": len(before_text),
        "after_chars": len(after_text),
        "before_rough_tokens": rough_token_count(before_text),
        "after_rough_tokens": rough_token_count(after_text),
        "selected_count": len(selected),
        "dropped_count": max(0, len(items) - len(selected)),
        "drop_reason": drop_reason,
        "top_k": safe_top_k,
        "summary_generated": False,
        "warning": warning,
    }
    return selected, compression_meta


def select_strategy_memory_items(
    items: list[dict],
    top_k: int = 5,
    query_context: dict | None = None,
) -> tuple[list[dict], dict]:
    """根据同领域、置信度、新鲜度和结果验证筛选策略记忆。"""
    safe_top_k = max(0, int(top_k or 0))
    before_text = _stable_json(items)
    drop_reason: dict[str, int] = {}
    query_context = query_context or {}
    query_keywords = _strategy_query_keywords(query_context)
    query_domain_version = str(query_context.get("domain_profile_version") or "").strip()
    candidates: list[tuple[tuple, int, dict, bool]] = []

    for index, item in enumerate(items):
        copied = dict(item)
        blocked_reason = _strategy_memory_blocked_reason(copied, query_domain_version)
        if blocked_reason:
            _count_reason(drop_reason, blocked_reason)
            continue
        candidates.append(
            (
                _score_strategy_memory(copied, query_keywords, query_domain_version),
                index,
                copied,
                _is_failure_memory(copied),
            )
        )

    candidates.sort(key=lambda value: (value[0], -value[1]), reverse=True)
    selected_rows = _pick_strategy_memory_rows(candidates, safe_top_k)
    selected = [item for _, _, item, _ in selected_rows]
    selected_ids = {id(item) for _, _, item, _ in selected_rows}
    for _, _, item, _ in candidates:
        if id(item) not in selected_ids:
            _count_reason(drop_reason, "not_in_top_k")

    after_text = _stable_json(selected)
    warning = None
    if any(is_failure for *_, is_failure in selected_rows):
        warning = "已保留少量失败复盘，用于避免重复踩坑"

    compression_meta = {
        "compressed": True,
        "truncated": False,
        "compression_method": "deterministic_strategy_memory_filter",
        "before_chars": len(before_text),
        "after_chars": len(after_text),
        "before_rough_tokens": rough_token_count(before_text),
        "after_rough_tokens": rough_token_count(after_text),
        "selected_count": len(selected),
        "dropped_count": max(0, len(items) - len(selected)),
        "drop_reason": drop_reason,
        "top_k": safe_top_k,
        "summary_generated": False,
        "warning": warning,
    }
    return selected, compression_meta


class ToolResultCompressor:
    """在工具输出进入上下文或追踪日志前，对长内容做有界压缩。"""

    def __init__(self, default_top_k: int = 5, default_max_tokens: int = 800):
        self.default_top_k = default_top_k
        self.default_max_tokens = default_max_tokens

    def compress(
        self,
        payload: Any,
        *,
        top_k: int | None = None,
        allowed_fields: list[str] | None = None,
        max_tokens: int | None = None,
    ) -> dict[str, Any]:
        """返回摘要优先的结构，并附带原始内容 hash 等元数据。"""
        raw_text = self._to_json(payload)
        filtered = self._filter_fields(payload, allowed_fields)
        clipped = self._top_k(filtered, top_k or self.default_top_k)
        compressed_text = self._to_json(clipped)
        trimmed_text, truncated = trim_to_token_budget(compressed_text, max_tokens or self.default_max_tokens)
        return {
            "summary": self._summary(trimmed_text),
            "data": self._safe_json_load(trimmed_text),
            "raw_hash": self.hash_payload(payload),
            "raw_length": len(raw_text),
            "original_tokens": estimate_tokens(raw_text),
            "compressed_tokens": estimate_tokens(trimmed_text),
            "truncated": truncated or len(compressed_text) != len(raw_text),
            "compression": {
                "top_k": top_k or self.default_top_k,
                "allowed_fields": allowed_fields or [],
                "max_tokens": max_tokens or self.default_max_tokens,
            },
        }

    def hash_payload(self, payload: Any) -> str:
        """对稳定 JSON 序列化后的 payload 计算 hash。"""
        return hashlib.sha256(self._to_json(payload).encode("utf-8")).hexdigest()

    def _filter_fields(self, payload: Any, allowed_fields: list[str] | None) -> Any:
        if not allowed_fields:
            return payload
        allowed = set(allowed_fields)
        if isinstance(payload, dict):
            filtered = {}
            for key, value in payload.items():
                if key in allowed:
                    filtered[key] = self._filter_fields(value, allowed_fields)
                    continue
                child = self._filter_fields(value, allowed_fields)
                if child not in ({}, []):
                    filtered[key] = child
            return filtered
        if isinstance(payload, list):
            return [self._filter_fields(item, allowed_fields) for item in payload]
        return payload

    def _top_k(self, payload: Any, top_k: int) -> Any:
        if isinstance(payload, list):
            return [self._top_k(item, top_k) for item in payload[:top_k]]
        if isinstance(payload, dict):
            return {key: self._top_k(value, top_k) for key, value in payload.items()}
        return payload

    def _summary(self, text: str) -> str:
        return text[:500]

    def _to_json(self, payload: Any) -> str:
        return json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)

    def _safe_json_load(self, text: str) -> Any:
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return {"text": text}


def _blocked_reason(item: dict) -> str | None:
    data_status = _upper_text(item.get("data_status"))
    source_type = _upper_text(item.get("source_type"))
    provider_name = str(item.get("provider_name") or "").lower()
    risk_level = _upper_text(item.get("risk_level"))
    if item.get("is_mock") is True:
        return "mock"
    if item.get("risk_blocked") is True:
        return "risk_blocked"
    if data_status in BLOCKED_DATA_STATUS:
        return f"data_status_{data_status.lower()}"
    if source_type in BLOCKED_SOURCE_TYPE:
        return f"source_type_{source_type.lower()}"
    if provider_name in BLOCKED_PROVIDER_NAME:
        return f"provider_{provider_name}"
    if risk_level in HIGH_RISK_VALUES:
        return "high_risk"
    return None


def _score_item(item: dict, query_keywords: set[str]) -> tuple:
    trust_score = _trust_score(item)
    relevance_score = _relevance_score(item, query_keywords)
    interaction_score = _interaction_score(item)
    freshness_score = _freshness_score(item)
    confidence_score = _number(item.get("confidence"))
    return (trust_score, relevance_score, interaction_score, freshness_score, confidence_score)


def _pick_strategy_memory_rows(
    candidates: list[tuple[tuple, int, dict, bool]],
    top_k: int,
) -> list[tuple[tuple, int, dict, bool]]:
    if top_k <= 0:
        return []

    failure_limit = 0 if top_k <= 1 else (2 if top_k >= 6 else 1)
    selected: list[tuple[tuple, int, dict, bool]] = []
    failure_rows = [row for row in candidates if row[3]]
    positive_rows = [row for row in candidates if not row[3]]

    selected.extend(failure_rows[:failure_limit])
    selected.extend(positive_rows[: max(0, top_k - len(selected))])

    if len(selected) < top_k and len(failure_rows) > failure_limit:
        selected.extend(failure_rows[failure_limit : top_k - len(selected) + failure_limit])

    selected = selected[:top_k]
    selected.sort(key=lambda value: (value[0], -value[1]), reverse=True)
    return selected


def _score_strategy_memory(item: dict, query_keywords: set[str], query_domain_version: str) -> tuple:
    domain_score = _strategy_domain_score(item, query_keywords, query_domain_version)
    confidence_score = _strategy_confidence(item)
    freshness_score = _freshness_score(item)
    verified_score = 1 if _has_result_validation(item) else 0
    failure_score = 1 if _is_failure_memory(item) else 0
    return (domain_score, confidence_score, freshness_score, verified_score, failure_score)


def _strategy_memory_blocked_reason(item: dict, query_domain_version: str) -> str | None:
    blocked_reason = _blocked_reason(item)
    if blocked_reason:
        return blocked_reason
    confidence = _strategy_confidence(item)
    if confidence < 0.2:
        return "low_confidence"
    if _domain_profile_version_mismatch(item, query_domain_version):
        return "domain_profile_version_mismatch"
    return None


def _strategy_domain_score(item: dict, query_keywords: set[str], query_domain_version: str) -> int:
    score = 0
    if query_domain_version and str(item.get("domain_profile_version") or "").strip() == query_domain_version:
        score += 3
    haystack = _strategy_memory_haystack(item)
    score += sum(1 for keyword in query_keywords if keyword and keyword.lower() in haystack)
    return score


def _strategy_memory_haystack(item: dict) -> str:
    parts = [
        item.get("memory_type"),
        item.get("summary"),
        item.get("pattern"),
        item.get("usage_reason"),
        item.get("content_pillar"),
        item.get("memory_domain"),
        item.get("account_type"),
        item.get("target_audience"),
    ]
    parts.extend(item.get("tags") or [])
    return " ".join(str(part or "") for part in parts).lower()


def _strategy_confidence(item: dict) -> float:
    values = [item.get("confidence"), item.get("score"), item.get("reliability")]
    normalized = [_normalize_confidence(value) for value in values if value is not None]
    if not normalized:
        return 0.5
    return max(normalized)


def _normalize_confidence(value: Any) -> float:
    number = _number(value)
    if number > 1:
        number = number / 100
    return max(0.0, min(1.0, number))


def _has_result_validation(item: dict) -> bool:
    return any(
        bool(item.get(key))
        for key in (
            "result_metric",
            "result_value",
            "success_or_failure",
            "verified",
            "usage_snapshot",
            "has_result",
        )
    )


def _is_failure_memory(item: dict) -> bool:
    values = [
        item.get("success_or_failure"),
        item.get("result_status"),
        item.get("outcome"),
        item.get("memory_type"),
        item.get("sentiment"),
    ]
    failure_values = {"failure", "failed", "negative", "ineffective", "invalid", "失败", "无效", "负向"}
    return any(str(value or "").strip().lower() in failure_values for value in values)


def _domain_profile_version_mismatch(item: dict, query_domain_version: str) -> bool:
    item_version = str(item.get("domain_profile_version") or "").strip()
    return bool(query_domain_version and item_version and item_version != query_domain_version and not _is_generic_memory(item))


def _is_generic_memory(item: dict) -> bool:
    if item.get("is_generic") is True:
        return True
    values = [
        item.get("scope"),
        item.get("memory_domain"),
        *(item.get("tags") or []),
    ]
    generic_values = {"general", "generic", "global", "通用", "全局"}
    return any(str(value or "").strip().lower() in generic_values for value in values)


def _strategy_query_keywords(query_context: dict) -> set[str]:
    keywords: set[str] = set()
    for key in ("selected_topic", "topic", "content_pillar", "target_audience", "account_type", "memory_domain"):
        _add_keywords(keywords, query_context.get(key))
    for key in ("account_profile", "domain_profile"):
        nested = query_context.get(key)
        if isinstance(nested, dict):
            for nested_key in ("content_domain", "positioning", "target_audience", "account_type", "content_pillar", "memory_domain"):
                _add_keywords(keywords, nested.get(nested_key))
            for nested_key in ("domain_keywords", "tags", "keywords"):
                _add_keywords(keywords, nested.get(nested_key))
    for key in ("account_keywords", "domain_keywords", "keywords", "tags"):
        _add_keywords(keywords, query_context.get(key))
    return {keyword.strip().lower() for keyword in keywords if keyword and keyword.strip()}


def _add_keywords(keywords: set[str], value: Any) -> None:
    if not value:
        return
    if isinstance(value, (list, tuple, set)):
        for item in value:
            _add_keywords(keywords, item)
        return
    text = str(value)
    keywords.add(text)
    keywords.update(text.split())


def _trust_score(item: dict) -> int:
    data_status = _upper_text(item.get("data_status"))
    source_type = _upper_text(item.get("source_type"))
    provider_name = _upper_text(item.get("provider_name"))
    return max(TRUST_RANK.get(data_status, 0), TRUST_RANK.get(source_type, 0), TRUST_RANK.get(provider_name, 0))


def _relevance_score(item: dict, query_keywords: set[str]) -> int:
    if not query_keywords:
        return 0
    haystack = " ".join(
        [
            str(item.get("title") or ""),
            str(item.get("content") or ""),
            str(item.get("summary") or ""),
            str(item.get("evidence_summary") or ""),
            str(item.get("content_pillar") or ""),
            str(item.get("title_pattern") or ""),
            " ".join(str(tag) for tag in (item.get("tags") or [])),
        ]
    ).lower()
    return sum(1 for keyword in query_keywords if keyword and keyword.lower() in haystack)


def _interaction_score(item: dict) -> float:
    return (_number(item.get("collect_count")) * 3) + (_number(item.get("like_count")) * 2) + _number(item.get("comment_count"))


def _freshness_score(item: dict) -> str:
    return str(item.get("updated_at") or item.get("published_at") or item.get("created_at") or "")


def _query_keywords(query_context: dict) -> set[str]:
    keywords: set[str] = set()
    for key in ("selected_topic", "topic", "content_pillar"):
        value = query_context.get(key)
        if value:
            keywords.add(str(value))
            keywords.update(str(value).split())
    for key in ("account_keywords", "domain_keywords", "keywords"):
        value = query_context.get(key) or []
        if isinstance(value, str):
            value = [value]
        keywords.update(str(item) for item in value if item)
    return {keyword.strip().lower() for keyword in keywords if keyword and keyword.strip()}


def _hits_diversity_limit(
    item: dict,
    title_pattern_counts: dict[str, int],
    content_pillar_counts: dict[str, int],
    author_counts: dict[str, int],
) -> bool:
    title_pattern = _diversity_key(item.get("title_pattern"))
    content_pillar = _diversity_key(item.get("content_pillar"))
    author = _diversity_key(item.get("author_id") or item.get("account_id"))
    return (
        (bool(title_pattern) and title_pattern_counts.get(title_pattern, 0) >= 2)
        or (bool(content_pillar) and content_pillar_counts.get(content_pillar, 0) >= 2)
        or (bool(author) and author_counts.get(author, 0) >= 2)
    )


def _record_diversity_keys(
    item: dict,
    title_pattern_counts: dict[str, int],
    content_pillar_counts: dict[str, int],
    author_counts: dict[str, int],
) -> None:
    for value, counts in (
        (_diversity_key(item.get("title_pattern")), title_pattern_counts),
        (_diversity_key(item.get("content_pillar")), content_pillar_counts),
        (_diversity_key(item.get("author_id") or item.get("account_id")), author_counts),
    ):
        if value:
            counts[value] = counts.get(value, 0) + 1


def _diversity_key(value: Any) -> str:
    return str(value or "").strip().lower()


def _number(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0


def _upper_text(value: Any) -> str:
    return str(value or "").strip().upper()


def _count_reason(drop_reason: dict[str, int], reason: str) -> None:
    drop_reason[reason] = drop_reason.get(reason, 0) + 1


def _stable_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)
