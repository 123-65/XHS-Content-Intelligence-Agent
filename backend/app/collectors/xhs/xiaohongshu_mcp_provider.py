import os
from typing import Any

import httpx

from app.collectors.xhs.base import XhsCollectionResult, XhsCollectorProvider
from app.collectors.xhs.normalizer import normalize_account_payload, normalize_note_payload


class XiaohongshuMcpProvider(XhsCollectorProvider):
    """Read-only adapter for an external xiaohongshu-mcp HTTP service."""

    provider_name = "xiaohongshu_mcp"
    source_type = "XHS_MCP"

    def __init__(self, base_url: str | None = None, timeout_seconds: int | None = None):
        self.base_url = (base_url if base_url is not None else os.getenv("XHS_MCP_BASE_URL") or "").rstrip("/")
        self.timeout_seconds = timeout_seconds or int(os.getenv("XHS_MCP_TIMEOUT_SECONDS") or "30")

    def collect_note(self, note_url: str, collect_comments: bool = True, max_comments: int = 20) -> XhsCollectionResult:
        if not self.base_url:
            return self._failure("PROVIDER_NOT_CONFIGURED", note_url, "XHS_MCP_BASE_URL is not configured.")
        payload = {"url": note_url, "note_url": note_url, "collect_comments": collect_comments, "max_comments": max_comments}
        return self._post_any(
            ["/notes/collect", "/note/detail", "/api/note/detail", "/api/v1/note/detail", "/mcp/tools/xhs_note_detail"],
            payload,
            source_url=note_url,
            result_type="note",
        )

    def collect_account(self, account_id_or_url: str, recent_note_limit: int = 10) -> XhsCollectionResult:
        if not self.base_url:
            return self._failure("PROVIDER_NOT_CONFIGURED", account_id_or_url, "XHS_MCP_BASE_URL is not configured.")
        payload = {
            "account_id_or_url": account_id_or_url,
            "user_id": account_id_or_url,
            "profile_url": account_id_or_url,
            "recent_note_limit": recent_note_limit,
        }
        return self._post_any(
            ["/accounts/collect", "/creator/detail", "/api/creator/detail", "/api/v1/creator/detail", "/mcp/tools/xhs_creator_detail"],
            payload,
            source_url=account_id_or_url,
            result_type="account",
        )

    def _post_any(self, paths: list[str], payload: dict[str, Any], *, source_url: str, result_type: str) -> XhsCollectionResult:
        last_error: XhsCollectionResult | None = None
        for path in paths:
            result = self._post(path, payload, source_url=source_url, result_type=result_type)
            if result.status != "COLLECT_FAILED" or result.error_code != "HTTP_404":
                return result
            last_error = result
        return last_error or self._failure("COLLECT_FAILED", source_url, "xiaohongshu-mcp endpoint was not found.")

    def _post(self, path: str, payload: dict[str, Any], *, source_url: str, result_type: str) -> XhsCollectionResult:
        try:
            response = httpx.post(f"{self.base_url}{path}", json=payload, timeout=self.timeout_seconds)
        except httpx.TimeoutException:
            return self._failure("PROVIDER_TIMEOUT", source_url, "xiaohongshu-mcp request timed out.")
        except httpx.ConnectError as exc:
            return self._failure("PROVIDER_NOT_CONFIGURED", source_url, f"xiaohongshu-mcp is not reachable: {exc}")
        except httpx.HTTPError as exc:
            return self._failure("COLLECT_FAILED", source_url, str(exc))

        if response.status_code == 404:
            return self._failure("COLLECT_FAILED", source_url, f"HTTP 404 for {path}", error_code="HTTP_404")
        if response.status_code in {401, 403}:
            return self._failure("LOGIN_REQUIRED", source_url, f"xiaohongshu-mcp requires login/session: HTTP {response.status_code}")
        if response.status_code == 440:
            return self._failure("LOGIN_REQUIRED", source_url, "xiaohongshu-mcp session expired.")
        if response.status_code == 429:
            return self._failure("RATE_LIMITED", source_url, "xiaohongshu-mcp rate limited.")
        if response.status_code >= 400:
            return self._failure("COLLECT_FAILED", source_url, f"xiaohongshu-mcp failed: HTTP {response.status_code}")
        try:
            data = response.json()
        except ValueError as exc:
            return self._failure("PARSE_FAILED", source_url, f"xiaohongshu-mcp returned non-JSON output: {exc}", raw_text=response.text[:20000])

        status = data.get("status") or ("SUCCESS" if data else "PARSE_FAILED")
        note = normalize_note_payload(data, source_url=source_url, provider_name=self.provider_name, source_type=self.source_type) if result_type == "note" else None
        account = normalize_account_payload(data, source_url=source_url, provider_name=self.provider_name, source_type=self.source_type) if result_type == "account" else None
        if result_type == "note" and not note:
            status = "PARSE_FAILED"
        if result_type == "account" and not account:
            status = "PARSE_FAILED"
        return XhsCollectionResult(
            status=status,
            provider_name=self.provider_name,
            source_url=source_url,
            parsed_note=note,
            parsed_result=note,
            parsed_account=account,
            raw_text=response.text[:20000],
            warnings=[str(item) for item in data.get("warnings") or []],
            error_code=data.get("error_code"),
            error_message=data.get("error_message"),
        )

    def _failure(self, status: str, source_url: str, message: str, error_code: str | None = None, raw_text: str | None = None) -> XhsCollectionResult:
        return XhsCollectionResult(
            status=status,
            provider_name=self.provider_name,
            source_url=source_url,
            error_code=error_code or status,
            error_message=message,
            raw_text=raw_text,
        )
