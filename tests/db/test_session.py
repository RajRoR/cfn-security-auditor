"""Tests for engine + session helpers in cfn_auditor.db.session."""

import contextlib

from sqlalchemy.engine import Engine
from sqlmodel import Session

from cfn_auditor.db import (
    create_db_and_tables,
    get_engine,
    get_session,
    reset_engine_for_testing,
)


def test_get_engine_caches_singleton() -> None:
    """get_engine returns the same Engine instance across calls."""
    reset_engine_for_testing("sqlite://")
    first = get_engine()
    second = get_engine()
    assert first is second
    first.dispose()


def test_reset_engine_for_testing_with_url_overrides() -> None:
    """reset_engine_for_testing replaces the cached engine when a URL is given."""
    reset_engine_for_testing("sqlite://")
    first = get_engine()
    second = reset_engine_for_testing("sqlite://")
    assert first is not second
    assert isinstance(second, Engine)
    second.dispose()


def test_reset_engine_for_testing_without_url_rebuilds() -> None:
    """reset_engine_for_testing() with no URL rebuilds from current settings."""
    reset_engine_for_testing("sqlite://")
    rebuilt = reset_engine_for_testing()
    assert isinstance(rebuilt, Engine)
    rebuilt.dispose()


def test_create_db_and_tables_runs_clean() -> None:
    """create_db_and_tables succeeds against a fresh in-memory engine."""
    engine = reset_engine_for_testing("sqlite://")
    create_db_and_tables()
    inspector_has_tables = engine.dialect.has_table(engine.connect(), "scan")
    assert inspector_has_tables
    engine.dispose()


def test_get_session_yields_session() -> None:
    """get_session yields an open SQLModel Session bound to the active engine."""
    engine = reset_engine_for_testing("sqlite://")
    create_db_and_tables()
    gen = get_session()
    session = next(gen)
    try:
        assert isinstance(session, Session)
        assert session.bind is engine
    finally:
        with contextlib.suppress(StopIteration):
            next(gen)
    engine.dispose()
