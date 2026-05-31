"""Round-trip tests for the scan endpoints.

These tests prove the get_session seam end-to-end: each request opens a
real Session against the in-memory StaticPool engine, the engine persists
through it, and subsequent reads see the rows. Scoring is asserted at the
boundary against the same oracles used by the engine integration tests.
"""

from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from cfn_auditor.config import get_settings


@pytest.fixture
def fixtures_dir() -> Path:
    """Absolute path to ``tests/fixtures``."""
    return Path(__file__).resolve().parent.parent / "fixtures"


def _post_scan(
    client: TestClient,
    fixtures_dir: Path,
    fixture: str,
    *,
    headers: dict[str, str] | None = None,
) -> dict[str, Any]:
    body = {
        "template": (fixtures_dir / fixture).read_text(encoding="utf-8"),
        "name": fixture,
    }
    response = client.post("/scans", json=body, headers=headers or {})
    assert response.status_code == 201, response.text
    payload: dict[str, Any] = response.json()
    return payload


# ---------------------------------------------------------------------------
# Oracle round-trips
# ---------------------------------------------------------------------------


def test_post_scan_clean_oracle(client: TestClient, fixtures_dir: Path) -> None:
    """Clean fixture: zero findings; score 100/A; gate passed."""
    payload = _post_scan(client, fixtures_dir, "clean.yaml")
    assert payload["finding_count"] == 0
    assert payload["findings"] == []
    assert payload["score"] == {"score": 100, "grade": "A", "passed": True}
    assert payload["status"] == "SUCCEEDED"
    assert payload["template_name"] == "clean.yaml"


def test_post_scan_medium_oracle(client: TestClient, fixtures_dir: Path) -> None:
    """Medium fixture: 1 HIGH + 3 MEDIUM; score 50/F; gate passed (no CRITICAL)."""
    payload = _post_scan(client, fixtures_dir, "medium.yaml")
    assert payload["finding_count"] == 4
    assert payload["high_count"] == 1
    assert payload["medium_count"] == 3
    assert payload["critical_count"] == 0
    assert payload["score"] == {"score": 50, "grade": "F", "passed": True}

    keys = {(f["rule_id"], f["resource_logical_id"]) for f in payload["findings"]}
    assert keys == {
        ("CFN_IAM_002", "ScopedActionPolicy"),
        ("CFN_CT_001", "AppTrail"),
        ("CFN_EC2_001", "ScratchVolume"),
        ("CFN_SG_001", "WebSecurityGroup"),
    }


def test_post_scan_critical_oracle(client: TestClient, fixtures_dir: Path) -> None:
    """Critical fixture: 4 CRITICAL + 3 HIGH + 1 MEDIUM; score 0/F; gate failed."""
    payload = _post_scan(client, fixtures_dir, "critical.yaml")
    assert payload["finding_count"] == 8
    assert payload["critical_count"] == 4
    assert payload["high_count"] == 3
    assert payload["medium_count"] == 1
    assert payload["score"] == {"score": 0, "grade": "F", "passed": False}


# ---------------------------------------------------------------------------
# List + detail
# ---------------------------------------------------------------------------


def test_list_scans_newest_first_with_id_secondary(client: TestClient, fixtures_dir: Path) -> None:
    """GET /scans returns newest-first with deterministic id-desc secondary sort."""
    first = _post_scan(client, fixtures_dir, "clean.yaml")
    second = _post_scan(client, fixtures_dir, "medium.yaml")
    third = _post_scan(client, fixtures_dir, "critical.yaml")

    response = client.get("/scans")
    assert response.status_code == 200
    payload = response.json()
    ids = [row["id"] for row in payload]
    assert ids == sorted(ids, reverse=True)
    assert ids[0] == third["id"]
    assert ids[-1] == first["id"]
    # Findings must NOT be on the list response.
    for row in payload:
        assert "findings" not in row
    # Score is on every row (compute-on-read).
    assert all("score" in row for row in payload)
    # Sanity: medium oracle's row carries the documented score envelope.
    medium_rows = [r for r in payload if r["id"] == second["id"]]
    assert medium_rows[0]["score"] == {"score": 50, "grade": "F", "passed": True}


