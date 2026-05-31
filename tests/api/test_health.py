"""GET /health is open and always returns 200 when the process is up."""

import pytest
from fastapi.testclient import TestClient

from cfn_auditor.config import get_settings


def test_health_returns_ok(client: TestClient) -> None:
    """/health returns 200 with the documented body."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_health_does_not_require_api_key(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """/health is reachable even when CFN_AUDITOR_API_KEY is set."""
    monkeypatch.setenv("CFN_AUDITOR_API_KEY", "topsecret")
    get_settings.cache_clear()
    try:
        response = client.get("/health")
        assert response.status_code == 200
    finally:
        get_settings.cache_clear()
