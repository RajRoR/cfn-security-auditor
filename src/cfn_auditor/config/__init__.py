"""Application configuration (env-only, via pydantic-settings)."""

from cfn_auditor.config.settings import Settings, get_settings

__all__ = ["Settings", "get_settings"]
