from functools import cached_property

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    project_name: str = "InsightRAG Studio"
    env: str = "development"

    database_url: str = "postgresql+psycopg://insightrag:insightrag@localhost:5432/insightrag"
    async_database_url: str = "postgresql://insightrag:insightrag@localhost:5432/insightrag"
    vector_store: str = "milvus"
    milvus_host: str = "localhost"
    milvus_port: int = 19530
    milvus_user: str = ""
    milvus_password: str = ""
    milvus_db_name: str = "default"
    milvus_collection: str = "insightrag_chunks"
    milvus_metric_type: str = "COSINE"
    milvus_index_type: str = "HNSW"

    llm_provider: str = "qwen"

    qwen_base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    qwen_api_key: str = "replace-me"
    qwen_chat_model: str = "qwen-plus"
    qwen_embedding_model: str = "text-embedding-v3"
    qwen_embedding_dim: int = 1024
    qwen_vl_model: str = "qwen-vl-max"
    qwen_ocr_model: str = "qwen-vl-ocr"

    openai_base_url: str = "https://api.openai.com/v1"
    openai_api_key: str = "replace-me"
    chat_model: str = "gpt-4o-mini"
    embedding_model: str = "text-embedding-3-small"
    embedding_dim: int = 1536

    default_chunk_size: int = 800
    default_chunk_overlap: int = 120
    upload_dir: str = "storage/uploads"
    storage_provider: str = "minio"
    storage_prefix: str = "knowledge-bases"

    oss_endpoint: str = "replace-me"
    oss_access_key_id: str = "replace-me"
    oss_access_key_secret: str = "replace-me"
    oss_bucket: str = "insightrag"
    oss_region: str = "oss-cn-hangzhou"
    oss_public_base_url: str = "replace-me"

    minio_endpoint: str = "http://localhost:9000"
    minio_access_key: str = "minioadmin"
    minio_secret_key: str = "minioadmin"
    minio_bucket: str = "insightrag"
    minio_public_base_url: str = "http://localhost:9000/insightrag"
    local_storage_dir: str = "storage/objects"
    local_public_base_url: str = "/storage/objects"

    backend_cors_origins: str = Field(default="http://localhost:5173,http://127.0.0.1:5173")

    @cached_property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.backend_cors_origins.split(",") if origin.strip()]

    @cached_property
    def active_provider(self) -> str:
        provider = self.llm_provider.strip().lower()
        return provider if provider in {"qwen", "openai"} else "qwen"

    @cached_property
    def active_base_url(self) -> str:
        return self.qwen_base_url if self.active_provider == "qwen" else self.openai_base_url

    @cached_property
    def active_api_key(self) -> str:
        return self.qwen_api_key if self.active_provider == "qwen" else self.openai_api_key

    @cached_property
    def active_chat_model(self) -> str:
        return self.qwen_chat_model if self.active_provider == "qwen" else self.chat_model

    @cached_property
    def active_embedding_model(self) -> str:
        return self.qwen_embedding_model if self.active_provider == "qwen" else self.embedding_model

    @cached_property
    def active_embedding_dim(self) -> int:
        return self.qwen_embedding_dim if self.active_provider == "qwen" else self.embedding_dim

    @cached_property
    def active_milvus_collection(self) -> str:
        return self.milvus_collection

    @cached_property
    def milvus_uri(self) -> str:
        return f"http://{self.milvus_host}:{self.milvus_port}"

    @cached_property
    def active_api_key_configured(self) -> bool:
        return bool(self.active_api_key and self.active_api_key != "replace-me")


settings = Settings()
