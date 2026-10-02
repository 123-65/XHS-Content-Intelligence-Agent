from typing import Literal

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
    xhs_mcp_base_url: str = ""
    xhs_mcp_host_header: str = ""
    xhs_mcp_timeout_seconds: int = 60
    xhs_mcp_auth_token: str = ""
    embedding_provider: str = "disabled"
    embedding_api_key: str | None = None
    embedding_model: str = "BAAI/bge-m3"
    llm_provider: str = "qwen"
    llm_api_key: str | None = None
    llm_base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    llm_model: str = "qwen-plus"
    llm_control_semantic_model: str | None = None
    llm_timeout_seconds: int = 30
    agent_workflow_tool_timeout_seconds: int = 150
    llm_research_analysis_model: str = "qwen3.7-flash-2026-07-15"
    llm_research_analysis_timeout_seconds: int = 120
    llm_content_strategy_timeout_seconds: int = 120
    llm_draft_generation_timeout_seconds: int = 120
    llm_draft_review_model: str = "qwen3.7-flash-2026-07-15"
    llm_draft_review_timeout_seconds: int = 120
    llm_research_analysis_enable_thinking: bool = False
    llm_post_publish_review_model: str | None = None
    llm_post_publish_review_timeout_seconds: int | None = None
    llm_post_publish_review_enable_thinking: bool | None = None
    llm_draft_revision_model: str | None = None
    llm_draft_revision_timeout_seconds: int | None = None
    llm_draft_revision_enable_thinking: bool | None = None
    llm_max_retries: int = 2
    llm_input_price_per_1m: float = 0
    llm_output_price_per_1m: float = 0
    agent_entry_mode: Literal["legacy", "conversation_v2"] = "conversation_v2"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @field_validator("debug", mode="before")
    @classmethod
    def normalize_debug(cls, value):
        """兼容本地 DEBUG=release/prod 这类环境值。"""
        if isinstance(value, str) and value.lower() in {"release", "prod", "production"}:
            return False
        return value

    @field_validator("llm_research_analysis_timeout_seconds")
    @classmethod
    def validate_research_analysis_timeout(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("LLM_RESEARCH_ANALYSIS_TIMEOUT_SECONDS must be positive")
        return value

    @field_validator(
        "llm_content_strategy_timeout_seconds",
        "llm_draft_generation_timeout_seconds",
        "llm_draft_review_timeout_seconds",
        "xhs_mcp_timeout_seconds",
        "agent_workflow_tool_timeout_seconds",
    )
    @classmethod
    def validate_positive_timeout(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("configured timeout must be positive")
        return value

    @field_validator("llm_post_publish_review_timeout_seconds")
    @classmethod
    def validate_post_publish_review_timeout(cls, value: int | None) -> int | None:
        if value is not None and value <= 0:
            raise ValueError("LLM_POST_PUBLISH_REVIEW_TIMEOUT_SECONDS must be positive")
        return value

    @field_validator("llm_draft_revision_timeout_seconds")
    @classmethod
    def validate_draft_revision_timeout(cls, value: int | None) -> int | None:
        if value is not None and value <= 0:
            raise ValueError("LLM_DRAFT_REVISION_TIMEOUT_SECONDS must be positive")
        return value


settings = Settings()
