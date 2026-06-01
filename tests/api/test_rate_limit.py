"""Rate-limiter tests with an injected clock — no wall-clock sleeps.

The middleware reads its limiter from settings at construction. To avoid
booting an entire app per scenario we build a thin Starlette/FastAPI app
inline with a custom :class:`FixedWindowLimiter` that uses a controllable
clock. The observability middleware is wired in too so we can assert that
``X-Request-ID`` is preserved on the 429 path (per the directive: the
limiter must compose with request-id).
"""

from __future__ import annotations

import json
import logging
from collections.abc import Generator
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from cfn_auditor.api.observability import (
    REQUEST_ID_HEADER,
    RequestIdFilter,
    _JsonFormatter,
    install_observability,
)
from cfn_auditor.api.rate_limit import (
    EXEMPT_PATHS,
    FixedWindowLimiter,
    RateLimitMiddleware,
    _client_key,
)


class _Clock:
    """Mutable clock fixture — tests advance ``now`` explicitly."""

    def __init__(self, start: float = 1000.0) -> None:
        self.now = start

    def __call__(self) -> float:
        return self.now


def _build_app(limiter: FixedWindowLimiter) -> FastAPI:
    """Spin up a minimal app wired with both middlewares."""
    application = FastAPI()
    application.add_middleware(RateLimitMiddleware, limiter=limiter)
    install_observability(application)

    @application.get("/health")
    def _health() -> dict[str, str]:
        return {"status": "ok"}

    @application.get("/probe")
    def _probe() -> dict[str, str]:
        return {"ok": "yes"}

    return application


# ---------------------------------------------------------------------------
# Captured-log fixture (mirrors test_observability.py's helper)
# ---------------------------------------------------------------------------


class _CapturingHandler(logging.Handler):
    def __init__(self, lines: list[str]) -> None:
        super().__init__()
        self._lines = lines
        self.setFormatter(_JsonFormatter())
        self.addFilter(RequestIdFilter())

    def emit(self, record: logging.LogRecord) -> None:
        self._lines.append(self.format(record))


@pytest.fixture
def captured_logs() -> Generator[list[str]]:
    lines: list[str] = []
    handler = _CapturingHandler(lines)
    root = logging.getLogger()
    previous = root.level
    root.setLevel(logging.DEBUG)
    root.addHandler(handler)
    try:
        yield lines
    finally:
        root.removeHandler(handler)
        root.setLevel(previous)


# ---------------------------------------------------------------------------
# Core throttling
# ---------------------------------------------------------------------------


def test_n_requests_pass_then_n_plus_1_throttles() -> None:
    """First N requests succeed; the (N+1)th lands inside the same window → 429."""
    clock = _Clock(start=1000.0)
    limiter = FixedWindowLimiter(cap=2, window_seconds=60.0, clock=clock)
    with TestClient(_build_app(limiter)) as client:
        assert client.get("/probe").status_code == 200
        assert client.get("/probe").status_code == 200
        rejected = client.get("/probe")
    assert rejected.status_code == 429
    assert rejected.json() == {"detail": "Rate limit exceeded. Retry later."}


def test_window_advance_unblocks() -> None:
    """Advancing the clock past the window boundary lets requests through again."""
    clock = _Clock(start=1000.0)
    limiter = FixedWindowLimiter(cap=1, window_seconds=60.0, clock=clock)
    with TestClient(_build_app(limiter)) as client:
        assert client.get("/probe").status_code == 200
        # Same window → 429.
        assert client.get("/probe").status_code == 429
        # Cross the window boundary.
        clock.now += 60.0
        assert client.get("/probe").status_code == 200


def test_429_carries_request_id_and_retry_after_and_clean_body() -> None:
    """The 429 echoes the inbound X-Request-ID, returns Retry-After + the docs body."""
    clock = _Clock(start=0.0)
    limiter = FixedWindowLimiter(cap=1, window_seconds=30.0, clock=clock)
    with TestClient(_build_app(limiter)) as client:
        client.get("/probe")
        # 5 seconds into the 30s window, 25 left.
        clock.now = 5.0
        rejected = client.get("/probe", headers={REQUEST_ID_HEADER: "trace-throttle"})
    assert rejected.status_code == 429
    assert rejected.headers.get(REQUEST_ID_HEADER) == "trace-throttle"
    retry_after = rejected.headers.get("Retry-After")
    assert retry_after is not None
    # Retry-After is whole-second integer; bucket has 25s remaining.
    assert int(retry_after) == 25
    # Uniform error envelope, no template content.
    assert rejected.json() == {"detail": "Rate limit exceeded. Retry later."}


def test_health_is_never_throttled() -> None:
    """/health is exempt: docker-compose's healthcheck must not flap."""
    clock = _Clock()
    limiter = FixedWindowLimiter(cap=1, window_seconds=60.0, clock=clock)
    assert "/health" in EXEMPT_PATHS
    with TestClient(_build_app(limiter)) as client:
        for _ in range(5):
            assert client.get("/health").status_code == 200


def test_disabled_when_cap_is_zero() -> None:
    """A zero cap means the limiter is a no-op — no 429s are ever produced."""
    clock = _Clock()
    limiter = FixedWindowLimiter(cap=0, window_seconds=60.0, clock=clock)
    assert limiter.enabled is False
    with TestClient(_build_app(limiter)) as client:
        for _ in range(5):
            assert client.get("/probe").status_code == 200


