"""Phase B1.1 headed Edge acceptance; all turns are submitted through the visible UI."""

import json
import re
import sys
from pathlib import Path

from playwright.sync_api import Page, sync_playwright


BASE_URL = "http://127.0.0.1:5173"
ACCOUNT_REF = 8456
CHAT_CASES = (
    ("CHAT-02", "你能做什么"),
    ("CHAT-03", "你是怎么知道的"),
    ("CHAT-04", "现在起你叫张三"),
    ("CHAT-12", "我跟你普通对话"),
    ("CHAT-05", "你现在叫张三"),
    ("CHAT-06", "你有记忆吗"),
    ("CHAT-07", "你记得我刚才让你叫什么吗"),
)
FORBIDDEN_CHAT_MARKERS = (
    "选择内容机会",
    "选择研究结果",
    "选择已发布笔记",
    "REFERENCE_CONTEXT_MISSING",
    "research_artifact_ref",
    "opportunity_ref",
    "必要信息",
)


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    mode = sys.argv[1].upper() if len(sys.argv) > 1 else "ALL"
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(channel="msedge", headless=False)
        page = browser.new_page(viewport={"width": 1440, "height": 1000})
        account_name = fresh_conversation(page)
        output = {"browser": "Microsoft Edge (headed)", "account_ref": ACCOUNT_REF, "account_name": account_name}

        if mode in {"ALL", "CHAT"}:
            chat_results = [run_case(page, case_id, text) for case_id, text in CHAT_CASES]
            output["chat"] = chat_results
            output["workflow_run_count"] = sum(1 for item in chat_results if item["run_ref"])
            output["forbidden_markers"] = sorted({
                marker
                for item in chat_results
                for marker in FORBIDDEN_CHAT_MARKERS
                if marker in item["visible_message"]
            })
            output["chat_pass"] = (
                output["workflow_run_count"] == 0
                and not output["forbidden_markers"]
                and all(item["network_response_captured"] for item in chat_results)
            )

        if mode in {"ALL", "REGRESSION"}:
            note_url, profile_url = authorized_urls()

            fresh_conversation(page)
            d02 = run_case(page, "D02", f"分析这篇：\n{note_url}", redact_input=True, timeout_ms=190_000)

            fresh_conversation(page)
            l02_first = run_case(page, "L02-1", "帮我分析一个同行账号", timeout_ms=60_000)
            l02_second = run_case(page, "L02-2", profile_url, redact_input=True, timeout_ms=190_000)

            fresh_conversation(page)
            page.goto(f"{BASE_URL}/agent/draft/2625", wait_until="networkidle")
            selection = page.locator(".actions .el-button--primary")
            selection.wait_for(timeout=10_000)
            selection.click()
            page.wait_for_url("**/agent/chat**")
            c01 = run_case(page, "C01", "这篇写得太差了", timeout_ms=60_000)

            output["regression"] = {
                "D02": d02,
                "L02": {"first": l02_first, "continuation": l02_second},
                "C01": c01,
            }

        print(json.dumps(output, ensure_ascii=False, indent=2))
        browser.close()


def authorized_urls() -> tuple[str, str]:
    source = Path(__file__).resolve().parents[3] / "xhs链接.md"
    text = source.read_text(encoding="utf-8")
    note = re.search(r"https://www\.xiaohongshu\.com/(?:explore|item)/[^\s<>\"']+", text)
    profile = re.search(r"https://www\.xiaohongshu\.com/user/profile/[^\s<>\"']+", text)
    if note is None or profile is None:
        raise RuntimeError("Authorized Profile or Note URL not found")
    return note.group(0).rstrip(")],;"), profile.group(0).rstrip(")],;")


def fresh_conversation(page: Page) -> str:
    page.goto(f"{BASE_URL}/agent/chat", wait_until="networkidle")
    page.evaluate("localStorage.clear()")
    with page.expect_response(
        lambda response: response.url.rstrip("/").endswith("/accounts") and response.request.method == "GET",
        timeout=15_000,
    ) as response_info:
        page.reload(wait_until="networkidle")
    payload = response_info.value.json()
    accounts = payload.get("data", payload)
    target = next((item for item in accounts if item.get("id") == ACCOUNT_REF), None)
    if target is None:
        raise RuntimeError(f"Account {ACCOUNT_REF} was not available in the UI account list")
    page.locator(".header-controls .el-select").click()
    page.locator(".el-select-dropdown__item").filter(has_text=target["account_name"]).last.click()
    page.wait_for_timeout(300)
    return target["account_name"]


def run_case(page: Page, case_id: str, text: str, *, redact_input: bool = False, timeout_ms: int = 60_000) -> dict:
    before = page.locator("article.message.assistant").count()
    composer = page.locator(".composer .el-textarea__inner").first
    composer.fill(text)
    with page.expect_response(
        lambda response: "/api/agent/turns" in response.url and response.request.method == "POST",
        timeout=timeout_ms,
    ) as response_info:
        page.locator(".composer-tools .el-button--primary").click()
    response = response_info.value
    payload = response.json()
    page.wait_for_function(
        "count => document.querySelectorAll('article.message.assistant').length > count || !!document.querySelector('.technical-details')",
        arg=before,
        timeout=10_000,
    )
    turn = (payload.get("data") or payload).get("turn", {})
    assistant = page.locator("article.message.assistant .message-content > p")
    return {
        "case_id": case_id,
        "input": "<AUTHORIZED_URL_REDACTED>" if redact_input else text,
        "visible_message": assistant.last.inner_text() if assistant.count() else "",
        "intent": turn.get("intent"),
        "action": turn.get("action"),
        "status": turn.get("status"),
        "run_ref": turn.get("run_ref"),
        "warnings": turn.get("warnings", []),
        "pending_required_fields": (turn.get("pending_interaction") or {}).get("required_fields", []),
        "network_response_captured": response.ok,
    }


if __name__ == "__main__":
    main()
