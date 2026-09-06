import re
from urllib.parse import urlparse

from app.schemas.xhs_note import XhsNoteUrlParseResult


NOTE_ID_PATTERN = re.compile(r"/(?:explore|discovery/item)/([0-9a-zA-Z]+)")


def parse_xhs_note_url(note_url: str) -> XhsNoteUrlParseResult:
    """解析小红书笔记 URL，提取 note_id。"""

    parsed = urlparse(note_url)
    if "xiaohongshu.com" not in parsed.netloc and "xhslink.com" not in parsed.netloc:
        return XhsNoteUrlParseResult(note_url=note_url, note_id=None, valid=False, reason="不是小红书链接")

    match = NOTE_ID_PATTERN.search(parsed.path)
    note_id = match.group(1) if match else None
    return XhsNoteUrlParseResult(note_url=note_url, note_id=note_id, valid=True, reason=None)