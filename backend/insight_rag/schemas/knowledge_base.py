from datetime import datetime

from pydantic import BaseModel, ConfigDict


class KnowledgeBaseCreate(BaseModel):
    name: str
    description: str | None = None
    chunk_size: int = 800
    chunk_overlap: int = 120


class KnowledgeBaseUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    chunk_size: int | None = None
    chunk_overlap: int | None = None


class KnowledgeBaseOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: str | None
    chunk_size: int
    chunk_overlap: int
    created_at: datetime
    updated_at: datetime
