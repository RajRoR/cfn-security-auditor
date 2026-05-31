"""GET /rules returns the in-process rule registry, gated by optional API key."""

import pytest
from fastapi.testclient import TestClient

from cfn_auditor.config import get_settings

EXPECTED_RULE_IDS = {
    "CFN_S3_001",
    "CFN_S3_002",
    "CFN_S3_003",
    "CFN_SG_001",
    "CFN_IAM_001",
    "CFN_IAM_002",
    "CFN_RDS_001",
    "CFN_RDS_002",
    "CFN_EC2_001",
    "CFN_CT_001",
}


def test_rules_returns_full_registry_in_dev_mode(client: TestClient) -> None:
    """With CFN_AUDITOR_API_KEY unset the endpoint is open and returns every rule."""
    response = client.get("/rules")
    assert response.status_code == 200
    payload = response.json()
    ids = {rule["id"] for rule in payload}
    assert ids >= EXPECTED_RULE_IDS


def test_rules_payload_shape(client: TestClient) -> None:
    """Each rule carries id, title, severity, resource_types (sorted list)."""
    response = client.get("/rules")
    payload = response.json()
    by_id = {rule["id"]: rule for rule in payload}

    s3_001 = by_id["CFN_S3_001"]
    assert s3_001["severity"] == "HIGH"
    assert s3_001["resource_types"] == ["AWS::S3::Bucket"]
    assert isinstance(s3_001["title"], str) and s3_001["title"]

    sg_001 = by_id["CFN_SG_001"]
    assert sg_001["severity"] == "HIGH"
    assert sg_001["resource_types"] == ["AWS::EC2::SecurityGroup"]

    iam_001 = by_id["CFN_IAM_001"]
    assert iam_001["severity"] == "HIGH"
    assert set(iam_001["resource_types"]) == {
        "AWS::IAM::Group",
        "AWS::IAM::ManagedPolicy",
        "AWS::IAM::Policy",
        "AWS::IAM::Role",
        "AWS::IAM::User",
    }
    assert iam_001["resource_types"] == sorted(iam_001["resource_types"])


def test_rules_does_not_leak_remediation_field(client: TestClient) -> None:
    """Remediation is per-finding, not per-rule. /rules must not expose it."""
    response = client.get("/rules")
    for rule in response.json():
        assert "remediation" not in rule


def test_rules_requires_api_key_when_configured(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """When CFN_AUDITOR_API_KEY is set, /rules returns 401 without X-API-Key."""
    monkeypatch.setenv("CFN_AUDITOR_API_KEY", "topsecret")
    get_settings.cache_clear()
    try:
        unauth = client.get("/rules")
        assert unauth.status_code == 401
        assert unauth.json()["detail"] == "Invalid or missing API key."
        # WWW-Authenticate is reserved for IANA HTTP auth schemes; X-API-Key
        # is not one. The 401 must NOT carry a non-standard challenge header.
        assert "WWW-Authenticate" not in unauth.headers

        wrong = client.get("/rules", headers={"X-API-Key": "wrong"})
        assert wrong.status_code == 401

        ok = client.get("/rules", headers={"X-API-Key": "topsecret"})
        assert ok.status_code == 200
        ids = {rule["id"] for rule in ok.json()}
        assert ids >= EXPECTED_RULE_IDS
    finally:
        get_settings.cache_clear()
