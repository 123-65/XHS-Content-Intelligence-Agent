import json

import httpx

from app.collectors.xhs.xiaohongshu_mcp_provider import XiaohongshuMcpProvider


def _mcp_response(payload: dict, *, is_error: bool = False) -> httpx.Response:
    content = [{"type": "text", "text": json.dumps(payload, ensure_ascii=False)}]
    return httpx.Response(200, json={"jsonrpc": "2.0", "id": 1, "result": {"content": content, "isError": is_error}})


def test_collect_note_uses_real_mcp_tool_contract_and_normalizes_payload() -> None:
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured.update(json.loads(request.content))
        return _mcp_response(
            {
                "note": {
                    "noteId": "note-1",
                    "title": "Real title",
                    "desc": "Real content",
                    "user": {"userId": "author-1", "nickname": "Real author"},
                    "interactInfo": {
                        "likedCount": "1.2万",
                        "collectedCount": "345",
                        "commentCount": "2",
                        "shareCount": "7",
                    },
                    "imageList": [{"urlDefault": "https://img.example/1.jpg"}],
                    "tagList": [{"name": "Agent"}],
                },
                "comments": [
                    {
                        "id": "comment-1",
                        "content": "How was this built?",
                        "likeCount": "8",
                        "userInfo": {"userId": "reader-1", "nickname": "Reader"},
                    }
                ],
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
    assert result.parsed_note.image_urls == ["https://img.example/1.jpg"]
    assert result.parsed_note.comments[0].comment_id == "comment-1"
    assert result.parsed_note.raw_payload["note"]["noteId"] == "note-1"
    assert "secret-token" not in result.source_url


def test_collect_account_uses_user_profile_and_normalizes_real_shape() -> None:
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured.update(json.loads(request.content))
        return _mcp_response(
            {
                "basicInfo": {
                    "userId": "user-1",
                    "nickname": "Peer account",
                    "desc": "Practical AI notes",
                    "images": "https://img.example/avatar.jpg",
                },
                "interactions": [
                    {"type": "follows", "count": "18"},
                    {"type": "fans", "count": "2.4万"},
                    {"type": "interaction", "count": "10万"},
                ],
                "feeds": [
                    {
                        "id": "recent-1",
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
    assert result.parsed_account.nickname == "Peer account"
    assert result.parsed_account.follower_count == 24000
    assert result.parsed_account.following_count == 18
    assert result.parsed_account.liked_count == 100000
    assert result.parsed_account.recent_notes[0].note_id == "recent-1"
    assert result.parsed_account.recent_notes[0].title == "Recent note"


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
