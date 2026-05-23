from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = "AI Support & Knowledge Agent"
    app_env: str = "local"
    app_debug: bool = True
    api_prefix: str = "/api/v1"

    database_url: str = Field(
        default="postgresql+psycopg://support_agent:support_agent@localhost:5432/support_agent"
    )
    qdrant_url: str = "http://localhost:6333"
    qdrant_collection: str = "company_knowledge"
    qdrant_vector_size: int = 1536

    embedding_provider: Literal["openai", "local", "disabled"] = "openai"
    embedding_api_key: str = ""
    embedding_model: str = ""

    chat_provider: Literal["openai", "disabled"] = "openai"
    chat_api_key: str = ""
    chat_model: str = ""

    openai_api_key: str = ""
    openai_chat_model: str = "gpt-4.1-mini"
    openai_embedding_model: str = "text-embedding-3-small"

    chunk_size: int = 900
    chunk_overlap: int = 150
    retrieval_top_k: int = 5
    max_upload_mb: int = 25
    upload_dir: str = "uploads/documents"

    langfuse_public_key: str = ""
    langfuse_secret_key: str = ""
    langfuse_host: str = "https://cloud.langfuse.com"


@lru_cache
def get_settings() -> Settings:
    return Settings()
