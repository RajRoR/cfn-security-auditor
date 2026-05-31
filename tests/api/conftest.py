"""API test fixtures: TestClient with the session dependency overridden.

The session dependency is overridden to yield a SQLModel session bound to an
in-memory ``StaticPool`` SQLite engine (per CLAUDE.md), so each test gets an
isolated DB without touching the production engine.
"""

from collections.abc import Generator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.engine import Engine
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from cfn_auditor.api import create_app
from cfn_auditor.api.dependencies import get_session


@pytest.fixture
def engine() -> Generator[Engine]:
    """In-memory SQLite engine shared across connections via StaticPool."""
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
def app(engine: Engine) -> FastAPI:
    """FastAPI app with the session dependency overridden onto the test engine."""
    application = create_app()

    def _override_get_session() -> Generator[Session]:
        with Session(engine) as session:
            yield session

    application.dependency_overrides[get_session] = _override_get_session
    return application


@pytest.fixture
def client(app: FastAPI) -> Generator[TestClient]:
    """TestClient bound to the test app."""
    with TestClient(app) as test_client:
        yield test_client
