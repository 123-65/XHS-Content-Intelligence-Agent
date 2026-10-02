import json

import httpx

from app.collectors.xhs.xiaohongshu_mcp_provider import XiaohongshuMcpProvider


def _mcp_response(payload: dict, *, is_error: bool = False) -> httpx.Response:
    content = [{"type": "text", "text": json.dumps(payload, ensure_ascii=False)}]
    return httpx.Response(200, json={"jsonrpc": "2.0", "id": 1, "result": {"content": content, "isError": is_error}})


def _mcp_text_response(text: str, *, is_error: bool = False) -> httpx.Response:
    content = [{"type": "text", "text": text}]
    return httpx.Response(200, json={"jsonrpc": "2.0", "id": 1, "result": {"content": content, "isError": is_error}})


def test_v240_logged_in_text_response_is_logged_in() -> None:
    provider = XiaohongshuMcpProvider(
        base_url="http://collector:18060",
        transport=httpx.MockTransport(lambda request: _mcp_text_response("\u2705 \u5df2\u767b\u5f55\n\u5f53\u524d\u4f1a\u8bdd\u53ef\u7528")),
    )

    result = provider.check_login_status()

    assert result["status"] == "LOGGED_IN"
    assert result["auth_state"] == "LOGGED_IN"
    assert result["is_logged_in"] is True
    assert result["status_source"] == "normalized_text"


def test_structured_login_state_takes_priority_over_text() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        result = {
            "structuredContent": {"isLoggedIn": True},
            "content": [{"type": "text", "text": "\u672a\u767b\u5f55"}],
        }
        return httpx.Response(200, json={"jsonrpc": "2.0", "id": 1, "result": result})

    provider = XiaohongshuMcpProvider(
        base_url="http://collector:18060",
        transport=httpx.MockTransport(handler),
    )

    result = provider.check_login_status()

    assert result["status"] == "LOGGED_IN"
    assert result["status_source"] == "structured_content"


def test_explicit_logged_out_response_is_login_required() -> None:
    provider = XiaohongshuMcpProvider(
        base_url="http://collector:18060",
        transport=httpx.MockTransport(lambda request: _mcp_text_response("\u672a\u767b\u5f55\uff0c\u8bf7\u5148\u767b\u5f55")),
    )

    result = provider.check_login_status()

    assert result["status"] == "LOGIN_REQUIRED"
    assert result["auth_state"] == "LOGIN_REQUIRED"
    assert result["is_logged_in"] is False


def test_unknown_response_remains_unknown_without_probe() -> None:
    provider = XiaohongshuMcpProvider(
        base_url="http://collector:18060",
        transport=httpx.MockTransport(lambda request: _mcp_text_response("status could not be determined")),
    )

    result = provider.check_login_status(probe_on_unknown=False)

    assert result["status"] == "UNKNOWN"
    assert result["auth_state"] == "UNKNOWN"
    assert result["is_logged_in"] is None


def test_unknown_response_with_authenticated_probe_success_is_logged_in() -> None:
    tool_names: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        tool_name = json.loads(request.content)["params"]["name"]
        tool_names.append(tool_name)
        if tool_name == "check_login_status":
            return _mcp_text_response("status could not be determined")
        return _mcp_text_response("profile available")

    provider = XiaohongshuMcpProvider(
        base_url="http://collector:18060",
        transport=httpx.MockTransport(handler),
    )

    result = provider.authentication_preflight()

    assert result["status"] == "LOGGED_IN"
    assert result["status_source"] == "authenticated_probe"
    assert tool_names == ["check_login_status", "get_my_profile"]


def test_unknown_response_with_authentication_failure_is_login_required() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        tool_name = json.loads(request.content)["params"]["name"]
        if tool_name == "check_login_status":
            return _mcp_text_response("status could not be determined")
        return _mcp_text_response("login required", is_error=True)

    provider = XiaohongshuMcpProvider(
        base_url="http://collector:18060",
        transport=httpx.MockTransport(handler),
    )

    result = provider.authentication_preflight()

    assert result["status"] == "LOGIN_REQUIRED"
    assert result["auth_state"] == "LOGIN_REQUIRED"
    assert result["status_source"] == "authenticated_probe"


def test_network_failure_is_env_blocked_not_login_required() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=request)

    provider = XiaohongshuMcpProvider(
        base_url="http://collector:18060",
        transport=httpx.MockTransport(handler),
    )

    result = provider.authentication_preflight()

    assert result["status"] == "ENV_BLOCKED"
    assert result["auth_state"] == "UNKNOWN"
    assert result["is_logged_in"] is None


