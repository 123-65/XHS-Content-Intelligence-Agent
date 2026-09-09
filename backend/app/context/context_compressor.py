import hashlib
import json
from typing import Any

from app.context.context_budget import estimate_tokens, trim_to_token_budget


class ToolResultCompressor:
    """Compress long tool outputs before they enter context or trace logs."""

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
        """Return a summary-first representation with hash metadata."""
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
        """Hash a payload after stable JSON serialization."""
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
