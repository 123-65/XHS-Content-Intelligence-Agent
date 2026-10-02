from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
import logging

from insight_rag.core.db import get_db
from insight_rag.models.knowledge_base import KnowledgeBase
from insight_rag.schemas.knowledge_base import KnowledgeBaseCreate, KnowledgeBaseOut, KnowledgeBaseUpdate

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("", response_model=list[KnowledgeBaseOut])
def list_knowledge_bases(db: Session = Depends(get_db)):
    return db.query(KnowledgeBase).order_by(KnowledgeBase.created_at.desc()).all()


@router.post("", response_model=KnowledgeBaseOut)
def create_knowledge_base(payload: KnowledgeBaseCreate, db: Session = Depends(get_db)):
    if payload.chunk_overlap >= payload.chunk_size:
        raise HTTPException(status_code=400, detail="chunk_overlap must be smaller than chunk_size")
    try:
        item = KnowledgeBase(**payload.model_dump())
        db.add(item)
        db.commit()
        db.refresh(item)
        logger.info("knowledge_base.create.done id=%s name=%s", item.id, item.name)
        return item
    except Exception as exc:
        db.rollback()
        logger.exception("knowledge_base.create.failed name=%s", payload.name)
        raise HTTPException(status_code=400, detail=f"create knowledge base failed: {exc}") from exc


@router.get("/{knowledge_base_id}", response_model=KnowledgeBaseOut)
def get_knowledge_base(knowledge_base_id: int, db: Session = Depends(get_db)):
    item = db.get(KnowledgeBase, knowledge_base_id)
    if not item:
        raise HTTPException(status_code=404, detail="Knowledge base not found")
    return item


@router.put("/{knowledge_base_id}", response_model=KnowledgeBaseOut)
def update_knowledge_base(knowledge_base_id: int, payload: KnowledgeBaseUpdate, db: Session = Depends(get_db)):
    item = db.get(KnowledgeBase, knowledge_base_id)
    if not item:
        raise HTTPException(status_code=404, detail="Knowledge base not found")
    data = payload.model_dump(exclude_unset=True)
    chunk_size = data.get("chunk_size", item.chunk_size)
    chunk_overlap = data.get("chunk_overlap", item.chunk_overlap)
    if chunk_overlap >= chunk_size:
        raise HTTPException(status_code=400, detail="chunk_overlap must be smaller than chunk_size")
    try:
        for key, value in data.items():
            setattr(item, key, value)
        db.commit()
        db.refresh(item)
        logger.info("knowledge_base.update.done id=%s name=%s", item.id, item.name)
        return item
    except Exception as exc:
        db.rollback()
        logger.exception("knowledge_base.update.failed id=%s", knowledge_base_id)
        raise HTTPException(status_code=400, detail=f"update knowledge base failed: {exc}") from exc


@router.delete("/{knowledge_base_id}")
def delete_knowledge_base(knowledge_base_id: int, db: Session = Depends(get_db)):
    item = db.get(KnowledgeBase, knowledge_base_id)
    if not item:
        raise HTTPException(status_code=404, detail="Knowledge base not found")
    db.delete(item)
    db.commit()
    return {"message": "deleted"}

