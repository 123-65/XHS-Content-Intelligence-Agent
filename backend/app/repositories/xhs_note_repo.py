from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.xhs_note import XhsNoteSnapshot
from app.schemas.xhs_note import XhsNoteSnapshotCreate


class XhsNoteSnapshotRepository:
    """小红书笔记快照数据库访问层。"""

    def __init__(self, db: Session):
        """初始化数据库会话。"""
        self.db = db

    def create(self, data: XhsNoteSnapshotCreate, raw_hash: str | None = None) -> XhsNoteSnapshot:
        """创建笔记快照。"""
        snapshot = XhsNoteSnapshot(**data.model_dump(), raw_hash=raw_hash)
        self.db.add(snapshot)
        self.db.commit()
        self.db.refresh(snapshot)
        return snapshot

    def list_latest(self, limit: int = 20) -> list[XhsNoteSnapshot]:
        """查询最新笔记快照。"""
        stmt = select(XhsNoteSnapshot).order_by(XhsNoteSnapshot.id.desc()).limit(limit)
        return list(self.db.execute(stmt).scalars().all())

    def list_by_source_type(self, source_type: str, limit: int = 20) -> list[XhsNoteSnapshot]:
        """根据来源类型查询笔记快照。"""
        stmt = (
            select(XhsNoteSnapshot)
            .where(XhsNoteSnapshot.source_type == source_type)
            .order_by(XhsNoteSnapshot.id.desc())
            .limit(limit)
        )
        return list(self.db.execute(stmt).scalars().all())

    def get_by_id(self, snapshot_id: int) -> XhsNoteSnapshot | None:
        """根据 ID 查询笔记快照。"""
        return self.db.get(XhsNoteSnapshot, snapshot_id)