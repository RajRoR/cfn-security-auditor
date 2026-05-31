"""Observability: request-id middleware + structured JSON logging.

This module is the only place we ever read or write the ``X-Request-ID``
header and the only place that touches root-logger configuration. The rest
of the codebase keeps using module-level ``logging.getLogger(__name__)``
loggers; their records pass through the JSON formatter installed here.

Design notes
------------
* The current request id lives in a :class:`contextvars.ContextVar` so it
  survives across coroutines without being threaded through every call.
  A :class:`logging.Filter` injects the active id onto every record so the
  JSON formatter can emit it.
* The middleware wraps the entire request lifecycle (so a 5xx still gets a
  structured access-log line and an X-Request-ID echo) and never calls
  through to template content. The lifecycle log carries metadata only
  (method, path, status, duration, request_id) — no request body, no
  response body. That is the error-hygiene contract applied to logs.
* Setup is idempotent: calling :func:`configure_logging` twice does not
  stack handlers.
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from collections.abc import Awaitable, Callable
from contextvars import ContextVar
from datetime import UTC, datetime

from fastapi import FastAPI
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp

__all__ = [
    "REQUEST_ID_HEADER",
    "RequestIdFilter",
    "RequestLifecycleMiddleware",
    "configure_logging",
    "get_request_id",
    "install_observability",
]


REQUEST_ID_HEADER: str = "X-Request-ID"
_HANDLER_NAME = "cfn_auditor.observability.json"
_LIFECYCLE_LOGGER = "cfn_auditor.api.access"

_request_id_var: ContextVar[str | None] = ContextVar("cfn_auditor_request_id", default=None)


def get_request_id() -> str | None:
    """Return the current request's id, if a request is in flight."""
    return _request_id_var.get()


# --- JSON formatter ---------------------------------------------------------


class _JsonFormatter(logging.Formatter):
    """Render a log record as a single JSON object on one line."""

    _STANDARD_ATTRS: frozenset[str] = frozenset(
        {
            "name",
            "msg",
            "args",
            "levelname",
            "levelno",
            "pathname",
            "filename",
            "module",
            "exc_info",
            "exc_text",
            "stack_info",
            "lineno",
            "funcName",
            "created",
            "msecs",
            "relativeCreated",
            "thread",
            "threadName",
            "processName",
            "process",
            "request_id",
            "taskName",
        }
    )

    def format(self, record: logging.LogRecord) -> str:
        """Serialise ``record`` plus any non-standard attributes to JSON."""
        payload: dict[str, object] = {
            "timestamp": datetime.fromtimestamp(record.created, tz=UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": getattr(record, "request_id", None),
        }
        for key, value in record.__dict__.items():
            if key in self._STANDARD_ATTRS or key.startswith("_"):
                continue
            payload[key] = value
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


class RequestIdFilter(logging.Filter):
    """Inject the current request id onto every log record."""

    def filter(self, record: logging.LogRecord) -> bool:
        """Always pass — this filter only annotates ``record.request_id``."""
        if not hasattr(record, "request_id"):
            record.request_id = get_request_id()
        return True


def configure_logging() -> None:
    """Install the JSON handler on the root logger. Idempotent."""
    root = logging.getLogger()
    for existing in root.handlers:
        if existing.name == _HANDLER_NAME:
            return

    handler = logging.StreamHandler()
    handler.set_name(_HANDLER_NAME)
    handler.setFormatter(_JsonFormatter())
    handler.addFilter(RequestIdFilter())
    root.addHandler(handler)

    if root.level == logging.WARNING or root.level == logging.NOTSET:
        root.setLevel(logging.INFO)


# --- Middleware -------------------------------------------------------------


class RequestLifecycleMiddleware(BaseHTTPMiddleware):
    """Assigns a request id, emits one access-log line, echoes the header.

    The middleware runs around the entire request — error responses go
    through the same path so the lifecycle log fires and the response
    carries ``X-Request-ID`` even on 4xx / 5xx.
    """

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)
        self._logger = logging.getLogger(_LIFECYCLE_LOGGER)

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        """Run a single request through the lifecycle log + id-echo path."""
        inbound_id = request.headers.get(REQUEST_ID_HEADER)
        request_id = inbound_id or uuid.uuid4().hex
        token = _request_id_var.set(request_id)
        start = time.perf_counter()
        status_code = 500

        try:
            response: Response = await call_next(request)
            status_code = response.status_code
            response.headers[REQUEST_ID_HEADER] = request_id
            return response
        except Exception:
            self._logger.exception(
                "Unhandled exception during request.",
                extra={
                    "method": request.method,
                    "path": request.url.path,
                    "status_code": 500,
                    "request_id": request_id,
                    "duration_ms": int((time.perf_counter() - start) * 1000),
                },
            )
            raise
        finally:
            duration_ms = int((time.perf_counter() - start) * 1000)
            level = logging.INFO
            if 400 <= status_code < 500:
                level = logging.WARNING
            elif status_code >= 500:
                level = logging.ERROR
            self._logger.log(
                level,
                "request.complete",
                extra={
                    "method": request.method,
                    "path": request.url.path,
                    "status_code": status_code,
                    "duration_ms": duration_ms,
                    "request_id": request_id,
                },
            )
            _request_id_var.reset(token)


def install_observability(app: FastAPI) -> None:
    """Attach the middleware and ensure JSON logging is configured."""
    configure_logging()
    app.add_middleware(RequestLifecycleMiddleware)
