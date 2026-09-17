from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """项目全局配置。"""

    app_name: str = "XHS Growth Intelligence Agent"
    app_env: str = "dev"
    debug: bool = True
    database_url: str = "postgresql+psycopg2://postgres:postgres@localhost:5432/xhs_growth"
    xhs_crawler_provider: str = "readonly_xhs"
    crawler_headless: bool = False
    crawler_timeout_ms: int = 15000
    embedding_provider: str = "disabled"
    embedding_api_key: str | None = None
    embedding_model: str = "BAAI/bge-m3"
    llm_provider: str = "qwen"
    llm_api_key: str | None = None
    llm_base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    llm_model: str = "qwen-plus"
    llm_timeout_seconds: int = 30
    llm_max_retries: int = 2
    llm_input_price_per_1m: float = 0
    llm_output_price_per_1m: float = 0

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @field_validator("debug", mode="before")
    @classmethod
    def normalize_debug(cls, value):
        """兼容本地 DEBUG=release/prod 这类环境值。"""
        if isinstance(value, str) and value.lower() in {"release", "prod", "production"}:
            return False
        return value


settings = Settings()
