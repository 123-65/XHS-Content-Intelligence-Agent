from fastapi.testclient import TestClient

from app.crawler.xhs_public_crawler import XhsPublicCrawler, parse_count
from app.crawler.mock_provider import MockXhsCrawlerProvider
from app.main import app

def test_parse_count_normal_number():
    """测试普通数字解析。"""
    assert parse_count("123") == 123


def test_parse_count_wan_number():
    """测试万单位数字解析。"""
    assert parse_count("1.2万") == 12000


def test_extract_tags():
    """测试从文本中提取标签。"""
    crawler = XhsPublicCrawler()
    tags = crawler._extract_tags("这是一篇 #AI学习 #AI Agent #项目实战 笔记")
    assert "AI学习" in tags


def test_build_merged_text():
    """测试合并分析文本。"""
    crawler = XhsPublicCrawler()
    text = crawler._build_merged_text(
        title="标题",
        content="正文",
        tags=["AI学习", "项目实战"],
        image_ocr_text="图片里的文字",
    )
    assert "标题" in text
    assert "正文" in text
    assert "AI学习" in text
    assert "图片里的文字" in text

def test_mock_crawler_provider_success():
    """测试 Mock 小红书采集器成功返回笔记数据。"""
    provider = MockXhsCrawlerProvider()
    result = provider.crawl_note(
        note_url="https://www.xiaohongshu.com/explore/65f123456789abcdef123456",
        source_type="COMPETITOR",
        keyword="AI Agent",
    )

    assert result.status == "SUCCESS"
    assert result.source_type == "COMPETITOR"
    assert result.note_id == "65f123456789abcdef123456"
    assert result.title is not None
    assert result.image_count == 2
    assert result.merged_text is not None
    assert "AI Agent" in result.merged_text


def test_mock_crawler_provider_invalid_url():
    """测试 Mock 小红书采集器处理非法链接。"""
    provider = MockXhsCrawlerProvider()
    result = provider.crawl_note(note_url="https://example.com/test")

    assert result.status == "FAILED"
    assert result.note_id is None
    assert result.error_message is not None

client = TestClient(app)


def test_crawl_note_api_success():
    """测试采集单篇笔记接口。"""
    response = client.post(
        "/xhs/notes/crawl",
        params={
            "note_url": "https://www.xiaohongshu.com/explore/65f123456789abcdef123456",
            "source_type": "COMPETITOR",
            "keyword": "AI Agent",
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["code"] == 0
    assert data["data"]["status"] == "SUCCESS"
    assert data["data"]["source_type"] == "COMPETITOR"
    assert data["data"]["image_count"] >= 1
