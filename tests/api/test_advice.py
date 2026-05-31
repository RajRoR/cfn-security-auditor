"""End-to-end tests for GET /scans/{id}/advice through the get_session seam."""

from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from cfn_auditor.config import get_settings
from cfn_auditor.rules.remediation import REMEDIATION_BY_RULE_ID


@pytest.fixture
def fixtures_dir() -> Path:
    return Path(__file__).resolve().parent.parent / "fixtures"


def _post(client: TestClient, fixtures_dir: Path, fixture: str) -> dict[str, Any]:
    body = {
        "template": (fixtures_dir / fixture).read_text(encoding="utf-8"),
        "name": fixture,
    }
    response = client.post("/scans", json=body)
    assert response.status_code == 201, response.text
    payload: dict[str, Any] = response.json()
    return payload


def test_advice_round_trip_for_critical_oracle(client: TestClient, fixtures_dir: Path) -> None:
    """Every finding on the critical oracle gets a non-empty static remediation."""
    scan = _post(client, fixtures_dir, "critical.yaml")
    response = client.get(f"/scans/{scan['id']}/advice")
    assert response.status_code == 200
    payload = response.json()

    assert payload["scan_id"] == scan["id"]
    assert payload["provider"] == "static"

    expected_count = scan["finding_count"]
    assert len(payload["items"]) == expected_count

    for item in payload["items"]:
        assert item["remediation"]
        # All ten MVP rules are in the canonical map; advice must match.
        assert item["remediation"] == REMEDIATION_BY_RULE_ID[item["rule_id"]]
        assert item["source"] == "static"
        for key in (
            "finding_id",
            "rule_id",
            "severity",
            "resource_logical_id",
            "message",
        ):
            assert key in item


def test_advice_for_clean_scan_is_empty_list(client: TestClient, fixtures_dir: Path) -> None:
    """A scan with zero findings yields an empty advice list, still 200."""
    scan = _post(client, fixtures_dir, "clean.yaml")
    response = client.get(f"/scans/{scan['id']}/advice")
    assert response.status_code == 200
    payload = response.json()
    assert payload["items"] == []
    assert payload["provider"] == "static"


def test_advice_404_does_not_echo_template_content(client: TestClient) -> None:
    """A missing scan returns 404; the body contains no template content."""
    response = client.get("/scans/99999/advice")
    assert response.status_code == 404
    body_text = response.text
    assert body_text  # there is *some* error body
    for forbidden in ("Resources:", "AWS::", "BucketName", "Properties"):
        assert forbidden not in body_text


def test_advice_requires_api_key_when_configured(
    client: TestClient, fixtures_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The advice route is gated by require_api_key (mirrors /rules + /scans)."""
    scan = _post(client, fixtures_dir, "medium.yaml")
    monkeypatch.setenv("CFN_AUDITOR_API_KEY", "topsecret")
    get_settings.cache_clear()
    try:
        unauth = client.get(f"/scans/{scan['id']}/advice")
        assert unauth.status_code == 401

        ok = client.get(
            f"/scans/{scan['id']}/advice",
            headers={"X-API-Key": "topsecret"},
        )
        assert ok.status_code == 200
        assert ok.json()["provider"] == "static"
    finally:
        get_settings.cache_clear()
