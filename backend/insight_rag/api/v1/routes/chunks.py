from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from insight_rag.core.db import get_db
from insight_rag.models.chunk import Chunk
from insight_rag.schemas.document import ChunkOut

router = APIRouter()


@router.get("", response_model=list[ChunkOut])
def list_chunks(
    knowledge_base_id: int | None = None,
    document_id: int | None = None,
    limit: int = 100,
    db: Session = Depends(get_db),
):
    query = db.query(Chunk)
    if knowledge_base_id:
        query = query.filter(Chunk.knowledge_base_id == knowledge_base_id)
    if document_id:
        query = query.filter(Chunk.document_id == document_id)
    return query.order_by(Chunk.created_at.desc()).limit(min(limit, 500)).all()

