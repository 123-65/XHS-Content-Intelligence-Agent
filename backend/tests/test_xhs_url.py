from app.crawler.xhs_url import parse_xhs_note_url


def test_parse_xhs_explore_url():
    """测试解析小红书 explore 笔记链接。"""
    result = parse_xhs_note_url("https://www.xiaohongshu.com/explore/65f123456789abcdef123456")
    assert result.valid is True
    assert result.note_id == "65f123456789abcdef123456"


def test_parse_invalid_url():
    """测试非小红书链接。"""
    result = parse_xhs_note_url("https://example.com/test")
    assert result.valid is False
    assert result.note_id is None