def test_two_distinct_keys_are_limited_independently() -> None:
    """Two API keys consume two separate buckets within the same window."""
    clock = _Clock(start=10_000.0)
    limiter = FixedWindowLimiter(cap=1, window_seconds=60.0, clock=clock)
    with TestClient(_build_app(limiter)) as client:
        assert client.get("/probe", headers={"X-API-Key": "alice"}).status_code == 200
        # Alice is now full-bucket; Bob still has his window.
        assert client.get("/probe", headers={"X-API-Key": "alice"}).status_code == 429
        assert client.get("/probe", headers={"X-API-Key": "bob"}).status_code == 200
        assert client.get("/probe", headers={"X-API-Key": "bob"}).status_code == 429


# ---------------------------------------------------------------------------
# Resilience: a bookkeeping error must not 500 the API
# ---------------------------------------------------------------------------


def test_internal_error_in_limiter_fails_open() -> None:
    """If hit() throws, the request still goes through (and the error is logged)."""

    class _Boom(FixedWindowLimiter):
        def hit(self, key: str) -> tuple[bool, float]:
            raise RuntimeError("synthetic limiter bug")

    limiter = _Boom(cap=1, window_seconds=60.0, clock=_Clock())
    with TestClient(_build_app(limiter)) as client:
        response = client.get("/probe")
    assert response.status_code == 200


# ---------------------------------------------------------------------------
# Logging hygiene + key resolution
# ---------------------------------------------------------------------------


def test_429_logs_one_warning_with_key_and_path_no_template_content(
    captured_logs: list[str],
) -> None:
    """The throttle WARN line carries client_key + path + status, never the raw key."""
    import re

    clock = _Clock()
    limiter = FixedWindowLimiter(cap=1, window_seconds=60.0, clock=clock)
    with TestClient(_build_app(limiter)) as client:
        client.get("/probe", headers={"X-API-Key": "alice"})
        client.get("/probe", headers={"X-API-Key": "alice"})

    rate_limit_lines: list[dict[str, Any]] = []
    for raw in captured_logs:
        record = json.loads(raw)
        if record.get("logger") == "cfn_auditor.api.rate_limit":
            rate_limit_lines.append(record)

    assert len(rate_limit_lines) == 1
    line = rate_limit_lines[0]
    assert line["level"] == "WARNING"
    # client_key is the SHA-256 prefix, never the raw secret.
    assert isinstance(line["client_key"], str)
    assert re.fullmatch(r"api:[0-9a-f]{16}", line["client_key"])
    assert line["path"] == "/probe"
    assert line["status_code"] == 429
    # The raw API-key value MUST NOT appear anywhere in the log JSON.
    raw_text = json.dumps(line)
    assert "alice" not in raw_text
    # Sanity: nothing template-shaped leaked in.
    for forbidden in ("Resources:", "AWS::", "BucketName"):
        assert forbidden not in raw_text


def test_client_key_prefers_x_api_key_over_ip() -> None:
    """X-API-Key wins over request.client.host when both are present."""
    clock = _Clock()
    limiter = FixedWindowLimiter(cap=1, window_seconds=60.0, clock=clock)
    with TestClient(_build_app(limiter)) as client:
        # Same IP, different keys: the buckets must NOT collide.
        assert client.get("/probe", headers={"X-API-Key": "k1"}).status_code == 200
        assert client.get("/probe", headers={"X-API-Key": "k2"}).status_code == 200
        # Same key from a (presumed) different IP would still share the bucket.
        assert client.get("/probe", headers={"X-API-Key": "k1"}).status_code == 429


def test_client_key_uses_request_client_host_when_no_api_key() -> None:
    """Without X-API-Key the bucket key uses the IP."""
    clock = _Clock()
    limiter = FixedWindowLimiter(cap=2, window_seconds=60.0, clock=clock)
    with TestClient(_build_app(limiter)) as client:
        assert client.get("/probe").status_code == 200
        assert client.get("/probe").status_code == 200
        assert client.get("/probe").status_code == 429


def test_unit_client_key_returns_unknown_when_client_missing() -> None:
    """Direct unit test on _client_key for the unusual no-client scope path."""
    from starlette.requests import Request

    scope: dict[str, Any] = {
        "type": "http",
        "method": "GET",
        "headers": [],
        "client": None,
        "path": "/probe",
        "query_string": b"",
    }
    request = Request(scope)
    assert _client_key(request) == "ip:unknown"


# ---------------------------------------------------------------------------
# Defensive constructor checks (runtime guards round out coverage)
# ---------------------------------------------------------------------------


def test_negative_cap_rejected() -> None:
    with pytest.raises(ValueError, match=">= 0"):
        FixedWindowLimiter(cap=-1, window_seconds=10.0)


def test_non_positive_window_rejected() -> None:
    with pytest.raises(ValueError, match="> 0"):
        FixedWindowLimiter(cap=1, window_seconds=0.0)


def test_disabled_limiter_hit_returns_allowed_without_bookkeeping() -> None:
    """When disabled, hit() short-circuits — useful for unit-level tests."""
    limiter = FixedWindowLimiter(cap=0, window_seconds=10.0)
    allowed, retry = limiter.hit("anyone")
    assert allowed is True
    assert retry == 0.0


def test_old_buckets_are_garbage_collected() -> None:
    """After the clock advances, stale buckets are dropped from the dict."""
    clock = _Clock(start=0.0)
    limiter = FixedWindowLimiter(cap=10, window_seconds=10.0, clock=clock)
    limiter.hit("alice")
    assert len(limiter._counts) == 1
    clock.now = 1000.0  # many windows later
    limiter.hit("alice")
    assert len(limiter._counts) == 1
