import json
import os
import re
import unicodedata
from typing import Any
from urllib.parse import parse_qs, urlparse

import httpx

from app.collectors.xhs.base import XhsCollectionResult, XhsCollectorProvider
from app.collectors.xhs.normalizer import normalize_account_payload, normalize_note_payload, sanitize_xhs_payload
from app.core.config import settings


class McpProviderError(RuntimeError):
    def __init__(self, code: str, message: str, raw_text: str | None = None):
        super().__init__(message)
        self.code = code
        self.raw_text = raw_text


class XiaohongshuMcpProvider(XhsCollectorProvider):
    """Read-only adapter for the official xiaohongshu-mcp Streamable HTTP endpoint."""

    provider_name = "xiaohongshu_mcp"
    source_type = "XHS_MCP"

    def __init__(
        self,
        base_url: str | None = None,
        timeout_seconds: int | None = None,
        transport: httpx.BaseTransport | None = None,
    ):
        self.base_url = (base_url if base_url is not None else os.getenv("XHS_MCP_BASE_URL", settings.xhs_mcp_base_url)).rstrip("/")
        self.timeout_seconds = timeout_seconds or int(os.getenv("XHS_MCP_TIMEOUT_SECONDS", str(settings.xhs_mcp_timeout_seconds)))
        self.auth_token = os.getenv("XHS_MCP_AUTH_TOKEN", settings.xhs_mcp_auth_token)
        self.host_header = os.getenv("XHS_MCP_HOST_HEADER", settings.xhs_mcp_host_header)
        self.transport = transport

    @property
    def mcp_url(self) -> str:
        return self.base_url if self.base_url.endswith("/mcp") else f"{self.base_url}/mcp"

    def list_tools(self) -> list[dict[str, Any]]:
        result = self._rpc("tools/list", {})
        tools = result.get("tools")
        return [item for item in tools if isinstance(item, dict)] if isinstance(tools, list) else []

    def check_login_status(self, *, probe_on_unknown: bool = True) -> dict[str, Any]:
        """Resolve authentication without treating an unrecognized response as logged out."""
        try:
            result, _ = self._call_tool("check_login_status", {})
        except McpProviderError as exc:
            return self._authentication_result_from_error(exc, source="check_login_status")

        state, source = self._login_state(result)
        if state == "UNKNOWN" and probe_on_unknown:
            state, source = self._authenticated_probe()
        return self._authentication_result(state, source=source)

    def authentication_preflight(self) -> dict[str, Any]:
        """Canonical preflight: semantic status parsing plus one bounded read-only probe."""
        return self.check_login_status(probe_on_unknown=True)

    @staticmethod
    def should_start_login(authentication: dict[str, Any]) -> bool:
        """Login is allowed only after a conclusive authentication failure."""
        return authentication.get("status") == "LOGIN_REQUIRED"

    def collect_note(self, note_url: str, collect_comments: bool = True, max_comments: int = 20) -> XhsCollectionResult:
        if not self.base_url:
            return self._failure("PROVIDER_NOT_CONFIGURED", self._redact_url(note_url), "XHS_MCP_BASE_URL is not configured.")
        target = self._parse_target(note_url, target_type="note")
        if not target:
            return self._failure(
                "UNSUPPORTED_URL",
                self._redact_url(note_url),
                "get_feed_detail requires a full XHS note URL containing feed_id and xsec_token.",
                error_code="XSEC_TOKEN_REQUIRED",
            )
        feed_id, xsec_token, canonical_url = target
        arguments: dict[str, Any] = {
            "feed_id": feed_id,
            "xsec_token": xsec_token,
            "load_all_comments": bool(collect_comments and max_comments > 10),
        }
        if collect_comments and max_comments > 10:
            arguments["limit"] = max_comments
        partial_comments = False
        retry_warning: str | None = None
        try:
            result, raw_text = self._call_tool("get_feed_detail", arguments)
            payload = self._tool_payload(result)
        except McpProviderError as exc:
            if exc.code != "PROVIDER_TIMEOUT":
                return self._failure(self._error_status(exc.code), canonical_url, str(exc), error_code=exc.code, raw_text=exc.raw_text)
            retry_arguments = arguments
            if collect_comments and max_comments > 10:
                retry_arguments = {"feed_id": feed_id, "xsec_token": xsec_token, "load_all_comments": False}
                partial_comments = True
            try:
                result, raw_text = self._call_tool("get_feed_detail", retry_arguments)
                payload = self._tool_payload(result)
                retry_warning = "PROVIDER_TIMEOUT_RETRIED"
            except McpProviderError as retry_exc:
                return self._failure(
                    self._error_status(retry_exc.code),
                    canonical_url,
                    str(retry_exc),
                    error_code=retry_exc.code,
                    raw_text=retry_exc.raw_text,
                )

        note = normalize_note_payload(
            payload,
            source_url=canonical_url,
            provider_name=self.provider_name,
            source_type=self.source_type,
        )
        if partial_comments:
            note.warnings.append("COMMENTS_PARTIAL_AFTER_TIMEOUT")
        comments_partial = collect_comments and note.comment_count is not None and note.comment_count > len(note.comments)
        if comments_partial:
            note.warnings.append("COMMENTS_PARTIAL_FROM_PROVIDER")
        if retry_warning:
            note.warnings.append(retry_warning)
        note.warnings = list(dict.fromkeys(note.warnings))
        status = "SUCCESS" if (note.title or note.content) and not partial_comments and not comments_partial else "PARTIAL_SUCCESS"
        note.status = status
        return XhsCollectionResult(
            status=status,
            provider_name=self.provider_name,
            source_url=canonical_url,
            parsed_note=note,
            parsed_result=note,
            raw_text=raw_text,
            warnings=note.warnings,
            is_mock=False,
        )

    def collect_account(self, account_id_or_url: str, recent_note_limit: int = 10) -> XhsCollectionResult:
        if not self.base_url:
            return self._failure(
                "PROVIDER_NOT_CONFIGURED",
                self._redact_url(account_id_or_url),
                "XHS_MCP_BASE_URL is not configured.",
            )
        target = self._parse_target(account_id_or_url, target_type="account")
        if not target:
            return self._failure(
                "UNSUPPORTED_URL",
                self._redact_url(account_id_or_url),
                "user_profile requires a full XHS profile URL containing user_id and xsec_token; a bare account ID is insufficient.",
                error_code="XSEC_TOKEN_REQUIRED",
            )
        user_id, xsec_token, canonical_url = target
        retry_warning: str | None = None
        try:
            result, raw_text = self._call_tool(
                "user_profile",
                {"user_id": user_id, "xsec_token": xsec_token, "tab": "note"},
            )
            payload = self._tool_payload(result)
        except McpProviderError as exc:
            if exc.code != "PROVIDER_TIMEOUT":
                return self._failure(self._error_status(exc.code), canonical_url, str(exc), error_code=exc.code, raw_text=exc.raw_text)
            try:
                result, raw_text = self._call_tool(
                    "user_profile",
                    {"user_id": user_id, "xsec_token": xsec_token, "tab": "note"},
                )
                payload = self._tool_payload(result)
                retry_warning = "PROVIDER_TIMEOUT_RETRIED"
            except McpProviderError as retry_exc:
                return self._failure(
                    self._error_status(retry_exc.code),
                    canonical_url,
                    str(retry_exc),
                    error_code=retry_exc.code,
                    raw_text=retry_exc.raw_text,
                )

        account = normalize_account_payload(
            payload,
            source_url=canonical_url,
            provider_name=self.provider_name,
            source_type=self.source_type,
        )
        account.recent_notes = account.recent_notes[:recent_note_limit]
        if retry_warning:
            account.warnings.append(retry_warning)
        status = "SUCCESS" if account.nickname else "PARTIAL_SUCCESS"
        account.status = status
        return XhsCollectionResult(
            status=status,
            provider_name=self.provider_name,
            source_url=canonical_url,
            parsed_account=account,
            raw_text=raw_text,
            warnings=account.warnings,
            is_mock=False,
        )

    def _rpc(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        if not self.base_url:
            raise McpProviderError("PROVIDER_NOT_CONFIGURED", "XHS_MCP_BASE_URL is not configured.")
        headers = {"Accept": "application/json, text/event-stream"}
        if self.auth_token:
            headers["Authorization"] = f"Bearer {self.auth_token}"
        if self.host_header:
            headers["Host"] = self.host_header
        request = {"jsonrpc": "2.0", "id": 1, "method": method, "params": params}
        try:
            with httpx.Client(timeout=self.timeout_seconds, transport=self.transport, trust_env=False) as client:
                response = client.post(self.mcp_url, json=request, headers=headers)
        except httpx.TimeoutException as exc:
            raise McpProviderError("PROVIDER_TIMEOUT", "xiaohongshu-mcp request timed out.") from exc
        except httpx.ConnectError as exc:
            raise McpProviderError("ENV_BLOCKED", f"xiaohongshu-mcp is configured but not reachable: {exc}") from exc
        except httpx.HTTPError as exc:
            raise McpProviderError("COLLECT_FAILED", str(exc)) from exc

        if response.status_code == 403 and "invalid Host header" in response.text:
            raise McpProviderError("ENV_BLOCKED", "xiaohongshu-mcp rejected the configured network host.")
        if response.status_code in {401, 403, 440}:
            raise McpProviderError("LOGIN_REQUIRED", f"xiaohongshu-mcp requires login/session: HTTP {response.status_code}")
        if response.status_code == 429:
            raise McpProviderError("RATE_LIMITED", "xiaohongshu-mcp rate limited the request.")
        if response.status_code >= 400:
            raise McpProviderError("COLLECT_FAILED", f"xiaohongshu-mcp failed: HTTP {response.status_code}", response.text[:20000])
        try:
            body = response.json()
        except ValueError as exc:
            raise McpProviderError("PARSE_FAILED", f"xiaohongshu-mcp returned non-JSON output: {exc}", response.text[:20000]) from exc
        if not isinstance(body, dict):
            raise McpProviderError("PARSE_FAILED", "xiaohongshu-mcp returned an invalid JSON-RPC response.", response.text[:20000])
        if isinstance(body.get("error"), dict):
            error = body["error"]
            raise McpProviderError("MCP_RPC_ERROR", str(error.get("message") or "MCP JSON-RPC error"), response.text[:20000])
        result = body.get("result")
        if not isinstance(result, dict):
            raise McpProviderError("PARSE_FAILED", "xiaohongshu-mcp JSON-RPC result is missing.", response.text[:20000])
        return result

    def _call_tool(self, name: str, arguments: dict[str, Any]) -> tuple[dict[str, Any], str]:
        result = self._rpc("tools/call", {"name": name, "arguments": arguments})
        raw_text = json.dumps(sanitize_xhs_payload(result), ensure_ascii=False)[:20000]
        if result.get("isError") is True:
            message = self._content_text(result) or f"MCP tool {name} failed."
            raise McpProviderError(self._tool_error_code(message), message, raw_text)
        return result, raw_text

    def _tool_payload(self, result: dict[str, Any]) -> dict[str, Any]:
        structured = result.get("structuredContent")
        if isinstance(structured, dict):
            return structured
        for item in result.get("content") or []:
            if not isinstance(item, dict) or item.get("type") != "text" or not isinstance(item.get("text"), str):
                continue
            try:
                parsed = json.loads(item["text"])
            except ValueError:
                continue
            if isinstance(parsed, dict):
                return parsed
            if isinstance(parsed, list):
                return {"items": parsed}
        raise McpProviderError("PARSE_FAILED", "xiaohongshu-mcp tool result did not contain a JSON object.", json.dumps(result, ensure_ascii=False)[:20000])

    def _parse_target(self, value: str, *, target_type: str) -> tuple[str, str, str] | None:
        parsed = urlparse(value.strip())
        if parsed.scheme not in {"http", "https"} or not parsed.netloc.lower().endswith("xiaohongshu.com"):
            return None
        query = parse_qs(parsed.query)
        token = (query.get("xsec_token") or query.get("xsecToken") or [""])[0]
        parts = [part for part in parsed.path.split("/") if part]
        marker = "profile" if target_type == "account" else next((item for item in ("explore", "item") if item in parts), "")
        if not marker or marker not in parts:
            return None
        marker_index = parts.index(marker)
        target_id = parts[marker_index + 1] if marker_index + 1 < len(parts) else ""
        if not target_id or not token:
            return None
        canonical_kind = "user/profile" if target_type == "account" else "explore"
        canonical_url = f"https://www.xiaohongshu.com/{canonical_kind}/{target_id}"
        return target_id, token, canonical_url

    def _content_text(self, result: dict[str, Any]) -> str:
        return "\n".join(
            str(item.get("text"))
            for item in result.get("content") or []
            if isinstance(item, dict) and item.get("type") == "text" and item.get("text")
        )

    def _login_state(self, result: dict[str, Any]) -> tuple[str, str]:
        structured = result.get("structuredContent")
        state = self._structured_login_state(structured)
        if state != "UNKNOWN":
            return state, "structured_content"

        for item in result.get("content") or []:
            if not isinstance(item, dict) or item.get("type") != "text" or not isinstance(item.get("text"), str):
                continue
            text = item["text"]
            try:
                decoded = json.loads(text)
            except ValueError:
                decoded = None
            state = self._structured_login_state(decoded)
            if state != "UNKNOWN":
                return state, "content_json"

        state = self._semantic_login_state(self._content_text(result))
        return state, "normalized_text" if state != "UNKNOWN" else "unknown_response"

    def _structured_login_state(self, value: Any) -> str:
        login_keys = {
            "authenticated",
            "isauthenticated",
            "isloggedin",
            "loggedin",
            "loginstate",
            "loginstatus",
        }
        if isinstance(value, dict):
            for key, item in value.items():
                normalized_key = re.sub(r"[^a-z0-9]", "", str(key).lower())
                if normalized_key in login_keys:
                    if isinstance(item, bool):
                        return "LOGGED_IN" if item else "LOGIN_REQUIRED"
                    if isinstance(item, (int, float)) and item in {0, 1}:
                        return "LOGGED_IN" if item == 1 else "LOGIN_REQUIRED"
                    if isinstance(item, str):
                        state = self._semantic_login_state(item)
                        if state != "UNKNOWN":
                            return state
                nested = self._structured_login_state(item)
                if nested != "UNKNOWN":
                    return nested
        elif isinstance(value, list):
            for item in value:
                nested = self._structured_login_state(item)
                if nested != "UNKNOWN":
                    return nested
        return "UNKNOWN"

    def _semantic_login_state(self, value: str) -> str:
        text = re.sub(r"\s+", " ", unicodedata.normalize("NFKC", value)).strip().casefold()
        if not text:
            return "UNKNOWN"
        logged_out_markers = (
            "\u672a\u767b\u5f55",
            "\u672a\u767b\u9646",
            "\u8bf7\u5148\u767b\u5f55",
            "\u8bf7\u5148\u767b\u9646",
            "\u9700\u8981\u767b\u5f55",
            "\u9700\u8981\u767b\u9646",
            "not logged in",
            "login required",
            "authentication required",
            "not authenticated",
            "unauthorized",
            "session expired",
            "cookie expired",
        )
        logged_in_markers = (
            "\u5df2\u767b\u5f55",
            "\u5df2\u767b\u9646",
            "\u767b\u5f55\u6210\u529f",
            "\u767b\u9646\u6210\u529f",
            "\u767b\u5f55\u72b6\u6001\u6b63\u5e38",
            "\u767b\u9646\u72b6\u6001\u6b63\u5e38",
            "logged in",
            "login successful",
            "authenticated",
            "session valid",
        )
        if any(marker in text for marker in logged_out_markers):
            return "LOGIN_REQUIRED"
        if any(marker in text for marker in logged_in_markers):
            return "LOGGED_IN"
        return "UNKNOWN"

    def _authenticated_probe(self) -> tuple[str, str]:
        try:
            self._call_tool("get_my_profile", {})
        except McpProviderError as exc:
            if exc.code == "LOGIN_REQUIRED":
                return "LOGIN_REQUIRED", "authenticated_probe"
            if exc.code == "ENV_BLOCKED":
                return "ENV_BLOCKED", "authenticated_probe"
            return "UNKNOWN", "authenticated_probe"
        return "LOGGED_IN", "authenticated_probe"

    def _authentication_result(self, state: str, *, source: str) -> dict[str, Any]:
        auth_state = state if state in {"LOGGED_IN", "LOGIN_REQUIRED", "UNKNOWN"} else "UNKNOWN"
        return {
            "status": state,
            "auth_state": auth_state,
            "is_logged_in": True if state == "LOGGED_IN" else False if state == "LOGIN_REQUIRED" else None,
            "status_source": source,
            "provider_name": self.provider_name,
            "is_mock": False,
        }

    def _authentication_result_from_error(self, exc: McpProviderError, *, source: str) -> dict[str, Any]:
        if exc.code == "LOGIN_REQUIRED":
            state = "LOGIN_REQUIRED"
        elif exc.code == "ENV_BLOCKED":
            state = "ENV_BLOCKED"
        else:
            state = "UNKNOWN"
        return self._authentication_result(state, source=source)

    def _tool_error_code(self, message: str) -> str:
        lowered = message.lower()
        if "deadline exceeded" in lowered or "timed out" in lowered or "timeout" in lowered:
            return "PROVIDER_TIMEOUT"
        if self._semantic_login_state(message) == "LOGIN_REQUIRED" or "cookie" in lowered or "session" in lowered:
            return "LOGIN_REQUIRED"
        if "captcha" in lowered or "验证" in message or "风控" in message:
            return "RATE_LIMITED"
        return "COLLECT_FAILED"

    def _error_status(self, code: str) -> str:
        if code in {"LOGIN_REQUIRED", "RATE_LIMITED", "PARSE_FAILED", "PROVIDER_NOT_CONFIGURED", "PROVIDER_TIMEOUT", "ENV_BLOCKED"}:
            return code
        return "COLLECT_FAILED"

    def _redact_url(self, value: str) -> str:
        parsed = urlparse(value.strip())
        if parsed.scheme not in {"http", "https"}:
            return value.strip()
        return f"{parsed.scheme}://{parsed.netloc}{parsed.path}"

    def _failure(
        self,
        status: str,
        source_url: str,
        message: str,
        error_code: str | None = None,
        raw_text: str | None = None,
    ) -> XhsCollectionResult:
        return XhsCollectionResult(
            status=status,
            provider_name=self.provider_name,
            source_url=source_url,
            error_code=error_code or status,
            error_message=message,
            raw_text=raw_text,
            is_mock=False,
        )
