"""FastAPI application factory.

The app is built via ``create_app()`` so tests can spin up an isolated
instance with overridden dependencies. The module-level ``app`` is what
``uvicorn cfn_auditor.api.app:app`` runs in production / dev.

Tables are created at startup via ``create_db_and_tables`` (the canonical
helper in ``cfn_auditor.db``). The DB layer owns engine creation; this module
only triggers schema creation.
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from cfn_auditor.api.observability import install_observability
from cfn_auditor.api.routes import health, rules, scans
from cfn_auditor.db import create_db_and_tables

__all__ = ["app", "create_app"]


@asynccontextmanager
async def _lifespan(_application: FastAPI) -> AsyncIterator[None]:
    """Ensure schema exists on the active engine before serving traffic."""
    create_db_and_tables()
    yield


def create_app() -> FastAPI:
    """Build and return a configured FastAPI instance."""
    application = FastAPI(
        title="CFN Security Auditor",
        description=(
            "Static-analysis security guardrail auditor for AWS CloudFormation "
            "templates. API-first; no live AWS calls."
        ),
        version="0.1.0",
        lifespan=_lifespan,
    )
    install_observability(application)
    application.include_router(health.router)
    application.include_router(rules.router)
    application.include_router(scans.router)
    return application


app = create_app()
