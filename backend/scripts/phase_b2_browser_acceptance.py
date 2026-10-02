"""Phase B2 headed Edge acceptance. All business turns are submitted through the visible UI."""

import hashlib
import json
import re
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright


BASE_URL = "http://127.0.0.1:5173"
ACCOUNT_REF = 8456
URL_FILE = Path(__file__).parents[2].parent / "xhs链接.md"


def authorized_urls() -> tuple[list[str], list[str]]:
    text = URL_FILE.read_text(encoding="utf-8")
    profiles = list(dict.fromkeys(re.findall(r"https://www\.xiaohongshu\.com/user/profile/[^\s<>\"']+", text)))[:3]
    notes = list(dict.fromkeys(re.findall(r"https://www\.xiaohongshu\.com/(?:explore|discovery/item)/[^\s<>\"']+", text)))
    return profiles, notes


def redacted_input(text: str) -> str:
    text = re.sub(r"https://www\.xiaohongshu\.com/user/profile/[^\s<>\"']+", "<AUTHORIZED_PROFILE_URL>", text)
    return re.sub(r"https://www\.xiaohongshu\.com/(?:explore|discovery/item)/[^\s<>\"']+", "<AUTHORIZED_NOTE_URL>", text)


def select_account(page):
    accounts = []

    def capture(response):
        if response.url.rstrip("/").endswith("/accounts") and response.request.method == "GET":
            try:
                accounts.extend(response.json().get("data", []))
            except Exception:
                pass

    page.on("response", capture)
    page.goto(f"{BASE_URL}/agent/chat", wait_until="networkidle")
    target = next(item for item in accounts if item.get("id") == ACCOUNT_REF)
    page.locator(".header-controls .el-select").click()
    page.locator(".el-select-dropdown__item").filter(has_text=target["account_name"]).last.click()
    page.wait_for_timeout(300)
    return target["account_name"]


def fresh(page):
    page.evaluate("localStorage.clear()")
    select_account(page)


def choose_first(page, list_path: str, selector: str):
    page.goto(f"{BASE_URL}{list_path}", wait_until="networkidle")
    page.locator(".asset-row").first.click()
    page.wait_for_load_state("networkidle")
    page.locator(selector).first.click()
    page.wait_for_url("**/agent/chat**")


