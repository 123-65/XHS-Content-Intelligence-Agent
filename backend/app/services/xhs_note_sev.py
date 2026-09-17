import hashlib

from sqlalchemy.orm import Session

from app.crawler.xhs_url import parse_xhs_note_url
from app.models.xhs_note import XhsNoteSnapshot
from app.repositories.xhs_note_repo import XhsNoteSnapshotRepository
from app.schemas.xhs_note import XhsNoteSnapshotCreate, XhsNoteUrlParseResult


class XhsNoteSnapshotService:
    """小红书笔记快照业务服务。"""

    def __init__(self, db: Session):
        """初始化笔记快照服务。"""
        self.repo = XhsNoteSnapshotRepository(db)

    def parse_url(self, note_url: str) -> XhsNoteUrlParseResult:
        """解析小红书笔记链接。"""
        return parse_xhs_note_url(note_url)

    def create_snapshot(self, data: XhsNoteSnapshotCreate) -> XhsNoteSnapshot:
        """创建笔记快照。"""
        if not data.image_count:
            data.image_count = len(data.image_urls)

        if not data.merged_text:
            data.merged_text = self._build_merged_text(data)

        parse_result = parse_xhs_note_url(data.note_url)
        if not parse_result.valid:
            raise ValueError(parse_result.reason or "无效的小红书链接")

        if not data.note_id:
            data.note_id = parse_result.note_id

        raw_hash = self._build_raw_hash(data)
        return self.repo.create(data, raw_hash=raw_hash)

    def list_snapshots(self, source_type: str | None = None, limit: int = 20) -> list[XhsNoteSnapshot]:
        """查询笔记快照列表。"""
        if source_type:
            return self.repo.list_by_source_type(source_type, limit)
        return self.repo.list_latest(limit)

    def get_snapshot(self, snapshot_id: int) -> XhsNoteSnapshot:
        """查询笔记快照详情。"""
        snapshot = self.repo.get_by_id(snapshot_id)
        if not snapshot:
            raise ValueError("笔记快照不存在")
        return snapshot

#==========================================内部函数=================================================
    def _build_merged_text(self, data: XhsNoteSnapshotCreate) -> str:
        """合并标题、正文、标签和图片 OCR 文本，生成分析文本。"""
        parts = [
            data.title or "",
            data.content or "",
            " ".join(data.tags),
            data.image_ocr_text or "",
        ]
        return "\n".join([part for part in parts if part.strip()])

    def _build_raw_hash(self, data: XhsNoteSnapshotCreate) -> str:
        """根据核心内容生成哈希，用于判断内容是否变化。"""
        raw_text = "|".join([
            data.note_url,
            data.title or "",
            data.content or "",
            ",".join(data.tags),
            ",".join(data.image_urls),
            data.image_ocr_text or "",
        ])
        return hashlib.sha256(raw_text.encode("utf-8")).hexdigest()
