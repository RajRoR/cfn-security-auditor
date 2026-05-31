"""Project-wide pytest configuration and fixtures."""

from __future__ import annotations

import os


def pytest_configure() -> None:
    """Force a deterministic, isolated DB URL for every test run."""
    os.environ.setdefault("CFN_AUDITOR_DATABASE_URL", "sqlite://")
