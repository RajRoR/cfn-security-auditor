"""Smoke test: the live app still produces a spec covering every documented path.

This is the regression guard for the committed ``docs/openapi.json``: if a
route is removed or renamed, this test fails before the docs go stale.
"""

from cfn_auditor.api import create_app

EXPECTED_PATHS: frozenset[str] = frozenset(
    {
        "/health",
        "/rules",
        "/scans",
        "/scans/{scan_id}",
        "/scans/{scan_id}/advice",
    }
)


def test_openapi_spec_exposes_every_documented_path() -> None:
    """The generated OpenAPI spec lists every endpoint the README documents."""
    spec = create_app().openapi()
    paths = set(spec.get("paths", {}).keys())
    missing = EXPECTED_PATHS - paths
    assert not missing, f"openapi spec missing paths: {sorted(missing)}"


def test_openapi_spec_has_basic_metadata() -> None:
    """The spec carries the project title and version."""
    spec = create_app().openapi()
    info = spec.get("info", {})
    assert info.get("title") == "CFN Security Auditor"
    assert info.get("version")
