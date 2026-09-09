from app.crawler.providers.base import BaseCrawlerProvider
from app.models.crawl_task import CrawlTask
from app.schemas.crawler_collection import (
    CompetitorAccountCreate,
    CompetitorCommentCreate,
    CompetitorNoteCreate,
    CrawlerProviderResult,
)


class SeedSampleProvider(BaseCrawlerProvider):
    """Seed 样本 Provider，用于无真实数据时跑通流程。"""

    name = "seed_sample"

    def collect(self, task: CrawlTask) -> CrawlerProviderResult:
        """根据关键词生成可测试的同行账号、笔记和评论样本。"""
        keyword = task.keyword or task.input_payload.get("keyword") or "AI Agent"
        account = CompetitorAccountCreate(
            account_id=task.account_id,
            platform_account_id=f"seed_{task.id}_creator",
            nickname=f"{keyword} 项目学姐",
            homepage_url=f"https://www.xiaohongshu.com/user/profile/seed-{task.id}",
            bio=f"专注分享 {keyword} 学习路线、项目实战和求职经验。",
            follower_count=18000,
            note_count=96,
            source_type="SEED_SAMPLE",
            confidence=0.86,
            raw_snapshot={"provider": self.name, "keyword": keyword, "sample_type": "competitor_account"},
        )
        notes = [
            self._build_note(task, keyword, index, title, collect_count)
            for index, title, collect_count in [
                (1, f"普通大学生怎么做 {keyword} 项目，别先学复杂框架", 620),
                (2, f"{keyword} 学习路线：从 API 调用到业务闭环", 540),
                (3, f"能写进简历的 {keyword} 项目应该长什么样", 710),
            ]
        ]
        comments = [
            self._build_comment(task, index, content)
            for index, content in [
                (1, "这个路线比我之前看的框架教程清楚多了，适合先收藏。"),
                (2, "想看完整项目结构，尤其是后端和模型调用怎么拆。"),
                (3, "普通本科能做这个当简历项目吗？需要学到什么程度？"),
            ]
        ]
        return CrawlerProviderResult(accounts=[account], notes=notes, comments=comments, provider_name=self.name, source_type="SEED_SAMPLE", is_mock=True, confidence=0.86)

    def _build_note(self, task: CrawlTask, keyword: str, index: int, title: str, collect_count: int) -> CompetitorNoteCreate:
        """构造 Seed 竞品笔记样本。"""
        return CompetitorNoteCreate(
            account_id=task.account_id,
            note_id=f"seed-note-{task.id}-{index}",
            note_url=f"https://www.xiaohongshu.com/explore/seed-note-{task.id}-{index}",
            author_name=f"{keyword} 项目学姐",
            title=title,
            content=f"围绕 {keyword} 的学习顺序、项目拆解和求职表达做图文说明。",
            tags=[keyword, "项目实战", "大学生求职", "学习路线"],
            like_count=collect_count + 420,
            collect_count=collect_count,
            comment_count=80 + index * 9,
            source_type="SEED_SAMPLE",
            provider_name=self.name,
            is_mock=True,
            confidence=0.84,
            raw_snapshot={"provider": self.name, "keyword": keyword, "sample_type": "competitor_note", "index": index},
        )

    def _build_comment(self, task: CrawlTask, index: int, content: str) -> CompetitorCommentCreate:
        """构造 Seed 评论样本。"""
        return CompetitorCommentCreate(
            account_id=task.account_id,
            comment_id=f"seed-comment-{task.id}-{index}",
            user_name=f"种子用户{index}",
            content=content,
            like_count=12 + index,
            source_type="SEED_SAMPLE",
            provider_name=self.name,
            is_mock=True,
            confidence=0.82,
            raw_snapshot={"provider": self.name, "sample_type": "competitor_comment", "index": index},
        )
