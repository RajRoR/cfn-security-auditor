"""Tests for cfn_auditor.config.settings."""

from cfn_auditor.config import Settings, get_settings


def test_settings_defaults_are_safe() -> None:
    """Default Settings boots with no env vars and points at local SQLite."""
    settings = Settings()
    assert settings.api_key is None
    assert settings.database_url.startswith("sqlite://")
    assert settings.max_template_bytes >= 1
    assert settings.log_level == "INFO"


def test_get_settings_is_cached() -> None:
    """get_settings returns the same instance across calls."""
    a = get_settings()
    b = get_settings()
    assert a is b
