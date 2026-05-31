"""Dashboard tests for the advice client method + transform.

No live server, no Streamlit runtime. The HTTP layer is exercised via
``httpx.MockTransport``; the transform is exercised against fixed payloads.
"""

from typing import Any

import httpx
import pytest

from cfn_auditor.dashboard.client import (
    SEVERITY_COLORS,
    AdviceDisplay,
    DashboardClient,
    DashboardClientError,
    build_advice_display,
    severity_color,
)


def _transport(handler: object) -> httpx.MockTransport:
    return httpx.MockTransport(handler)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Transform
# ---------------------------------------------------------------------------


_PAYLOAD: dict[str, Any] = {
    "scan_id": 7,
    "provider": "static",
    "items": [
        {
            "finding_id": 11,
            "rule_id": "CFN_S3_001",
            "severity": "HIGH",
            "resource_logical_id": "Bucket",
            "message": "S3 bucket has no encryption.",
            "remediation": "Add a BucketEncryption.ServerSideEncryptionConfiguration block.",
            "source": "static",
        },
        {
            "finding_id": 12,
            "rule_id": "CFN_RDS_002",
            "severity": "CRITICAL",
            "resource_logical_id": "Db",
            "message": "DB is publicly accessible.",
            "remediation": "Set PubliclyAccessible to false.",
            "source": "static",
        },
        {
            "finding_id": 13,
            "rule_id": "CFN_TEST_UNKNOWN",
            "severity": "INFO",
            "resource_logical_id": "X",
            "message": "synthetic.",
            "remediation": "Review this finding manually.",
            "source": "static",
        },
    ],
}


def test_build_advice_display_preserves_api_order() -> None:
    """The transform does NOT re-sort — it preserves the API's order."""
    display = build_advice_display(_PAYLOAD)
    assert isinstance(display, AdviceDisplay)
    assert [r.finding_id for r in display.rows] == [11, 12, 13]


def test_build_advice_display_surfaces_provider_label() -> None:
    """The provider/source label is exposed verbatim for the UI caption."""
    display = build_advice_display(_PAYLOAD)
    assert display.provider == "static"
    assert display.scan_id == 7


def test_build_advice_display_reuses_shared_severity_palette() -> None:
    """Each row's colour comes from the shared SEVERITY_COLORS map."""
    display = build_advice_display(_PAYLOAD)
    by_id = {r.finding_id: r for r in display.rows}
    assert by_id[11].color == SEVERITY_COLORS["HIGH"]
    assert by_id[12].color == SEVERITY_COLORS["CRITICAL"]
    assert by_id[13].color == SEVERITY_COLORS["INFO"]
    # Sanity: severity_color() and the palette agree.
    assert by_id[11].color == severity_color("HIGH")


def test_build_advice_display_passes_remediation_through_unchanged() -> None:
    """The dashboard never invents text — remediation is whatever the API said."""
    display = build_advice_display(_PAYLOAD)
    by_id = {r.finding_id: r for r in display.rows}
    assert by_id[11].remediation == _PAYLOAD["items"][0]["remediation"]
    # Fallback strings from the static provider also pass through verbatim.
    assert "manually" in by_id[13].remediation


def test_build_advice_display_handles_empty_items() -> None:
    """Clean scans return an empty items list — no error, no synthesis."""
    display = build_advice_display({"scan_id": 1, "provider": "static", "items": []})
    assert display.scan_id == 1
    assert display.provider == "static"
    assert display.rows == []


# ---------------------------------------------------------------------------
# Client method
# ---------------------------------------------------------------------------


def test_get_advice_calls_correct_path() -> None:
    """get_advice hits /scans/{id}/advice and returns the JSON body."""
    captured: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request.url.path)
        return httpx.Response(200, json=_PAYLOAD)

    with DashboardClient(transport=_transport(handler), api_key="") as client:
        result = client.get_advice(7)

    assert captured == ["/scans/7/advice"]
    assert result == _PAYLOAD


def test_get_advice_sends_x_api_key_when_configured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When CFN_AUDITOR_API_KEY is set the X-API-Key header rides on /advice."""
    monkeypatch.setenv("CFN_AUDITOR_API_KEY", "topsecret")
    seen: list[str | None] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.headers.get("x-api-key"))
        return httpx.Response(200, json=_PAYLOAD)

    with DashboardClient(transport=_transport(handler)) as client:
        client.get_advice(1)

    assert seen == ["topsecret"]


def test_get_advice_omits_x_api_key_when_unset(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Without CFN_AUDITOR_API_KEY the header is absent on /advice."""
    monkeypatch.delenv("CFN_AUDITOR_API_KEY", raising=False)
    seen: list[str | None] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.headers.get("x-api-key"))
        return httpx.Response(200, json=_PAYLOAD)

    with DashboardClient(transport=_transport(handler)) as client:
        client.get_advice(1)

    assert seen == [None]


@pytest.mark.parametrize(
    ("status_code", "detail"),
    [(401, "Invalid or missing API key."), (404, "Scan 99 not found.")],
)
def test_get_advice_non_2xx_raises_clean_client_error(status_code: int, detail: str) -> None:
    """4xx responses surface as DashboardClientError — never a crash."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code, json={"detail": detail})

    with (
        DashboardClient(transport=_transport(handler), api_key="") as client,
        pytest.raises(DashboardClientError) as excinfo,
    ):
        client.get_advice(99)

    assert excinfo.value.status_code == status_code
    assert excinfo.value.detail == detail
