import hashlib
import json
import re
from typing import Any

from pydantic import ValidationError

from app.core.database import SessionLocal
from app.models.prompt_run_log import PromptRunLog


SECRET_KEY = re.compile(r"(api[_-]?key|authorization|cookie|secret|password|execution[_-]?token|lease[_-]?token)", re.I)
SECRET_VALUE = re.compile(r"(?i)(bearer\s+\S+|sk-[A-Za-z0-9_-]+|api[_-]?key\s*[:=]\s*\S+|password\s*[:=]\s*\S+)")


def safe_value(value: Any, *, preserve_scalar: bool = False) -> Any:
    """Keep structure and small validation scalars while removing content and secrets."""
    if isinstance(value, dict):
        return {
            str(key): "[REDACTED]" if SECRET_KEY.search(str(key)) else safe_value(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [safe_value(item) for item in value[:20]]
    if value is None or isinstance(value, (bool, int, float)):
        return value
    text = SECRET_VALUE.sub("[REDACTED]", str(value))
    if preserve_scalar and len(text) <= 120:
        return text
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]
    return f"<str:length={len(text)}:sha256={digest}>"


def validation_summary(exc: Exception, candidate: Any = None) -> dict[str, Any]:
    if hasattr(exc, "validation_path"):
        actual = getattr(exc, "actual_value", None)
        return {
            "validation_path": exc.validation_path,
            "expected": getattr(exc, "expected", type(exc).__name__),
            "actual_type": type(actual).__name__,
            "actual_value": safe_value(actual, preserve_scalar=True),
            "validation_error_type": type(exc).__name__,
        }
    if isinstance(exc, ValidationError):
        item = exc.errors(include_url=False)[0]
        return {
            "validation_path": ".".join(str(part) for part in item.get("loc", ())) or "$",
            "expected": item.get("msg") or item.get("type"),
            "actual_type": type(item.get("input")).__name__,
            "actual_value": safe_value(item.get("input"), preserve_scalar=True),
            "validation_error_type": item.get("type"),
        }
    return {
        "validation_path": "$",
        "expected": safe_value(str(exc), preserve_scalar=True),
        "actual_type": type(candidate).__name__ if candidate is not None else None,
        "actual_value": None,
        "validation_error_type": type(exc).__name__,
    }


class StructuredBusinessValidationError(ValueError):
    def __init__(self, message: str, *, validation_path: str, expected: str, actual_value: Any):
        super().__init__(message)
        self.validation_path = validation_path
        self.expected = expected
        self.actual_value = actual_value


class PromptRunEvidenceRecorder:
    """Persist minimal structured-attempt evidence in an independent transaction."""

    def record(self, evidence: dict[str, Any]) -> None:
        summary = {
            key: safe_value(value, preserve_scalar=True)
            for key, value in evidence.items()
            if key not in {"structured_candidate", "validation_summary"}
        }
        summary["validation_summary"] = {
            key: safe_value(value, preserve_scalar=True)
            for key, value in (evidence.get("validation_summary") or {}).items()
        }
        candidate = safe_value(evidence.get("structured_candidate"))
        with SessionLocal() as db:
            db.add(
                PromptRunLog(
                    prompt_name=evidence.get("prompt_key") or "structured_output",
                    prompt_version=evidence.get("prompt_version") or "unknown",
                    input_payload={},
                    input_summary={"schema": evidence.get("schema_name")},
                    rendered_prompt="",
                    output_text=None,
                    output_json=candidate if isinstance(candidate, dict) else {},
                    output_summary=summary,
                    model=evidence.get("model") or "unknown",
                    provider=evidence.get("provider") or "unknown",
                    prompt_key=evidence.get("prompt_key"),
                    latency_ms=int(evidence.get("latency_ms") or 0),
                    is_mock=False,
                    fallback_used=False,
                    status=evidence.get("attempt_status") or "FAILED",
                    error_message=json.dumps(summary.get("validation_summary") or {}, ensure_ascii=False)[:2000],
                )
            )
            db.commit()
