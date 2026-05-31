"""Observability tests: X-Request-ID propagation + structured JSON logging.

The middleware contract:

* When the inbound request carries no ``X-Request-ID``, the middleware
  generates one (a uuid4 hex) and echoes it on the response.
* When the inbound request carries ``X-Request-ID``, the middleware echoes
  it back unchanged — even on an error response.
* One JSON-formatted log line per request lands on the
  ``cfn_auditor.api.access`` logger, carrying request_id + status_code +
  method/path/duration_ms.
* No log record produced anywhere during the request lifecycle contains
  template content (the error-hygiene contract applied to logs).
"""

from __future__ import annotations

import json
import logging
import re
import uuid
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient

from cfn_auditor.api.observability import (
    REQUEST_ID_HEADER,
    RequestIdFilter,
    _JsonFormatter,
)
from cfn_auditor.config import get_settings

_HEX_RE = re.compile(r"^[0-9a-f]{32}$")


class _CapturingHandler(logging.Handler):
    """A logging handler that records each formatted record into a list."""

    def __init__(self, lines: list[str]) -> None:
        super().__init__()
        self._lines = lines
        self.setFormatter(_JsonFormatter())
        self.addFilter(RequestIdFilter())

    def emit(self, record: logging.LogRecord) -> None:
        self._lines.append(self.format(record))


@pytest.fixture
def captured_logs() -> Generator[list[str]]:
    """Capture log records emitted during the test as JSON-formatted strings.

    Records are appended live (not at teardown) so a test can read them
    immediately after the request returns.
    """
    lines: list[str] = []
    handler = _CapturingHandler(lines)
    root = logging.getLogger()
    previous_level = root.level
    root.setLevel(logging.DEBUG)
    root.addHandler(handler)
    try:
        yield lines
    finally:
        root.removeHandler(handler)
        root.setLevel(previous_level)


# ---------------------------------------------------------------------------
# Header propagation
# ---------------------------------------------------------------------------


def test_request_id_generated_when_inbound_header_absent(client: TestClient) -> None:
    """No inbound header → server generates a uuid4 hex and echoes it."""
    response = client.get("/health")
    assert response.status_code == 200
    rid = response.headers.get(REQUEST_ID_HEADER)
    assert rid is not None
    assert _HEX_RE.match(rid)
    assert uuid.UUID(rid)  # valid uuid hex


def test_request_id_propagated_unchanged_when_supplied(client: TestClient) -> None:
    """Inbound X-Request-ID rides through unchanged on the response."""
    response = client.get(
        "/health",
        headers={REQUEST_ID_HEADER: "client-supplied-trace-1234"},
    )
    assert response.status_code == 200
    assert response.headers[REQUEST_ID_HEADER] == "client-supplied-trace-1234"


def test_request_id_echoed_on_404(client: TestClient) -> None:
    """A 404 still echoes X-Request-ID."""
    response = client.get("/scans/99999")
    assert response.status_code == 404
    assert REQUEST_ID_HEADER in response.headers


