from datetime import datetime

from pydantic import BaseModel, ConfigDict


class DocumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    knowledge_base_id: int
    filename: str
    file_type: str
    status: str
    error_message: str | None
    created_at: datetime
    updated_at: datetime


class ChunkOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    document_id: int
    knowledge_base_id: int
    content: str
    chunk_text: str | None
    chunk_hash: str | None
    chunk_index: int
    page_number: int | None
    heading_path: str | None
    sheet_name: str | None
    row_start: int | None
    row_end: int | None
    source_type: str | None
    token_count: int
    meta: dict
    embedded: bool
    deleted: bool
    created_at: datetime
    updated_at: datetime


class EmbedResponse(BaseModel):
    document_id: int
    embedded_chunks: int
