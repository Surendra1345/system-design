from __future__ import annotations

from functools import lru_cache
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuration comes from environment variables or a .env file."""

    database_url: str = "sqlite:///./data/blueprint.db"
    session_days: int = 30
    cors_origins: str = "http://localhost:5173"

    # LLM features are optional. Without a key the app still works, and
    # the AI endpoints fall back to simple rules or report that AI is off.
    groq_api_key: Optional[str] = None
    groq_model: str = "openai/gpt-oss-120b"
    ai_calls_per_hour: int = 40

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
