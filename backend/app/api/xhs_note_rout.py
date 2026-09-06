from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.response import fail, success
from app.schemas.xhs_note import XhsNoteSnapshotCreate, XhsNoteSnapshotResponse
from app.services.xhs_note_sev import XhsNoteSnapshotService

router = APIRouter(prefix="/xhs/notes", tags=["小红书笔记"])


@router.get("/parse-url")
def parse_note_url(note_url: str = Query(...), db: Session = Depends(get_db)):
    """解析小红书笔记链接。"""
    service = XhsNoteSnapshotService(db)
    result = service.parse_url(note_url)
    return success(result.model_dump())


@router.post("/snapshots")
def create_note_snapshot(data: XhsNoteSnapshotCreate, db: Session = Depends(get_db)):
    """手动创建小红书笔记快照。"""
    service = XhsNoteSnapshotService(db)
    try:
        snapshot = service.create_snapshot(data)
        result = XhsNoteSnapshotResponse.model_validate(snapshot).model_dump(mode="json")
        return success(result)
    except ValueError as exc:
        return JSONResponse(status_code=400, content=fail(str(exc), code=400).model_dump())


@router.get("/snapshots")
def list_note_snapshots(
    source_type: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """查询小红书笔记快照列表。"""
    service = XhsNoteSnapshotService(db)
    snapshots = service.list_snapshots(source_type=source_type, limit=limit)
    result = [XhsNoteSnapshotResponse.model_validate(item).model_dump(mode="json") for item in snapshots]
    return success(result)


@router.get("/snapshots/{snapshot_id}")
def get_note_snapshot(snapshot_id: int, db: Session = Depends(get_db)):
    """查询小红书笔记快照详情。"""
    service = XhsNoteSnapshotService(db)
    try:
        snapshot = service.get_snapshot(snapshot_id)
        result = XhsNoteSnapshotResponse.model_validate(snapshot).model_dump(mode="json")
        return success(result)
    except ValueError as exc:
        return JSONResponse(status_code=404, content=fail(str(exc), code=404).model_dump())