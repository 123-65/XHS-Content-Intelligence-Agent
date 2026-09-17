import os

import pytest

from app.collectors.xhs.provider_types import SUCCESS_STATUSES
from app.collectors.xhs.xiaohongshu_mcp_provider import XiaohongshuMcpProvider


pytestmark = pytest.mark.skipif(
    os.getenv("RUN_REAL_XHS_INTEGRATION") != "1",
    reason="set RUN_REAL_XHS_INTEGRATION=1 with private XHS test inputs to run",
)


def test_real_xhs_mcp_contract() -> None:
    note_url = os.environ.get("XHS_TEST_NOTE_URL")
    account_id_or_url = os.environ.get("XHS_TEST_ACCOUNT_URL") or os.environ.get("XHS_TEST_ACCOUNT_ID")
    assert note_url, "XHS_TEST_NOTE_URL is required"
    assert account_id_or_url, "XHS_TEST_ACCOUNT_URL is required"

    provider = XiaohongshuMcpProvider()
    login = provider.check_login_status()
    assert login["status"] == "SUCCESS"
    assert login["is_logged_in"] is True
    assert login["provider_name"] == "xiaohongshu_mcp"
    assert login["is_mock"] is False

    tool_names = {item.get("name") for item in provider.list_tools()}
    assert {"check_login_status", "get_feed_detail", "user_profile"}.issubset(tool_names)

    note_result = provider.collect_note(note_url, collect_comments=True, max_comments=10)
    assert note_result.status in SUCCESS_STATUSES
    assert note_result.provider_name == "xiaohongshu_mcp"
    assert note_result.is_mock is False
    assert note_result.parsed_note is not None
    assert note_result.parsed_note.title or note_result.status == "PARTIAL_SUCCESS"
    assert note_result.parsed_note.raw_payload

    account_result = provider.collect_account(account_id_or_url, recent_note_limit=10)
    assert account_result.status in SUCCESS_STATUSES
    assert account_result.provider_name == "xiaohongshu_mcp"
    assert account_result.is_mock is False
    assert account_result.parsed_account is not None
    assert account_result.parsed_account.raw_payload
