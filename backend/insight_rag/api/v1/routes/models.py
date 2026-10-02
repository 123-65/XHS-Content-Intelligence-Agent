from fastapi import APIRouter

from insight_rag.core.config import settings

router = APIRouter()


@router.get("/models")
def get_models():
    return {
        "provider": settings.active_provider,
        "base_url": settings.active_base_url,
        "chat_model": settings.active_chat_model,
        "embedding_model": settings.active_embedding_model,
        "embedding_dim": settings.active_embedding_dim,
        "api_key_configured": settings.active_api_key_configured,
        "milvus_collection": settings.active_milvus_collection,
        "providers": {
            "qwen": {
                "base_url": settings.qwen_base_url,
                "chat_model": settings.qwen_chat_model,
                "embedding_model": settings.qwen_embedding_model,
                "embedding_dim": settings.qwen_embedding_dim,
            },
            "openai": {
                "base_url": settings.openai_base_url,
                "chat_model": settings.chat_model,
                "embedding_model": settings.embedding_model,
                "embedding_dim": settings.embedding_dim,
            },
        },
    }

