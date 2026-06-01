"""In-process per-client rate limiter.

Self-contained — stdlib only. No new runtime dependency. The limiter is
opt-in via :attr:`Settings.rate_limit_requests`; when the cap is 0 (the
default), the middleware is a no-op so dev traffic and the existing test
suite are frictionless.

Algorithm
---------
Fixed window per (client-key, window-start). For each request we compute
``window_start = floor(now / window_seconds) * window_seconds`` and increment
the counter for ``(key, window_start)``. When ``count > cap`` we reject
with HTTP 429. Window expiry is implicit: the dict-key for the next window
is different, so old buckets are GC'd lazily on demand.

Keying
------
Per client. Prefer ``X-API-Key`` (so authenticated callers each get their
own bucket); fall back to ``request.client.host``. Trivial documented rule
that holds for both single-tenant and multi-tenant deployments.

Resilience
----------
Bookkeeping that throws (e.g. a malformed scope, unexpected SDK behaviour)
must NOT take the API down. The middleware catches its own internal errors,
logs them, and **fails open** — the request proceeds. The 429 path is an
intentional rejection, not a failure.

Cooperation with the request-id middleware
------------------------------------------
:class:`RequestLifecycleMiddleware` stamps the active id onto
``request.scope`` at dispatch start. This middleware reads from there so a
429 response carries the same ``X-Request-ID`` that a 200/4xx/5xx would.
The 429's structured WARN log line carries the same id via the contextvar.
"""

from __future__ import annotations

import hashlib
import logging
import math
import threading
import time
from collections.abc import Awaitable, Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.types import ASGIApp

from cfn_auditor.api.observability import REQUEST_ID_HEADER
from cfn_auditor.config import get_settings

__all__ = [
    "EXEMPT_PATHS",
    "FixedWindowLimiter",
    "RateLimitMiddleware",
]


_LIMITER_LOGGER = "cfn_auditor.api.rate_limit"
EXEMPT_PATHS: frozenset[str] = frozenset({"/health"})


class FixedWindowLimiter:
    """Per-key fixed-window counter with an injectable clock for tests."""

    def __init__(
        self,
        *,
        cap: int,
        window_seconds: float,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if cap < 0:
            raise ValueError("cap must be >= 0")
        if window_seconds <= 0:
            raise ValueError("window_seconds must be > 0")
        self._cap = cap
        self._window = window_seconds
        self._clock = clock
        self._lock = threading.Lock()
        self._counts: dict[tuple[str, float], int] = {}

    @property
    def enabled(self) -> bool:
        """Return True when the limiter actually rejects (cap > 0)."""
        return self._cap > 0

    @property
    def cap(self) -> int:
        """Return the per-window request cap."""
        return self._cap

    @property
    def window_seconds(self) -> float:
        """Return the configured window length in seconds."""
        return self._window

    def hit(self, key: str) -> tuple[bool, float]:
        """Record a request for ``key``.

        Returns ``(allowed, retry_after_seconds)``. ``retry_after_seconds`` is
        the time until the current window expires when the request is
        rejected; it is ``0.0`` on the allowed path.
        """
        if not self.enabled:
            return True, 0.0
        now = self._clock()
        window_start = math.floor(now / self._window) * self._window
        with self._lock:
            bucket = (key, window_start)
            current = self._counts.get(bucket, 0) + 1
            self._counts[bucket] = current
            self._gc_locked(now)
        if current > self._cap:
            retry_after = max(0.0, (window_start + self._window) - now)
            return False, retry_after
        return True, 0.0

    def _gc_locked(self, now: float) -> None:
        """Drop buckets older than the current window. Caller holds the lock."""
        cutoff = math.floor(now / self._window) * self._window
        stale = [k for k in self._counts if k[1] < cutoff]
        for k in stale:
            del self._counts[k]


def _client_key(request: Request) -> str:
    """Resolve the bucket key for ``request``.

    The ``X-API-Key`` value is the app's gating credential, so the raw secret
    must never reach the in-memory bucket dict or the throttle log line. We
    derive the bucket key from a SHA-256 digest (truncated to 16 hex chars
    for log readability); distinct API keys still hash to distinct buckets,
    so two different callers remain independently limited. The ``ip:`` branch
    is unchanged — IPs are not secrets and stay useful for debugging.
    """
    api_key = request.headers.get("x-api-key")
    if api_key:
        digest = hashlib.sha256(api_key.encode("utf-8")).hexdigest()[:16]
        return f"api:{digest}"
    client = request.client
    if client is not None and client.host:
        return f"ip:{client.host}"
    return "ip:unknown"


class RateLimitMiddleware(BaseHTTPMiddleware):
    """FastAPI middleware that applies :class:`FixedWindowLimiter`.

    Configuration is read once at construction time so production runs do
    not pay the settings-lookup tax per request. Tests inject a custom
    ``limiter`` (with a controllable clock) directly.
    """

    def __init__(
        self,
        app: ASGIApp,
        *,
        limiter: FixedWindowLimiter | None = None,
    ) -> None:
        super().__init__(app)
        self._logger = logging.getLogger(_LIMITER_LOGGER)
        if limiter is not None:
            self._limiter = limiter
        else:
            settings = get_settings()
            self._limiter = FixedWindowLimiter(
                cap=settings.rate_limit_requests,
                window_seconds=settings.rate_limit_window_seconds,
            )

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        """Throttle the request when the bucket is full; pass otherwise."""
        if not self._limiter.enabled or request.url.path in EXEMPT_PATHS:
            return await call_next(request)

        try:
            key = _client_key(request)
            allowed, retry_after = self._limiter.hit(key)
        except Exception:
            # Bookkeeping must never take the API down. Fail open and let
            # the request through.
            self._logger.exception(
                "Rate limiter bookkeeping failed; failing open.",
                extra={"path": request.url.path},
            )
            return await call_next(request)

        if allowed:
            return await call_next(request)

        request_id = request.scope.get("cfn_auditor.request_id")
        retry_after_int = max(1, math.ceil(retry_after))
        headers: dict[str, str] = {"Retry-After": str(retry_after_int)}
        if isinstance(request_id, str):
            headers[REQUEST_ID_HEADER] = request_id

        self._logger.warning(
            "Rate limit exceeded.",
            extra={
                "client_key": key,
                "path": request.url.path,
                "method": request.method,
                "status_code": 429,
                "retry_after_seconds": retry_after_int,
            },
        )

        return JSONResponse(
            status_code=429,
            content={"detail": "Rate limit exceeded. Retry later."},
            headers=headers,
        )
