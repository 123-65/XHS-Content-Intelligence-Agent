import json
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from insight_rag.core.db import SessionLocal, get_db
from insight_rag.models.chat import ChatMessageRecord, ChatSession
from insight_rag.models.knowledge_base import KnowledgeBase
from insight_rag.schemas.chat import ChatMessageOut, ChatRequest, ChatSessionCreate, ChatSessionOut, ChatSessionUpdate
from insight_rag.services.llm import stream_chat_completion
from insight_rag.services.multimodal_retrieval_service import retrieve_multimodal_chunks
from insight_rag.services.rag_graph import rag_graph

router = APIRouter()


def sse(event: str, data) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def _session_title(question: str) -> str:
    title = question.strip().replace("\n", " ")
    return title[:48] or "新对话"


@router.get("/sessions", response_model=list[ChatSessionOut])
def list_sessions(knowledge_base_id: int | None = None, db: Session = Depends(get_db)):
    query = db.query(ChatSession)
    if knowledge_base_id:
        query = query.filter(ChatSession.knowledge_base_id == knowledge_base_id)
    return query.order_by(ChatSession.updated_at.desc()).all()


@router.post("/sessions", response_model=ChatSessionOut)
def create_session(payload: ChatSessionCreate, db: Session = Depends(get_db)):
    kb = db.get(KnowledgeBase, payload.knowledge_base_id)
    if not kb:
        raise HTTPException(status_code=404, detail="Knowledge base not found")
    session = ChatSession(knowledge_base_id=payload.knowledge_base_id, title=payload.title or "新对话")
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


@router.put("/sessions/{session_id}", response_model=ChatSessionOut)
def update_session(session_id: int, payload: ChatSessionUpdate, db: Session = Depends(get_db)):
    session = db.get(ChatSession, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Chat session not found")
    session.title = payload.title.strip() or session.title
    session.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(session)
    return session


@router.get("/sessions/{session_id}")
def get_session(session_id: int, db: Session = Depends(get_db)):
    session = db.get(ChatSession, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Chat session not found")
    messages = (
        db.query(ChatMessageRecord)
        .filter(ChatMessageRecord.session_id == session_id)
        .order_by(ChatMessageRecord.created_at.asc(), ChatMessageRecord.id.asc())
        .all()
    )
    return {
        "session": ChatSessionOut.model_validate(session),
        "messages": [ChatMessageOut.model_validate(message) for message in messages],
    }


@router.delete("/sessions/{session_id}")
def delete_session(session_id: int, db: Session = Depends(get_db)):
    session = db.get(ChatSession, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Chat session not found")
    db.delete(session)
    db.commit()
    return {"message": "deleted"}


@router.post("/stream")
async def chat_stream(payload: ChatRequest):
    async def generator():
        db = SessionLocal()
        try:
            kb = db.get(KnowledgeBase, payload.knowledge_base_id)
            if not kb:
                yield sse("error", {"message": "Knowledge base not found"})
                return

            session = db.get(ChatSession, payload.session_id) if payload.session_id else None
            if session and session.knowledge_base_id != payload.knowledge_base_id:
                yield sse("error", {"message": "Chat session does not belong to selected knowledge base"})
                return
            if not session:
                session = ChatSession(
                    knowledge_base_id=payload.knowledge_base_id,
                    title=_session_title(payload.question),
                )
                db.add(session)
                db.commit()
                db.refresh(session)

            history_records = (
                db.query(ChatMessageRecord)
                .filter(ChatMessageRecord.session_id == session.id)
                .order_by(ChatMessageRecord.created_at.desc(), ChatMessageRecord.id.desc())
                .limit(10)
                .all()
            )
            history_messages = [
                {"role": record.role, "content": record.content}
                for record in reversed(history_records)
                if record.role in {"user", "assistant"}
            ]

            db.add(ChatMessageRecord(session_id=session.id, role="user", content=payload.question, sources=[]))
            session.updated_at = datetime.now(timezone.utc)
            db.commit()
            yield sse("session", {"id": session.id, "title": session.title, "knowledge_base_id": session.knowledge_base_id})
            yield sse("stage", {"name": "rewrite_query"})
            graph_result = await rag_graph.ainvoke(
                {
                    "knowledge_base_id": payload.knowledge_base_id,
                    "question": payload.question,
                    "rewritten_query": payload.question,
                    "top_k": payload.top_k,
                    "rerank": payload.rerank,
                    "retrieval_mode": payload.retrieval_mode,
                    "db": db,
                    "hits": [],
                    "answer": "",
                    "answer_messages": [],
                }
            )
            hits = graph_result["hits"]
            sources = [hit.model_dump() for hit in hits]
            yield sse("sources", sources)
            messages = graph_result["answer_messages"]
            if history_messages and messages:
                messages = [messages[0], *history_messages, *messages[1:]]

            yield sse("stage", {"name": "generate_answer"})
            answer = ""
            async for token in stream_chat_completion(messages):
                answer += token
                yield sse("token", token)
            db.add(ChatMessageRecord(session_id=session.id, role="assistant", content=answer, sources=sources))
            session.updated_at = datetime.now(timezone.utc)
            db.commit()
            yield sse("done", {"ok": True})
        except Exception as exc:
            db.rollback()
            yield sse("error", {"message": str(exc)})
        finally:
            db.close()

    return StreamingResponse(generator(), media_type="text/event-stream")


@router.post("/stream/simple")
async def chat_stream_simple(payload: ChatRequest):
    db = SessionLocal()
    try:
        hits = await retrieve_multimodal_chunks(db, payload.knowledge_base_id, payload.question, payload.top_k, rerank=payload.rerank)
        return {"sources": hits}
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    finally:
        db.close()