def test_list_scans_pagination(client: TestClient, fixtures_dir: Path) -> None:
    """Limit + offset trim the result set."""
    for _ in range(3):
        _post_scan(client, fixtures_dir, "clean.yaml")

    page1 = client.get("/scans?limit=2&offset=0").json()
    page2 = client.get("/scans?limit=2&offset=2").json()
    assert len(page1) == 2
    assert len(page2) == 1
    assert {r["id"] for r in page1} & {r["id"] for r in page2} == set()


def test_get_scan_detail_round_trips_findings(client: TestClient, fixtures_dir: Path) -> None:
    """GET /scans/{id} returns the persisted findings."""
    created = _post_scan(client, fixtures_dir, "medium.yaml")
    response = client.get(f"/scans/{created['id']}")
    assert response.status_code == 200
    payload = response.json()
    assert payload["id"] == created["id"]
    assert {(f["rule_id"], f["resource_logical_id"]) for f in payload["findings"]} == {
        (f["rule_id"], f["resource_logical_id"]) for f in created["findings"]
    }
    assert payload["score"] == created["score"]


def test_get_scan_404_does_not_echo_template(client: TestClient) -> None:
    """A missing scan returns 404 with no template content in the body."""
    response = client.get("/scans/99999")
    assert response.status_code == 404
    body = response.json()
    assert body["detail"] == "Scan 99999 not found."
    body_text = response.text
    for forbidden in ("Resources:", "AWS::", "BucketName", "Properties"):
        assert forbidden not in body_text


# ---------------------------------------------------------------------------
# Error mapping (no template content in error bodies)
# ---------------------------------------------------------------------------


def test_post_scan_malformed_yaml_returns_400_clean_message(client: TestClient) -> None:
    """Malformed YAML → 400 with a clean message that does not echo the input."""
    response = client.post(
        "/scans",
        json={"template": "Resources: : :\n  bad", "name": "bad.yaml"},
    )
    assert response.status_code == 400
    body_text = response.text
    assert "'bad.yaml'" in body_text
    # The offending content must not appear in the response.
    assert "Resources: : :" not in body_text
    assert "bad" not in body_text.replace("'bad.yaml'", "")


def test_post_scan_no_resources_returns_400(client: TestClient) -> None:
    """Top-level mapping without Resources → 400."""
    response = client.post(
        "/scans",
        json={"template": "Description: docs only\n", "name": "noresources.yaml"},
    )
    assert response.status_code == 400
    body_text = response.text
    assert "Description: docs only" not in body_text


def test_post_scan_oversize_returns_413(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Oversized template → 413."""
    monkeypatch.setenv("CFN_AUDITOR_MAX_TEMPLATE_BYTES", "32")
    get_settings.cache_clear()
    try:
        response = client.post(
            "/scans",
            json={
                "template": ("Resources:\n  R:\n    Type: AWS::S3::Bucket\n    Properties: {}\n"),
                "name": "big.yaml",
            },
        )
        assert response.status_code == 413
        body_text = response.text
        assert "AWS::S3::Bucket" not in body_text
    finally:
        get_settings.cache_clear()


# ---------------------------------------------------------------------------
# Auth: scan endpoints are gated when an API key is configured
# ---------------------------------------------------------------------------


def test_post_scan_requires_api_key_when_configured(
    client: TestClient, fixtures_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """POST /scans honours require_api_key (mirrors /rules)."""
    monkeypatch.setenv("CFN_AUDITOR_API_KEY", "topsecret")
    get_settings.cache_clear()
    try:
        body = {
            "template": (fixtures_dir / "clean.yaml").read_text(encoding="utf-8"),
            "name": "clean.yaml",
        }
        unauth = client.post("/scans", json=body)
        assert unauth.status_code == 401

        ok = client.post("/scans", json=body, headers={"X-API-Key": "topsecret"})
        assert ok.status_code == 201
    finally:
        get_settings.cache_clear()
