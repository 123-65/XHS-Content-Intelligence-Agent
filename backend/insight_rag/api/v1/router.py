from fastapi import APIRouter

from insight_rag.api.v1.routes import chat, chunks, documents, health, knowledge_bases, models, search

api_router = APIRouter()
api_router.include_router(health.router, tags=["health"])
api_router.include_router(models.router, tags=["models"])
api_router.include_router(knowledge_bases.router, prefix="/knowledge-bases", tags=["knowledge-bases"])
api_router.include_router(documents.router, prefix="/documents", tags=["documents"])
api_router.include_router(chunks.router, prefix="/chunks", tags=["chunks"])
api_router.include_router(chat.router, prefix="/chat", tags=["chat"])
api_router.include_router(search.router, prefix="/search", tags=["search"])