def test_logged_in_state_never_invokes_login_executable() -> None:
    invocation_count = 0
    provider = XiaohongshuMcpProvider(
        base_url="http://collector:18060",
        transport=httpx.MockTransport(lambda request: _mcp_text_response("\u5df2\u767b\u5f55")),
    )

    authentication = provider.authentication_preflight()
    if provider.should_start_login(authentication):
        invocation_count += 1

    assert authentication["status"] == "LOGGED_IN"
    assert invocation_count == 0


def test_collect_note_uses_real_mcp_tool_contract_and_normalizes_payload() -> None:
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured.update(json.loads(request.content))
        return _mcp_response(
            {
                "feed_id": "note-1",
                "data": {
                    "note": {
                        "noteId": "note-1",
                        "title": "Real title",
                        "desc": "Real content",
                        "user": {"userId": "author-1", "nickname": "Real author"},
                        "interactInfo": {
                            "likedCount": "1.2万",
                            "collectedCount": "345",
                            "commentCount": "1",
                            "sharedCount": "7",
                        },
                        "imageList": [{"urlDefault": "https://img.example/1.jpg"}],
                        "tagList": [{"name": "Agent"}],
                    },
                    "comments": {
                        "list": [
                            {
                                "id": "comment-1",
                                "content": "How was this built?",
                                "likeCount": "8",
                                "userInfo": {"userId": "reader-1", "nickname": "Reader"},
                            }
                        ]
                    },
                },
            }
        )

    provider = XiaohongshuMcpProvider(
        base_url="http://collector:18060",
        transport=httpx.MockTransport(handler),
    )
    result = provider.collect_note(
        "https://www.xiaohongshu.com/explore/note-1?xsec_token=secret-token&xsec_source=pc_feed",
        max_comments=20,
    )

    assert captured["method"] == "tools/call"
    assert captured["params"]["name"] == "get_feed_detail"
    assert captured["params"]["arguments"] == {
        "feed_id": "note-1",
        "xsec_token": "secret-token",
        "load_all_comments": True,
        "limit": 20,
    }
    assert result.status == "SUCCESS"
    assert result.provider_name == "xiaohongshu_mcp"
    assert result.is_mock is False
    assert result.source_url == "https://www.xiaohongshu.com/explore/note-1"
    assert result.parsed_note is not None
    assert result.parsed_note.title == "Real title"
    assert result.parsed_note.author_id == "author-1"
    assert result.parsed_note.like_count == 12000
    assert result.parsed_note.share_count == 7
    assert result.parsed_note.image_urls == ["https://img.example/1.jpg"]
    assert result.parsed_note.comments[0].comment_id == "comment-1"
    assert result.parsed_note.raw_payload["data"]["note"]["noteId"] == "note-1"
    assert "secret-token" not in result.source_url


def test_collect_account_uses_user_profile_and_normalizes_real_shape() -> None:
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured.update(json.loads(request.content))
        return _mcp_response(
            {
                "userBasicInfo": {
                    "nickname": "Peer account",
                    "desc": "Practical AI notes",
                    "images": "https://img.example/avatar.jpg",
                    "redId": "display-id",
                },
                "interactions": [
                    {"type": "follows", "count": "18"},
                    {"type": "fans", "count": "2.4万"},
                    {"type": "interaction", "count": "10万"},
                ],
                "feeds": [
                    {
                        "id": "recent-1",
                        "xsecToken": "must-not-be-persisted",
                        "cookie": "must-not-be-persisted",
                        "noteCard": {
                            "displayTitle": "Recent note",
                            "user": {"userId": "user-1", "nickname": "Peer account"},
                        },
                    }
                ],
            }
        )

    provider = XiaohongshuMcpProvider(
        base_url="http://collector:18060/mcp",
        transport=httpx.MockTransport(handler),
    )
    result = provider.collect_account(
        "https://www.xiaohongshu.com/user/profile/user-1?xsec_token=profile-token",
        recent_note_limit=5,
    )

    assert captured["params"]["name"] == "user_profile"
    assert captured["params"]["arguments"] == {"user_id": "user-1", "xsec_token": "profile-token", "tab": "note"}
    assert result.status == "SUCCESS"
    assert result.is_mock is False
    assert result.parsed_account is not None
    assert result.parsed_account.account_id == "user-1"
    assert result.parsed_account.nickname == "Peer account"
    assert result.parsed_account.follower_count == 24000
    assert result.parsed_account.following_count == 18
    assert result.parsed_account.liked_count == 100000
    assert result.parsed_account.recent_notes[0].note_id == "recent-1"
    assert result.parsed_account.recent_notes[0].title == "Recent note"
    serialized_payload = json.dumps(result.parsed_account.raw_payload)
    assert "must-not-be-persisted" not in serialized_payload
    assert "xsecToken" not in serialized_payload
    assert "cookie" not in serialized_payload
    assert "profile-token" not in (result.raw_text or "")


