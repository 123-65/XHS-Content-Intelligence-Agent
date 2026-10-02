from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from insight_rag.core.config import settings
from insight_rag.core.db import get_db
from insight_rag.models.chunk import Chunk
from insight_rag.models.document import Document
from insight_rag.models.knowledge_base import KnowledgeBase
from insight_rag.models.multimodal_asset import MultimodalAsset
from insight_rag.services.vector_store import health_check as vector_health_check

router = APIRouter()


@router.get("/health")
def health():
    return {"status": "ok"}


@router.get("/health/db")
def health_db(db: Session = Depends(get_db)):
    try:
        db.execute(text("SELECT 1"))
        return {"status": "ok", "database": "postgresql"}
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"PostgreSQL unavailable: {exc}") from exc


@router.get("/health/vector")
def health_vector():
    result = vector_health_check()
    if result.get("status") != "ok":
        raise HTTPException(status_code=503, detail=result)
    return {"status": "ok", "vector_store": "milvus", **result}


@router.get("/diagnostics")
def diagnostics(db: Session = Depends(get_db)):
    vector = vector_health_check()
    counts = {
        "knowledge_bases": db.query(KnowledgeBase).count(),
        "documents": db.query(Document).count(),
        "chunks": db.query(Chunk).count(),
        "multimodal_assets": db.query(MultimodalAsset).count(),
    }
    recent_documents = (
        db.query(Document)
        .order_by(Document.updated_at.desc(), Document.id.desc())
        .limit(5)
        .all()
    )
    return {
        "status": "ok",
        "environment": settings.env,
        "llm": {
            "provider": settings.active_provider,
            "api_key_configured": settings.active_api_key_configured,
            "base_url": settings.active_base_url,
            "chat_model": settings.active_chat_model,
            "embedding_model": settings.active_embedding_model,
            "embedding_dim": settings.active_embedding_dim,
            "qwen_vl_model": settings.qwen_vl_model,
            "qwen_ocr_model": settings.qwen_ocr_model,
        },
        "storage": {
            "provider": settings.storage_provider,
            "prefix": settings.storage_prefix,
            "oss_endpoint_configured": bool(settings.oss_endpoint and settings.oss_endpoint != "replace-me"),
            "oss_bucket": settings.oss_bucket,
            "minio_endpoint": settings.minio_endpoint,
        },
        "database": {"status": "ok", "url_driver": settings.database_url.split("://", 1)[0], "counts": counts},
        "vector": vector,
        "recent_documents": [
            {
                "id": doc.id,
                "filename": doc.filename,
                "status": doc.status,
                "error_message": doc.error_message,
                "updated_at": doc.updated_at.isoformat() if doc.updated_at else None,
            }
            for doc in recent_documents
        ],
    }