def test_request_id_echoed_on_401(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    """A 401 still echoes X-Request-ID."""
    monkeypatch.setenv("CFN_AUDITOR_API_KEY", "topsecret")
    get_settings.cache_clear()
    try:
        response = client.get("/rules")  # gated, no key sent
        assert response.status_code == 401
        assert REQUEST_ID_HEADER in response.headers
    finally:
        get_settings.cache_clear()


# ---------------------------------------------------------------------------
# Structured JSON logging
# ---------------------------------------------------------------------------


def test_lifecycle_log_is_valid_json_with_facets(
    client: TestClient, captured_logs: list[str]
) -> None:
    """A successful request emits one JSON log line carrying the documented facets."""
    response = client.get(
        "/health",
        headers={REQUEST_ID_HEADER: "trace-abc"},
    )
    assert response.status_code == 200

    access_lines: list[dict[str, object]] = []
    for raw in captured_logs:
        record = json.loads(raw)
        if record.get("logger") == "cfn_auditor.api.access":
            access_lines.append(record)

    assert access_lines, "expected at least one access-log record"
    line = access_lines[-1]
    assert line["message"] == "request.complete"
    assert line["request_id"] == "trace-abc"
    assert line["method"] == "GET"
    assert line["path"] == "/health"
    assert line["status_code"] == 200
    assert isinstance(line["duration_ms"], int)
    assert line["level"] == "INFO"


def test_lifecycle_log_warning_level_for_4xx(client: TestClient, captured_logs: list[str]) -> None:
    """4xx requests log at WARNING level."""
    response = client.get("/scans/99999")
    assert response.status_code == 404

    access_lines = [
        json.loads(raw)
        for raw in captured_logs
        if json.loads(raw).get("logger") == "cfn_auditor.api.access"
    ]
    last = access_lines[-1]
    assert last["status_code"] == 404
    assert last["level"] == "WARNING"


def test_logs_never_echo_template_content_on_parse_failure(
    client: TestClient, captured_logs: list[str]
) -> None:
    """Logs from a malformed-template POST contain no fragment of the source.

    The endpoint already returns a clean error body (PR #9 regression test);
    this asserts the same hygiene rule on the log surface.
    """
    template = "Resources: : :\n" "  SecretBucketName: my-confidential-bucket-do-not-leak\n"
    response = client.post(
        "/scans",
        json={"template": template, "name": "leak-test.yaml"},
    )
    assert response.status_code == 400

    forbidden = (
        "SecretBucketName",
        "my-confidential-bucket-do-not-leak",
        "Resources: : :",
    )
    for raw in captured_logs:
        for needle in forbidden:
            assert needle not in raw, f"Template content {needle!r} leaked into log line: {raw}"


# ---------------------------------------------------------------------------
# Formatter / filter direct tests
# ---------------------------------------------------------------------------


def test_json_formatter_includes_extras_and_drops_internals() -> None:
    """The JSON formatter serialises ``extra`` keys but skips logging internals."""
    record = logging.LogRecord(
        name="cfn_auditor.test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="hello %s",
        args=("world",),
        exc_info=None,
    )
    record.request_id = "abc"
    record.method = "GET"
    payload = json.loads(_JsonFormatter().format(record))
    assert payload["message"] == "hello world"
    assert payload["request_id"] == "abc"
    assert payload["method"] == "GET"
    assert payload["level"] == "INFO"
    assert "args" not in payload  # standard logging attr is dropped


def test_unhandled_exception_yields_500_with_request_id_and_one_access_log(
    app: object, captured_logs: list[str]
) -> None:
    """A genuine unhandled exception still echoes X-Request-ID on the 500.

    Uses TestClient(raise_server_exceptions=False) so the framework returns
    the produced 500 response instead of re-raising into the test. The
    failing handler raises a synthetic exception via a route override; the
    registered exception handler converts it into a 500 carrying the
    documented body. The middleware adds X-Request-ID and the lifecycle log
    must fire exactly once with status_code 500 at ERROR level.
    """
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    fastapi_app: FastAPI = app  # type: ignore[assignment]

    @fastapi_app.get("/__test_boom")
    def _boom() -> None:
        raise RuntimeError("synthetic")

    with TestClient(fastapi_app, raise_server_exceptions=False) as bad_client:
        response = bad_client.get("/__test_boom", headers={REQUEST_ID_HEADER: "trace-boom"})
    assert response.status_code == 500
    assert response.headers.get(REQUEST_ID_HEADER) == "trace-boom"
    assert response.json() == {"detail": "Internal Server Error"}

    access_lines = [
        json.loads(raw)
        for raw in captured_logs
        if json.loads(raw).get("logger") == "cfn_auditor.api.access"
        and json.loads(raw).get("message") == "request.complete"
        and json.loads(raw).get("path") == "/__test_boom"
    ]
    assert len(access_lines) == 1, f"expected exactly one lifecycle log, got {access_lines}"
    line = access_lines[0]
    assert line["status_code"] == 500
    assert line["level"] == "ERROR"
    assert line["request_id"] == "trace-boom"


def test_request_id_filter_annotates_records_without_request_id() -> None:
    """The filter sets ``record.request_id`` from the contextvar when missing."""
    record = logging.LogRecord(
        name="x",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="m",
        args=(),
        exc_info=None,
    )
    assert RequestIdFilter().filter(record) is True
    assert hasattr(record, "request_id")
