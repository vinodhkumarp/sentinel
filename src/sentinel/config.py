"""Configuration. Everything tunable lives here; nothing tunable lives in code."""

from __future__ import annotations

from pydantic import Field, PostgresDsn
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="SENTINEL_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    source_database_url: PostgresDsn = Field(
        default=PostgresDsn("postgresql://rateradar:rateradar@localhost:5432/rateradar"),
        description="The pipeline Sentinel reads. Read-only: nothing here writes to it.",
    )

    # --- history --------------------------------------------------------------
    # How many prior runs to consider when deciding whether something is normal.
    # Ten runs is five days at RateRadar's cadence: long enough for a baseline,
    # short enough that a bank's deliberate product cull becomes the new normal
    # within a week rather than alerting forever.
    history_runs: int = 10

    # --- narration (optional; see ADR-0003) -----------------------------------
    narrate: bool = False
    ollama_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.1:8b"
    ollama_timeout_s: float = 60.0


settings = Settings()
