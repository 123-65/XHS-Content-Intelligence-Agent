from app.crawler.provider import XhsCrawlerProvider
from app.crawler.xhs_url import parse_xhs_note_url
from app.schemas.xhs_note import XhsNoteCrawlResult


class MockXhsCrawlerProvider(XhsCrawlerProvider):
    """小红书 Mock 采集器，用于前端演示和接口联调。"""

    def crawl_note(
        self,
        note_url: str,
        source_type: str = "MANUAL_LINK",
        keyword: str | None = None,
    ) -> XhsNoteCrawlResult:
        """模拟采集单篇小红书公开笔记。"""
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

        title = "普通大学生怎么做 AI Agent 项目，别一上来就学复杂框架"
        content = "这是一篇模拟采集到的小红书笔记正文，用来演示竞品内容采集、入库和后续分析流程。"
        tags = ["AI学习", "AI Agent", "项目实战", "大学生求职"]
        image_ocr_text = "第1张图：AI Agent 学习路线。第2张图：先学 OpenAI SDK，再学工具调用，最后做 Workflow。"

        merged_text = "\n".join(
            [
                title,
                content,
                " ".join(tags),
                image_ocr_text,
            ]
        )

        return XhsNoteCrawlResult(
            source_type=source_type,
            keyword=keyword,
            note_url=note_url,
            note_id=parse_result.note_id,
            author_name="模拟竞品博主",
            author_homepage="https://www.xiaohongshu.com/user/profile/mock",
            title=title,
            content=content,
            tags=tags,
            content_type="IMAGE_TEXT",
            cover_url="https://example.com/mock-cover.jpg",
            image_urls=[
                "https://example.com/mock-image-1.jpg",
                "https://example.com/mock-image-2.jpg",
            ],
            image_count=2,
            image_ocr_text=image_ocr_text,
            image_ocr_items=[
                {"index": 1, "text": "AI Agent 学习路线", "confidence": 0.98},
                {"index": 2, "text": "先学 SDK，再学工具调用，再做 Workflow", "confidence": 0.95},
            ],
            merged_text=merged_text,
            like_count=1280,
            collect_count=620,
            comment_count=89,
            status="SUCCESS",
        )