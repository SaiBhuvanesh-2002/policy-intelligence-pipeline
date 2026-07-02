"""Application configuration loaded from environment / .env file."""
from __future__ import annotations

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
SEED_DIR = DATA_DIR / "seeds"
FRONTEND_DIR = BASE_DIR / "frontend"
DB_PATH = DATA_DIR / "policy_intel.db"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_prefix="PIP_",
        extra="ignore",
    )

    llm_provider: str = "offline"
    anthropic_model: str = "claude-3-5-sonnet-latest"
    openai_model: str = "gpt-4o"
    groq_model: str = "llama-3.3-70b-versatile"
    allow_network_fetch: bool = False
    demo_auto_approve: bool = True

    # Provider keys use their conventional env var names (no PIP_ prefix).
    # validation_alias bypasses env_prefix so these load from .env and real env vars.
    anthropic_api_key: str = Field("", validation_alias="ANTHROPIC_API_KEY")
    openai_api_key: str = Field("", validation_alias="OPENAI_API_KEY")
    groq_api_key: str = Field("", validation_alias="GROQ_API_KEY")


settings = Settings()
