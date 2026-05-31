"""Typed application settings, loaded from environment variables only."""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

__all__ = ["Settings", "get_settings"]


class Settings(BaseSettings):
    """Runtime configuration sourced from the environment.

    All fields have safe defaults so the app boots in dev with zero env vars.
    """

    model_config = SettingsConfigDict(
        env_prefix="CFN_AUDITOR_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    api_key: str | None = Field(
        default=None,
        description=(
            "Optional API key. If set, requests must send X-API-Key. "
            "If unset, the API is open (dev mode)."
        ),
    )
    database_url: str = Field(
        default="sqlite:///./cfn_auditor.db",
        description="SQLModel/SQLAlchemy database URL.",
    )
    max_template_bytes: int = Field(
        default=5 * 1024 * 1024,
        ge=1,
        description="Hard cap on CloudFormation template size in bytes.",
    )
    log_level: str = Field(
        default="INFO",
        description="Root logger level (DEBUG, INFO, WARNING, ERROR).",
    )
    llm_provider: str | None = Field(
        default=None,
        description=(
            "Selects an LLM remediation provider. Currently supported: "
            "'anthropic'. Unset → deterministic static provider."
        ),
    )
    llm_api_key: str | None = Field(
        default=None,
        description="Credential for the configured LLM provider.",
    )
    llm_model: str = Field(
        default="claude-sonnet-4-5",
        description="Model identifier passed to the LLM provider.",
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the process-wide Settings instance, cached for reuse."""
    return Settings()
