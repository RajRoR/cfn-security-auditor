"""FastAPI dependencies: DB session + optional API-key auth.

The session dependency wraps the existing ``cfn_auditor.db.get_session``
generator so routes use ``Depends(get_session)`` and tests override **this
seam** to inject an in-memory ``StaticPool`` engine.

The API-key dependency honours the CLAUDE.md security contract: if
``CFN_AUDITOR_API_KEY`` is unset, the API is open (dev mode); if set, every
gated route must carry a matching ``X-API-Key`` header. The comparison uses
``secrets.compare_digest`` for constant-time equality.
"""

import secrets
from collections.abc import Generator

from fastapi import Header, HTTPException, status
from sqlmodel import Session

from cfn_auditor.config import get_settings
from cfn_auditor.db import get_session as _db_get_session

__all__ = ["get_session", "require_api_key"]


def get_session() -> Generator[Session]:
    """Yield a per-request SQLModel session bound to the active engine."""
    yield from _db_get_session()


def require_api_key(x_api_key: str | None = Header(default=None)) -> None:
    """Optional API-key gate.

    - When ``CFN_AUDITOR_API_KEY`` is unset, the gate is a no-op (dev mode).
    - When set, ``X-API-Key`` must be supplied and match exactly. Mismatch or
      absence raises HTTP 401.
    """
    expected = get_settings().api_key
    if expected is None:
        return
    supplied = x_api_key or ""
    if not secrets.compare_digest(supplied, expected):
        # Intentionally no WWW-Authenticate header: that header is reserved
        # for IANA-registered HTTP auth schemes (Basic, Bearer, ...). The
        # custom X-API-Key gate is not a registered scheme, so emitting
        # "WWW-Authenticate: X-API-Key" was non-standard and could confuse
        # well-behaved clients.
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key.",
        )
