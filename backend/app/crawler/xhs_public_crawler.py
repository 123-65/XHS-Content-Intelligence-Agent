import re

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright

from app.core.config import settings
from app.crawler.xhs_url import parse_xhs_note_url
from app.schemas.xhs_note import XhsNoteCrawlResult
from app.crawler.provider import XhsCrawlerProvider


def parse_count(value: str | None) -> int | None:
    """解析小红书页面中的点赞、收藏、评论数字。"""
    if not value:
        return None
    text = value.strip().replace(",", "")
    if not text:
        return None
    match = re.search(r"(\d+(?:\.\d+)?)(万|w|W)?", text)
    if not match:
        return None
    number = float(match.group(1))
    unit = match.group(2)
    if unit in {"万", "w", "W"}:
        number *= 10000
    return int(number)


class XhsPublicCrawler(XhsCrawlerProvider):
    """小红书公开网页轻量采集器。"""

    def crawl_note(self, note_url: str, source_type: str = "MANUAL_LINK", keyword: str | None = None) -> XhsNoteCrawlResult:
        """采集单篇公开笔记页面。"""
        parse_result = parse_xhs_note_url(note_url)
        if not parse_result.valid:
            return XhsNoteCrawlResult(
                source_type=source_type,
                keyword=keyword,
                note_url=note_url,
                note_id=None,
                status="FAILED",
                error_message=parse_result.reason or "无效的小红书链接",
            )

        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=settings.crawler_headless)
                page = browser.new_page()
                page.goto(note_url, wait_until="domcontentloaded", timeout=settings.crawler_timeout_ms)
                page.wait_for_timeout(3000)

                data = page.evaluate(
                    """
                    () => {
                        const pick = (selectors) => {
                            for (const selector of selectors) {
                                const el = document.querySelector(selector);
                                if (el && el.innerText && el.innerText.trim()) return el.innerText.trim();
                                if (el && el.content && el.content.trim()) return el.content.trim();
                            }
                            return null;
                        };

                        const meta = (name) => {
                            const el = document.querySelector(`meta[property="${name}"], meta[name="${name}"]`);
                            return el ? el.content : null;
                        };

                        const images = Array.from(document.querySelectorAll("img"))
                            .map(img => img.src)
                            .filter(src => src && src.startsWith("http"))
                            .filter((src, index, arr) => arr.indexOf(src) === index);

                        const links = Array.from(document.querySelectorAll("a"))
                            .map(a => ({ text: a.innerText || "", href: a.href || "" }));

                        const bodyText = document.body ? document.body.innerText : "";

                        return {
                            title: meta("og:title") || document.title || pick([".title", "[class*=title]"]),
                            description: meta("description") || meta("og:description"),
                            bodyText,
                            images,
                            links,
                        };
                    }
                    """
                )

                browser.close()

            return self._normalize_result(
                note_url=note_url,
                note_id=parse_result.note_id,
                source_type=source_type,
                keyword=keyword,
                page_data=data,
            )
        except PlaywrightTimeoutError:
            return XhsNoteCrawlResult(
                source_type=source_type,
                keyword=keyword,
                note_url=note_url,
                note_id=parse_result.note_id,
                status="FAILED",
                error_message="页面加载超时",
            )
        except Exception as exc:
            return XhsNoteCrawlResult(
                source_type=source_type,
                keyword=keyword,
                note_url=note_url,
                note_id=parse_result.note_id,
                status="FAILED",
                error_message=f"采集失败：{exc}",
            )

    def _normalize_result(
        self,
        note_url: str,
        note_id: str | None,
        source_type: str,
        keyword: str | None,
        page_data: dict,
    ) -> XhsNoteCrawlResult:
        """将页面数据标准化为项目内部采集结果。"""
        title = self._clean_title(page_data.get("title"))
        content = page_data.get("description")
        body_text = page_data.get("bodyText") or ""
        image_urls = page_data.get("images") or []
        tags = self._extract_tags(body_text)
        like_count = self._extract_metric(body_text, ["点赞", "赞"])
        collect_count = self._extract_metric(body_text, ["收藏"])
        comment_count = self._extract_metric(body_text, ["评论"])

        merged_text = self._build_merged_text(title=title, content=content, tags=tags, image_ocr_text=None)
        return XhsNoteCrawlResult(
            source_type=source_type,
            keyword=keyword,
            note_url=note_url,
            note_id=note_id,
            title=title,
            content=content,
            tags=tags,
            content_type="IMAGE_TEXT" if image_urls else "TEXT_ONLY",
            cover_url=image_urls[0] if image_urls else None,
            image_urls=image_urls,
            image_count=len(image_urls),
            merged_text=merged_text,
            like_count=like_count,
            collect_count=collect_count,
            comment_count=comment_count,
            status="SUCCESS",
        )

    def _clean_title(self, title: str | None) -> str | None:
        """清洗网页标题。"""
        if not title:
            return None
        return title.replace(" - 小红书", "").replace("小红书", "").strip(" -_")

    def _extract_tags(self, text: str) -> list[str]:
        """从页面文本中提取话题标签。"""
        tags = re.findall(r"#([\u4e00-\u9fa5A-Za-z0-9_\-]+)", text)
        return list(dict.fromkeys(tags))[:20]

    def _extract_metric(self, text: str, names: list[str]) -> int | None:
        """从页面文本中尽力提取公开互动指标。"""
        for name in names:
            patterns = [
                rf"{name}\\s*(\\d+(?:\\.\\d+)?\\s*(?:万|w|W)?)",
                rf"(\\d+(?:\\.\\d+)?\\s*(?:万|w|W)?)\\s*{name}",
            ]
            for pattern in patterns:
                match = re.search(pattern, text)
                if match:
                    return parse_count(match.group(1))
        return None

    def _build_merged_text(
        self,
        title: str | None,
        content: str | None,
        tags: list[str],
        image_ocr_text: str | None,
    ) -> str:
        """合并标题、正文、标签和 OCR 文本。"""
        parts = [
            title or "",
            content or "",
            " ".join(tags),
            image_ocr_text or "",
        ]
        return "\n".join([part for part in parts if part.strip()])
