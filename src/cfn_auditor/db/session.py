"""SQLModel engine factory + session generator.

The engine is lazily constructed and cached at module level so production code
shares one connection pool. Tests can override the URL via
``reset_engine_for_testing``.
"""

from __future__ import annotations

import logging
from collections.abc import Generator
from typing import Any

from sqlalchemy.engine import Engine
from sqlmodel import Session, SQLModel, create_engine

from cfn_auditor.config import get_settings

__all__ = [
    "create_db_and_tables",
    "get_engine",
    "get_session",
    "reset_engine_for_testing",
]

logger = logging.getLogger(__name__)

_engine: Engine | None = None


def get_engine() -> Engine:
    """Return the lazily initialised process-wide SQLModel engine."""
    global _engine
    if _engine is None:
        settings = get_settings()
        connect_args: dict[str, Any] = {}
        if settings.database_url.startswith("sqlite"):
            connect_args["check_same_thread"] = False
        _engine = create_engine(
            settings.database_url,
            echo=False,
            connect_args=connect_args,
        )
        logger.debug("Initialised DB engine for %s", settings.database_url)
    return _engine


def reset_engine_for_testing(url: str | None = None) -> Engine:
    """Discard the cached engine and rebuild it (optionally with an override URL).

    Intended for the test suite. ``url`` accepts e.g. ``"sqlite://"`` for an
    in-memory database. If omitted, the engine is rebuilt from current settings.
    """
    global _engine
    _engine = None
    if url is not None:
        connect_args: dict[str, Any] = {}
        if url.startswith("sqlite"):
            connect_args["check_same_thread"] = False
        _engine = create_engine(url, echo=False, connect_args=connect_args)
        return _engine
    return get_engine()


def create_db_and_tables() -> None:
    """Create every SQLModel-registered table on the active engine."""
    engine = get_engine()
    SQLModel.metadata.create_all(engine)
    logger.info("Created database tables on %s", engine.url)


def get_session() -> Generator[Session]:
    """Yield a SQLModel Session bound to the active engine."""
    with Session(get_engine()) as session:
        yield session
