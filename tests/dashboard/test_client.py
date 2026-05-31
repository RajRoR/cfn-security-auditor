"""HTTP client tests with httpx.MockTransport — no live server."""

from typing import Any

import httpx
import pytest

from cfn_auditor.dashboard.client import (
    DEFAULT_API_URL,
    DashboardClient,
    DashboardClientError,
)


def _make_transport(handler: Any) -> httpx.MockTransport:
    return httpx.MockTransport(handler)


def test_client_uses_env_url_when_no_arg(monkeypatch: pytest.MonkeyPatch) -> None:
    """CFN_AUDITOR_API_URL overrides the default."""
    monkeypatch.setenv("CFN_AUDITOR_API_URL", "https://api.example.com")
    captured: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(str(request.url))
        return httpx.Response(200, json={"status": "ok"})

    with DashboardClient(transport=_make_transport(handler), api_key="") as client:
        client.health()

    assert captured == ["https://api.example.com/health"]


def test_client_uses_default_url_when_env_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    """No env var → http://localhost:8000."""
    monkeypatch.delenv("CFN_AUDITOR_API_URL", raising=False)
    captured: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(str(request.url))
        return httpx.Response(200, json={"status": "ok"})

    with DashboardClient(transport=_make_transport(handler), api_key="") as client:
        client.health()

    assert captured[0].startswith(DEFAULT_API_URL)


def test_client_sends_x_api_key_when_configured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """CFN_AUDITOR_API_KEY → X-API-Key header on every request."""
    monkeypatch.setenv("CFN_AUDITOR_API_KEY", "topsecret")
    seen_keys: list[str | None] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen_keys.append(request.headers.get("x-api-key"))
        return httpx.Response(200, json=[])

    with DashboardClient(transport=_make_transport(handler)) as client:
        client.list_rules()

    assert seen_keys == ["topsecret"]


def test_client_omits_x_api_key_when_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    """Without CFN_AUDITOR_API_KEY the header is absent."""
    monkeypatch.delenv("CFN_AUDITOR_API_KEY", raising=False)
    seen_keys: list[str | None] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen_keys.append(request.headers.get("x-api-key"))
        return httpx.Response(200, json=[])

    with DashboardClient(transport=_make_transport(handler)) as client:
        client.list_rules()

    assert seen_keys == [None]


def test_post_scan_returns_decoded_payload() -> None:
    """post_scan returns the JSON body of a 201 response."""
    expected = {
        "id": 7,
        "template_name": "t.yaml",
        "status": "SUCCEEDED",
        "finding_count": 0,
        "critical_count": 0,
        "high_count": 0,
        "medium_count": 0,
        "low_count": 0,
        "info_count": 0,
        "score": {"score": 100, "grade": "A", "passed": True},
        "findings": [],
        "created_at": "2026-05-31T10:00:00Z",
    }

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.url.path == "/scans"
        return httpx.Response(201, json=expected)

    with DashboardClient(transport=_make_transport(handler), api_key="") as client:
        payload = client.post_scan("Resources:\n  R:\n    Type: AWS::S3::Bucket", "t.yaml")

    assert payload == expected


def test_list_scans_passes_pagination_params() -> None:
    """list_scans forwards limit and offset as query parameters."""
    captured: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(str(request.url))
        return httpx.Response(200, json=[])

    with DashboardClient(transport=_make_transport(handler), api_key="") as client:
        client.list_scans(limit=10, offset=20)

    assert "limit=10" in captured[0]
    assert "offset=20" in captured[0]


def test_get_scan_round_trip() -> None:
    """get_scan returns the JSON body for the requested id."""

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/scans/42"
        return httpx.Response(200, json={"id": 42})

    with DashboardClient(transport=_make_transport(handler), api_key="") as client:
        assert client.get_scan(42) == {"id": 42}


def test_list_rules_round_trip() -> None:
    """list_rules returns the rule list."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=[{"id": "CFN_S3_001"}])

    with DashboardClient(transport=_make_transport(handler), api_key="") as client:
        rules = client.list_rules()

    assert rules == [{"id": "CFN_S3_001"}]


@pytest.mark.parametrize(
    ("status_code", "detail"),
    [
        (400, "Template 'bad.yaml' is not valid YAML or JSON."),
        (401, "Invalid or missing API key."),
        (404, "Scan 99 not found."),
        (413, "Template 'big.yaml' exceeds the configured size limit."),
    ],
)
def test_non_2xx_raises_dashboard_client_error(status_code: int, detail: str) -> None:
    """Any non-2xx response surfaces as DashboardClientError carrying the status."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code, json={"detail": detail})

    with (
        DashboardClient(transport=_make_transport(handler), api_key="") as client,
        pytest.raises(DashboardClientError) as excinfo,
    ):
        client.list_rules()

    assert excinfo.value.status_code == status_code
    assert excinfo.value.detail == detail


def test_non_json_error_body_falls_back_to_text() -> None:
    """A non-JSON error body still yields a usable detail string."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="oh no")

    with (
        DashboardClient(transport=_make_transport(handler), api_key="") as client,
        pytest.raises(DashboardClientError) as excinfo,
    ):
        client.list_rules()

    assert excinfo.value.status_code == 500
    assert "oh no" in excinfo.value.detail


def test_close_is_idempotent() -> None:
    """close() can be called explicitly outside the context manager."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"status": "ok"})

    client = DashboardClient(transport=_make_transport(handler), api_key="")
    client.health()
    client.close()
    client.close()  # second call must not raise
