"""Phase B1 real Edge UI acceptance; submits only through the visible product UI."""

import json
import sys
from playwright.sync_api import sync_playwright


BASE_URL = "http://127.0.0.1:5173"
ACCOUNT_REF = 8456
NOTE_URL = "https://www.xiaohongshu.com/explore/6a335dbe000000000f01d537?xsec_token=ABdI3IUeatWf93oKL_Mb6WoHs3msXn148ZSe_wdBW-t94=&xsec_source=pc_search&source=web_explore_feed"
PROFILE_URL = "https://www.xiaohongshu.com/user/profile/5d38107b0000000012021405?xsec_token=AB-myX73mfmMwo-_qH_rOtFI3s8_dq4amUUlrvvcO039s=&xsec_source=pc_user"


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    results = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(channel="msedge", headless=False)
        page = browser.new_page(viewport={"width": 1440, "height": 1000})
        account_name = select_account(page)

        def fresh() -> None:
            page.evaluate("localStorage.clear()")
            select_account(page)

        if sys.argv[1:] == ["K01"]:
            first = run_case(page, "K01-1", "我不喜欢标题里用逆袭")
            second = run_case(page, "K01", "再给我一个标题")
            second["setup"] = first
            results.append(second)
            output = {
                "browser": "Microsoft Edge (Playwright channel=msedge, headed)",
                "account_ref": ACCOUNT_REF,
                "account_name": account_name,
                "cases": results,
            }
            print(json.dumps(output, ensure_ascii=False, indent=2))
            browser.close()
            return
        if sys.argv[1:] == ["C01"]:
            page.goto(f"{BASE_URL}/agent/draft/2625", wait_until="networkidle")
            selection = page.locator(".actions .el-button--primary")
            selection.wait_for(timeout=10_000)
            selection.click()
            page.wait_for_url("**/agent/chat**")
            results.append(run_case(page, "C01", "这篇写得太差了"))
            output = {
                "browser": "Microsoft Edge (Playwright channel=msedge, headed)",
                "account_ref": ACCOUNT_REF,
                "account_name": account_name,
                "cases": results,
            }
            print(json.dumps(output, ensure_ascii=False, indent=2))
            browser.close()
            return

        results.append(run_case(page, "A01", "你好，简单介绍一下你自己"))
        fresh()
        results.append(run_case(page, "A03", "你能做什么？"))
        fresh()
        results.append(run_case(page, "A04", "你有哪些 skill？"))
        fresh()
        results.append(run_case(page, "A05", "你有哪些工具？"))
        fresh()
        results.append(run_case(page, "A07", "帮我自动发布到小红书"))
        fresh()
        results.append(run_case(page, "A08", "帮我自动评论"))

        fresh()
        page.goto(f"{BASE_URL}/agent/draft/2625", wait_until="networkidle")
        selection = page.locator(".actions .el-button--primary")
        selection.wait_for(timeout=10_000)
        selection.click()
        page.wait_for_url("**/agent/chat**")
        results.append(run_case(page, "C01", "这篇写得太差了"))

        fresh()
        results.append(run_case(page, "D02", f"分析这篇：\n{NOTE_URL}"))

        fresh()
        first = run_case(page, "K01-1", "我不喜欢标题里用逆袭")
        second = run_case(page, "K01", "再给我一个标题")
        second["setup"] = first
        results.append(second)

        fresh()
        first = run_case(page, "L02-1", "帮我分析一个同行账号")
        second = run_case(page, "L02", PROFILE_URL)
        second["setup"] = first
        results.append(second)

        output = {
            "browser": "Microsoft Edge (Playwright channel=msedge, headed)",
            "account_ref": ACCOUNT_REF,
            "account_name": account_name,
            "cases": results,
        }
        print(json.dumps(output, ensure_ascii=False, indent=2))
        browser.close()


def select_account(page):
    accounts = []

    def capture(response):
        nonlocal accounts
        if response.url.rstrip("/").endswith("/accounts") and response.request.method == "GET":
            try:
                accounts = response.json().get("data", [])
            except Exception:
                pass

    page.on("response", capture)
    page.goto(f"{BASE_URL}/agent/chat", wait_until="networkidle")
    target = next((item for item in accounts if item.get("id") == ACCOUNT_REF), None)
    if target is None:
        raise RuntimeError(f"Account {ACCOUNT_REF} was not available in the UI account list")
    page.locator(".header-controls .el-select").click()
    option = page.locator(".el-select-dropdown__item").filter(has_text=target["account_name"])
    option.last.click()
    page.wait_for_timeout(300)
    return target["account_name"]


def run_case(page, case_id, text):
    responses = []

    def capture(response):
        if "/api/agent/turns" in response.url and response.request.method == "POST":
            try:
                responses.append(response.json())
            except Exception:
                pass

    page.on("response", capture)
    before = page.locator("article.message.assistant").count()
    composer = page.locator(".composer .el-textarea__inner").first
    composer.fill(text)
    page.locator(".composer-tools .el-button--primary").click()
    try:
        page.wait_for_function(
            "count => document.querySelectorAll('article.message.assistant').length > count || !!document.querySelector('.technical-details')",
            arg=before,
            timeout=40_000,
        )
    except Exception:
        pass
    page.wait_for_timeout(300)
    assistant = page.locator("article.message.assistant .message-content > p")
    message = assistant.last.inner_text() if assistant.count() else ""
    payload = responses[-1] if responses else None
    turn = ((payload or {}).get("data") or payload or {}).get("turn", {})
    return {
        "case_id": case_id,
        "input": text,
        "visible_message": message,
        "intent": turn.get("intent"),
        "action": turn.get("action"),
        "status": turn.get("status"),
        "run_ref": turn.get("run_ref"),
        "warnings": turn.get("warnings", []),
        "pending_required_fields": (turn.get("pending_interaction") or {}).get("required_fields", []),
        "network_response_captured": payload is not None,
    }


if __name__ == "__main__":
    main()
