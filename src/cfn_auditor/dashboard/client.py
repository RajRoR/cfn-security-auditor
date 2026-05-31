"""HTTP client + pure transforms for the Streamlit dashboard.

This module is import-clean: it depends only on ``httpx`` and the standard
library. It must NOT import the engine, rules, scoring, or db. The dashboard
is a real client of the HTTP API — that's how the layering stays honest.

Configuration is read from the environment so the same app can run against
local dev (default) or a remote deployment without code changes:

  * ``CFN_AUDITOR_API_URL`` — base URL, default ``http://localhost:8000``.
  * ``CFN_AUDITOR_API_KEY`` — sent as ``X-API-Key`` when set; omitted when not.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

import httpx

__all__ = [
    "DEFAULT_API_URL",
    "SEVERITY_COLORS",
    "AdviceDisplay",
    "AdviceRow",
    "DashboardClient",
    "DashboardClientError",
    "FindingRow",
    "ScanDisplay",
    "TrendPoint",
    "build_advice_display",
    "build_findings_rows",
    "build_trend_series",
    "severity_color",
]


DEFAULT_API_URL = "http://localhost:8000"

# Severity → CSS hex colour. Centralised so the table, the badge, and any
# future visual all share one palette.
SEVERITY_COLORS: dict[str, str] = {
    "CRITICAL": "#b71c1c",
    "HIGH": "#e53935",
    "MEDIUM": "#fb8c00",
    "LOW": "#fdd835",
    "INFO": "#1e88e5",
}


class DashboardClientError(RuntimeError):
    """Surfaced when the API returns a non-2xx response.

    The dashboard maps these onto Streamlit error/warning messages without
    crashing. The status code is preserved on the instance so the UI can
    differentiate (e.g. 401 → "set CFN_AUDITOR_API_KEY", 413 → "too large").
    """

    def __init__(self, status_code: int, detail: str) -> None:
        super().__init__(f"API returned {status_code}: {detail}")
        self.status_code = status_code
        self.detail = detail


@dataclass(frozen=True)
class FindingRow:
    """A flattened finding suitable for table rendering."""

    id: int
    rule_id: str
    severity: str
    resource: str
    message: str
    color: str


@dataclass(frozen=True)
class ScanDisplay:
    """Compact view-model for a single scan."""

    id: int
    template_name: str
    status: str
    score: int
    grade: str
    passed: bool
    finding_count: int
    critical_count: int
    high_count: int
    medium_count: int
    low_count: int
    info_count: int


@dataclass(frozen=True)
class TrendPoint:
    """One point on the score-over-time trend."""

    scan_id: int
    created_at: str
    score: int
    grade: str
    passed: bool


@dataclass(frozen=True)
class AdviceRow:
    """One per-finding remediation row, ready for the Streamlit table."""

    finding_id: int
    rule_id: str
    severity: str
    resource: str
    message: str
    remediation: str
    source: str
    color: str


@dataclass(frozen=True)
class AdviceDisplay:
    """View-model for the remediation panel: provider label + rows."""

    scan_id: int
    provider: str
    rows: list[AdviceRow]


# ---------------------------------------------------------------------------
# Pure transforms (no I/O, no Streamlit) — easy to unit-test.
# ---------------------------------------------------------------------------


def severity_color(severity: str) -> str:
    """Return the table-cell colour for ``severity``; falls back to grey."""
    return SEVERITY_COLORS.get(severity, "#9e9e9e")


def build_findings_rows(scan_payload: dict[str, Any]) -> list[FindingRow]:
    """Project a ``ScanDetailResponse`` payload into table rows.

    Findings are sorted by severity (CRITICAL first), then rule_id, then
    resource_logical_id — deterministic and reader-friendly.
    """
    severity_rank = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3, "INFO": 4}
    raw = scan_payload.get("findings", [])
    rows = [
        FindingRow(
            id=f["id"],
            rule_id=f["rule_id"],
            severity=f["severity"],
            resource=f["resource_logical_id"],
            message=f["message"],
            color=severity_color(f["severity"]),
        )
        for f in raw
    ]
    rows.sort(
        key=lambda r: (
            severity_rank.get(r.severity, 99),
            r.rule_id,
            r.resource,
        )
    )
    return rows


def build_scan_display(scan_payload: dict[str, Any]) -> ScanDisplay:
    """Compress a scan payload into a :class:`ScanDisplay` view-model."""
    score = scan_payload["score"]
    return ScanDisplay(
        id=scan_payload["id"],
        template_name=scan_payload["template_name"],
        status=scan_payload["status"],
        score=score["score"],
        grade=score["grade"],
        passed=score["passed"],
        finding_count=scan_payload["finding_count"],
        critical_count=scan_payload["critical_count"],
        high_count=scan_payload["high_count"],
        medium_count=scan_payload["medium_count"],
        low_count=scan_payload["low_count"],
        info_count=scan_payload["info_count"],
    )


def build_trend_series(history: list[dict[str, Any]]) -> list[TrendPoint]:
    """Project a list of scan summaries into a chronological trend series.

    The API returns scans newest-first; the trend is rendered oldest-first so
    a chart x-axis reads left-to-right in time order. Ties on ``created_at``
    are broken by ``id`` ascending — deterministic.
    """
    points = [
        TrendPoint(
            scan_id=row["id"],
            created_at=row["created_at"],
            score=row["score"]["score"],
            grade=row["score"]["grade"],
            passed=row["score"]["passed"],
        )
        for row in history
    ]
    points.sort(key=lambda p: (p.created_at, p.scan_id))
    return points


def build_advice_display(advice_payload: dict[str, Any]) -> AdviceDisplay:
    """Project an ``AdviceResponse`` payload into the panel view-model.

    The API returns items in finding order; we preserve that order so the
    advice table aligns with the findings table the user is already reading.
    Severity colour is derived from the shared :data:`SEVERITY_COLORS` map —
    no second palette in the dashboard.
    """
    raw_items = advice_payload.get("items", [])
    rows = [
        AdviceRow(
            finding_id=item["finding_id"],
            rule_id=item["rule_id"],
            severity=item["severity"],
            resource=item["resource_logical_id"],
            message=item["message"],
            remediation=item["remediation"],
            source=item["source"],
            color=severity_color(item["severity"]),
        )
        for item in raw_items
    ]
    return AdviceDisplay(
        scan_id=advice_payload["scan_id"],
        provider=advice_payload["provider"],
        rows=rows,
    )


# ---------------------------------------------------------------------------
# HTTP client — narrow surface, raises DashboardClientError on non-2xx.
# ---------------------------------------------------------------------------


class DashboardClient:
    """Thin wrapper around the API. Reads URL + API key from the environment."""

    def __init__(
        self,
        *,
        base_url: str | None = None,
        api_key: str | None = None,
        transport: httpx.BaseTransport | None = None,
        timeout: float = 30.0,
    ) -> None:
        resolved_url = base_url or os.environ.get("CFN_AUDITOR_API_URL", DEFAULT_API_URL)
        # Distinguish "explicitly opted out" (api_key="") from "not provided"
        # (api_key=None falls back to the env). Empty string disables the
        # header entirely so tests can opt out without unsetting an env var.
        if api_key is None:
            resolved_key: str | None = os.environ.get("CFN_AUDITOR_API_KEY")
        else:
            resolved_key = api_key or None

        headers: dict[str, str] = {}
        if resolved_key:
            headers["X-API-Key"] = resolved_key

        self._client = httpx.Client(
            base_url=resolved_url,
            headers=headers,
            timeout=timeout,
            transport=transport,
        )

    # Context-manager protocol so callers can ``with DashboardClient() as c:``.
    def __enter__(self) -> DashboardClient:
        return self

    def __exit__(self, *exc: object) -> None:
        self._client.close()

    def close(self) -> None:
        """Close the underlying ``httpx.Client``."""
        self._client.close()

    # --- API methods ---------------------------------------------------------

    def health(self) -> dict[str, Any]:
        """GET /health."""
        payload = self._json(self._client.get("/health"))
        assert isinstance(payload, dict)
        return payload

    def list_rules(self) -> list[dict[str, Any]]:
        """GET /rules."""
        payload = self._json(self._client.get("/rules"))
        assert isinstance(payload, list)
        return payload

    def post_scan(self, template: str, name: str = "template") -> dict[str, Any]:
        """POST /scans with ``{"template": ..., "name": ...}``."""
        payload = self._json(self._client.post("/scans", json={"template": template, "name": name}))
        assert isinstance(payload, dict)
        return payload

    def list_scans(self, *, limit: int = 50, offset: int = 0) -> list[dict[str, Any]]:
        """GET /scans?limit&offset."""
        payload = self._json(self._client.get("/scans", params={"limit": limit, "offset": offset}))
        assert isinstance(payload, list)
        return payload

    def get_scan(self, scan_id: int) -> dict[str, Any]:
        """GET /scans/{id}."""
        payload = self._json(self._client.get(f"/scans/{scan_id}"))
        assert isinstance(payload, dict)
        return payload

    def get_advice(self, scan_id: int) -> dict[str, Any]:
        """GET /scans/{id}/advice — per-finding remediation."""
        payload = self._json(self._client.get(f"/scans/{scan_id}/advice"))
        assert isinstance(payload, dict)
        return payload

    # --- internals -----------------------------------------------------------

    @staticmethod
    def _json(response: httpx.Response) -> Any:
        """Return the JSON body or raise :class:`DashboardClientError`."""
        if response.status_code >= 400:
            try:
                detail = response.json().get("detail", response.text)
            except ValueError:
                detail = response.text
            raise DashboardClientError(response.status_code, str(detail))
        return response.json()
