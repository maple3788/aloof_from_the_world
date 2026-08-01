from enum import StrEnum
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data"


class LLMProvider(StrEnum):
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    OLLAMA = "ollama"


class EmbeddingProvider(StrEnum):
    OPENAI = "openai"
    OLLAMA = "ollama"
    CHROMA_DEFAULT = "chroma-default"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / "backend" / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    llm_provider: LLMProvider = LLMProvider.OLLAMA

    openai_api_key: str | None = None
    openai_model: str = "gpt-4o-mini"
    # Point at any OpenAI-compatible API (DeepSeek, Moonshot, ...) e.g. https://api.deepseek.com
    openai_base_url: str | None = None

    anthropic_api_key: str | None = None
    anthropic_model: str = "claude-sonnet-4-20250514"

    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.1"

    embedding_provider: EmbeddingProvider = EmbeddingProvider.CHROMA_DEFAULT
    openai_embedding_model: str = "text-embedding-3-small"
    ollama_embedding_model: str = "nomic-embed-text"

    chroma_dir: Path = DATA_DIR / "chroma"
    corpus_dir: Path = DATA_DIR / "corpus"
    database_path: Path = DATA_DIR / "aloof.db"

    retrieval_top_k: int = 6
    critic_enabled: bool = True
    roundtable_max_personas: int = 3
    max_history_messages: int = 20

    # Persona forge: auto-generate persona cards for corpus authors who lack one.
    persona_autogen: bool = True
    persona_gen_timeout: int = 90

    # Uploads: user-supplied texts (.txt/.md/.pdf/.epub), indexed at request time.
    upload_enabled: bool = True
    max_upload_mb: int = 2
    upload_dir: Path = DATA_DIR / "uploads"
    upload_timeout: int = 180

    # Cache layer: unset redis_url disables caching entirely (local-first default).
    redis_url: str | None = None
    cache_ttl_retrieval: int = 3600
    cache_ttl_critic: int = 86400

    cors_origins: list[str] = ["http://localhost:3000"]


@lru_cache
def get_settings() -> Settings:
    return Settings()