def test_collect_note_retries_with_partial_comments_after_full_comment_timeout() -> None:
    requests: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        requests.append(payload)
        if payload["params"]["arguments"]["load_all_comments"]:
            raise httpx.ReadTimeout("all comments timed out", request=request)
        return _mcp_response({"data": {"note": {"noteId": "note-1", "title": "Real title"}, "comments": {"list": []}}})

    provider = XiaohongshuMcpProvider(base_url="http://collector:18060", transport=httpx.MockTransport(handler))
    result = provider.collect_note(
        "https://www.xiaohongshu.com/explore/note-1?xsec_token=secret-token",
        collect_comments=True,
        max_comments=20,
    )

    assert result.status == "PARTIAL_SUCCESS"
    assert result.parsed_note is not None
    assert result.parsed_note.title == "Real title"
    assert result.parsed_note.warnings == ["COMMENTS_PARTIAL_AFTER_TIMEOUT", "PROVIDER_TIMEOUT_RETRIED"]
    assert [item["params"]["arguments"]["load_all_comments"] for item in requests] == [True, False]


def test_collect_note_marks_provider_comment_subset_as_partial() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return _mcp_response(
            {
                "data": {
                    "note": {
                        "noteId": "note-1",
                        "title": "Real title",
                        "interactInfo": {"commentCount": "12"},
                    },
                    "comments": {"list": [{"id": "comment-1", "content": "Real comment"}]},
                }
            }
        )

    provider = XiaohongshuMcpProvider(base_url="http://collector:18060", transport=httpx.MockTransport(handler))
    result = provider.collect_note(
        "https://www.xiaohongshu.com/explore/note-1?xsec_token=secret-token",
        collect_comments=True,
        max_comments=10,
    )

    assert result.status == "PARTIAL_SUCCESS"
    assert result.warnings == ["COMMENTS_PARTIAL_FROM_PROVIDER"]
    assert result.parsed_note is not None
    assert len(result.parsed_note.comments) == 1


def test_collect_note_retries_bounded_request_once_after_timeout() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise httpx.ReadTimeout("bounded request timed out", request=request)
        return _mcp_response({"data": {"note": {"noteId": "note-1", "title": "Real title"}, "comments": {"list": []}}})

    provider = XiaohongshuMcpProvider(base_url="http://collector:18060", transport=httpx.MockTransport(handler))
    result = provider.collect_note(
        "https://www.xiaohongshu.com/explore/note-1?xsec_token=secret-token",
        collect_comments=True,
        max_comments=10,
    )

    assert calls == 2
    assert result.status == "SUCCESS"
    assert result.warnings == ["PROVIDER_TIMEOUT_RETRIED"]


def test_missing_xsec_token_is_a_real_failure_without_mock_fallback() -> None:
    provider = XiaohongshuMcpProvider(base_url="http://collector:18060")

    result = provider.collect_note("https://www.xiaohongshu.com/explore/note-1")

    assert result.status == "UNSUPPORTED_URL"
    assert result.error_code == "XSEC_TOKEN_REQUIRED"
    assert result.parsed_note is None
    assert result.is_mock is False


def test_mcp_tool_error_maps_to_login_required() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        result = {"content": [{"type": "text", "text": "未登录，请先登录"}], "isError": True}
        return httpx.Response(200, json={"jsonrpc": "2.0", "id": 1, "result": result})

    provider = XiaohongshuMcpProvider(
        base_url="http://collector:18060",
        transport=httpx.MockTransport(handler),
    )
    result = provider.collect_note("https://www.xiaohongshu.com/explore/note-1?xsec_token=secret-token")

    assert result.status == "LOGIN_REQUIRED"
    assert result.error_code == "LOGIN_REQUIRED"
    assert result.parsed_note is None
    assert result.is_mock is False


def test_configured_host_header_supports_docker_to_windows_connection(monkeypatch) -> None:
    monkeypatch.setenv("XHS_MCP_HOST_HEADER", "localhost:18060")

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["host"] == "localhost:18060"
        return httpx.Response(
            200,
            json={"jsonrpc": "2.0", "id": 1, "result": {"tools": [{"name": "check_login_status"}]}},
        )

    provider = XiaohongshuMcpProvider(
        base_url="http://host.docker.internal:18060",
        transport=httpx.MockTransport(handler),
    )

    assert [item["name"] for item in provider.list_tools()] == ["check_login_status"]
