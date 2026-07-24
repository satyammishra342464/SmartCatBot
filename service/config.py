"""Centralised settings, read from environment / .env.

This is the single source of truth for config across the FastAPI backend,
the service layer, and the CLI scripts. Streamlit continues to call
``load_dotenv()`` itself; here we let pydantic-settings read the same .env.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=ROOT / ".env", env_file_encoding="utf-8",
        case_sensitive=False, extra="ignore",
    )

    # Gemini
    gemini_api_key: str = ""
    google_api_key: str = ""  # accepted fallback
    gemini_model: str = "gemini-3.5-flash"
    gemini_embed_model: str = "gemini-embedding-2"

    # Identity (single-user Streamlit + default API user)
    smartcat_user_name: str = "User"
    smartcat_user_email: str = ""

    # Infra
    database_url: str = "postgresql+psycopg://postgres:smartcat@localhost:5432/smartcat"

    @property
    def api_key(self) -> str:
        return self.gemini_api_key or self.google_api_key

    @property
    def default_user_id(self) -> str:
        """The user id Streamlit and unauthenticated API calls fall back to."""
        return self.smartcat_user_email or self.smartcat_user_name or "default"


@lru_cache
def get_settings() -> Settings:
    return Settings()
