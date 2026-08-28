"""Central configuration. No secret is ever hard-coded — everything comes from the
environment via pydantic-settings."""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # --- database ---
    database_url: str = "postgresql+psycopg://aq:aq@localhost:5432/aq"

    # --- auth ---
    jwt_secret: str = "dev-secret-not-for-prod"
    jwt_algorithm: str = "HS256"
    access_token_ttl_minutes: int = 15
    refresh_token_ttl_days: int = 14

    # --- llm (advisory rephrasing only) ---
    llm_api_key: str | None = None
    llm_base_url: str = "https://api.openai.com/v1"
    llm_model: str = "gpt-4o-mini"

    # --- ingestion / scheduler ---
    openaq_base_url: str = "https://api.openaq.org/v3"
    openweather_api_key: str | None = None
    scheduler_enabled: bool = True
    synthetic_ingest: bool = True
    ingest_interval_minutes: int = 20

    # --- rag ---
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    rag_min_score: float = 0.32  # cosine similarity floor before we refuse
    rag_top_k: int = 4

    # --- uploads ---
    upload_dir: str = "uploads"

    @property
    def is_sqlite(self) -> bool:
        return self.database_url.startswith("sqlite")


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
