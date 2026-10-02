from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from insight_rag.core.db import get_db
from insight_rag.schemas.chat import SearchDebugRequest, SearchHit
from insight_rag.services.retrieval_service import retrieve_chunks

router = APIRouter()


@router.post("/debug", response_model=list[SearchHit])
async def search_debug(payload: SearchDebugRequest, db: Session = Depends(get_db)):
    try:
        return await retrieve_chunks(db, payload.knowledge_base_id, payload.query, payload.top_k, rerank=payload.rerank)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