def run_case(page, case_id: str, text: str, timeout_ms: int = 190_000, materials: dict | None = None):
    responses = []
    request_materials = []

    def capture(response):
        if "/api/agent/turns" not in response.url or response.request.method != "POST":
            return
        try:
            payload = response.request.post_data_json or {}
            request_materials.append(payload.get("materials", {}))
            responses.append(response.json())
        except Exception:
            pass

    page.on("response", capture)
    before = page.locator("article.message.assistant").count()
    started = time.monotonic()
    if materials:
        if not page.locator(".materials").count():
            page.get_by_role("button", name="＋ 添加材料").click()
        page.locator(".material-field").nth(0).locator("textarea").fill("\n".join(materials.get("note_urls", [])))
        page.locator(".material-field").nth(1).locator("textarea").fill("\n".join(materials.get("profile_urls", [])))
    page.locator(".composer .el-textarea__inner").first.fill(text)
    page.locator(".composer-tools .el-button--primary").click()
    try:
        page.wait_for_function(
            "count => document.querySelectorAll('article.message.assistant').length > count || !!document.querySelector('.technical-details')",
            arg=before,
            timeout=timeout_ms,
        )
    except Exception:
        pass
    page.wait_for_timeout(500)
    elapsed = round(time.monotonic() - started, 3)
    assistant = page.locator("article.message.assistant .message-content > p")
    visible = assistant.last.inner_text() if assistant.count() else ""
    payload = responses[-1] if responses else None
    turn = ((payload or {}).get("data") or payload or {}).get("turn", {})
    materials = request_materials[-1] if request_materials else {}
    return {
        "case_id": case_id,
        "input": redacted_input(text),
        "input_sha256": hashlib.sha256(text.encode()).hexdigest(),
        "visible_message": visible,
        "intent": turn.get("intent"),
        "action": turn.get("action"),
        "status": turn.get("status"),
        "run_ref": turn.get("run_ref"),
        "artifacts": turn.get("artifacts", []),
        "error": turn.get("error"),
        "request_material_counts": {
            "profile_urls": len(materials.get("profile_urls", [])),
            "note_urls": len(materials.get("note_urls", [])),
        },
        "network_response_captured": payload is not None,
        "elapsed_seconds": elapsed,
    }


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    selected = set(sys.argv[1:])
    profiles, notes = authorized_urls()
    if len(profiles) != 3 or not notes:
        raise RuntimeError("xhs链接.md must contain three authorized Profile URLs and at least one Note URL")
    results = []
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="msedge", headless=False)
        page = browser.new_page(viewport={"width": 1440, "height": 1000})
        account_name = select_account(page)

        research_cases = {
            "R01": (f"分析这个同行账号\n{profiles[0]}", None),
            "R02": (f"分析这篇为什么表现好\n{notes[0]}", None),
            "B01": (f"分析这个账号：{profiles[0]}", None),
            "D01": (f"研究这个小红书账号：\n{profiles[0]}", None),
            "D02": (f"分析这篇：\n{notes[0]}", None),
            "D03": ("比较这三个账号", {"profile_urls": profiles}),
            "E01": (f"研究这个小红书账号，分析：\n1. 账号定位\n2. 内容方向\n3. 目标人群\n4. 内容特点\n5. 可借鉴点\n\n{profiles[0]}", None),
            "E02": (f"分析这篇笔记：\n标题为什么有效？\n内容结构是什么？\n用户需求是什么？\n点赞收藏评论表现如何？\n\n{notes[0]}", None),
        }
        for case_id, (text, materials) in research_cases.items():
            if selected and case_id not in selected:
                continue
            fresh(page)
            results.append(run_case(page, case_id, text, 190_000, materials=materials))

        if not selected or "R03" in selected:
            fresh(page)
            first = run_case(page, "R03-1", "帮我研究一个同行账号", 60_000)
            second = run_case(
                page,
                "R03-2",
                "采集这个同行账号",
                190_000,
                materials={"profile_urls": [profiles[0]]},
            )
            results.append({"case_id": "R03", "turns": [first, second]})

        for case_id, text in (("B03", "根据刚才研究做下一阶段内容策略"), ("G01", "基于刚才的研究，制定下一阶段内容策略。")):
            if selected and case_id not in selected:
                continue
            fresh(page)
            choose_first(page, "/agent/research", ".actions .el-button--primary")
            results.append(run_case(page, case_id, text))

        for case_id, text in (("B04", "根据这个内容机会写一篇小红书"), ("H01", "根据刚才的策略和内容机会写一篇小红书。")):
            if selected and case_id not in selected:
                continue
            fresh(page)
            choose_first(page, "/agent/strategy", ".opportunity .el-button--primary")
            results.append(run_case(page, case_id, text))

        for case_id, text in (("B06", "复盘一下刚发布的这篇"), ("N05", "复盘一下这篇。")):
            if selected and case_id not in selected:
                continue
            fresh(page)
            page.goto(f"{BASE_URL}/agent/publication/592", wait_until="networkidle")
            page.get_by_role("button", name="开始复盘").click()
            page.wait_for_url("**/agent/chat**")
            results.append(run_case(page, case_id, text))

        if not selected or "CHAIN-01" in selected:
            fresh(page)
            chain = [run_case(page, "CHAIN-01-RESEARCH", f"分析这篇为什么表现好\n{notes[0]}")]
            chain.append(run_case(page, "CHAIN-01-STRATEGY", "根据刚才研究制定内容策略"))
            chain.append(run_case(page, "CHAIN-01-DRAFT", "根据第一个选题写一篇"))
            results.append({"case_id": "CHAIN-01", "turns": chain})

        browser.close()
    print(json.dumps({
        "browser": "Microsoft Edge (Playwright channel=msedge, headed)",
        "account_ref": ACCOUNT_REF,
        "account_name": account_name,
        "authorized_profile_count": len(profiles),
        "authorized_note_count": len(notes),
        "cases": results,
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
