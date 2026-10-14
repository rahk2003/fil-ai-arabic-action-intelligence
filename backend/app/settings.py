"""Environment-backed configuration with safe local defaults."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SQLITE_URL = f"sqlite:///{PROJECT_ROOT / 'data' / 'fil_ai.db'}"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_prefix="FIL_AI_",
        extra="ignore",
    )

    app_name: str = "FI'L AI API"
    app_version: str = "0.3.0"
    environment: str = "development"
    database_url: str = DEFAULT_SQLITE_URL
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    # SQLite is always initialized additively. PostgreSQL should normally use
    # Alembic; this escape hatch is off so startup cannot bypass migrations.
    auto_create_db: bool = False
    sql_echo: bool = False
    model_path: str | None = None
    camelbert_model_path: str = "models/FIL_AI_CAMeLBERT"
    transformer_device: str = "auto"
    embedding_enabled: bool = True
    embedding_model_name: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    embedding_cache_dir: str = "models/embedding_cache"
    embedding_local_files_only: bool = False
    semantic_threshold: float = 0.55
    api_prefix: str = "/api"

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def is_sqlite(self) -> bool:
        return self.database_url.startswith("sqlite")

    @property
    def resolved_model_path(self) -> Path | None:
        if not self.model_path:
            return None
        path = Path(self.model_path)
        return path if path.is_absolute() else PROJECT_ROOT / path

    @property
    def resolved_camelbert_model_path(self) -> Path:
        path = Path(self.camelbert_model_path)
        return path if path.is_absolute() else PROJECT_ROOT / path

    @property
    def resolved_embedding_cache_dir(self) -> Path:
        path = Path(self.embedding_cache_dir)
        return path if path.is_absolute() else PROJECT_ROOT / path


@lru_cache
def get_settings() -> Settings:
    return Settings()
