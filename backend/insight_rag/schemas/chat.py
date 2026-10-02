from datetime import datetime

from pydantic import BaseModel
from pydantic import ConfigDict


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    knowledge_base_id: int
    question: str
    session_id: int | None = None
    history: list[ChatMessage] = []
    top_k: int = 5
    rerank: bool = False
    retrieval_mode: str = "hybrid"


class ChatSessionCreate(BaseModel):
    knowledge_base_id: int
    title: str | None = None


class ChatSessionUpdate(BaseModel):
    title: str


class ChatSessionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    knowledge_base_id: int
    title: str
    created_at: datetime
    updated_at: datetime


class ChatMessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    session_id: int
    role: str
    content: str
    sources: list
    created_at: datetime


class SearchDebugRequest(BaseModel):
    knowledge_base_id: int
    query: str
    top_k: int = 5
    rerank: bool = True
    retrieval_mode: str = "hybrid"


class SearchHit(BaseModel):
    chunk_id: int
    document_id: int
    knowledge_base_id: int
    content: str
    metadata: dict
    score: float | None = None
    dense_score: float | None = None
    bm25_score: float | None = None
    retrieval_mode: str = "hybrid"
