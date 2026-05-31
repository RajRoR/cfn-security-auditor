"""Engine-layer test fixtures: in-memory DB session, fixture-template loader."""

from collections.abc import Generator
from pathlib import Path

import pytest
from sqlalchemy.engine import Engine
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine


@pytest.fixture
def engine() -> Generator[Engine]:
    """In-memory SQLite engine, shared across connections via StaticPool.

    Per CLAUDE.md: in-memory test engines must use StaticPool +
    check_same_thread=False so a single shared in-memory database is visible
    across connections (required for any future TestClient/threaded paths).
    """
    test_engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(test_engine)
    try:
        yield test_engine
    finally:
        SQLModel.metadata.drop_all(test_engine)
        test_engine.dispose()


@pytest.fixture
def session(engine: Engine) -> Generator[Session]:
    """SQLModel Session bound to the in-memory engine."""
    with Session(engine) as s:
        yield s


@pytest.fixture
def fixtures_dir() -> Path:
    """Absolute path to ``tests/fixtures``."""
    return Path(__file__).resolve().parent.parent / "fixtures"
