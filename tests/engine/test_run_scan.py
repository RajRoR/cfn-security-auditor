"""Integration tests for the engine: clean / medium / critical oracle templates.

Each test runs ``run_scan`` against a fixture under ``tests/fixtures/`` and
asserts both the persisted finding set (by ``(rule_id, resource_logical_id)``)
and the finalised severity counters on the Scan row.
"""

from collections import Counter
from pathlib import Path

import pytest
from sqlmodel import Session, select

from cfn_auditor.engine import run_scan
from cfn_auditor.models import Finding, Scan, ScanStatus
from cfn_auditor.parser import (
    MalformedTemplateError,
    NotACloudFormationTemplateError,
    TemplateTooLargeError,
)


def _load(fixtures_dir: Path, name: str) -> str:
    return (fixtures_dir / name).read_text(encoding="utf-8")


def _finding_keys(scan: Scan) -> set[tuple[str, str]]:
    return {(f.rule_id, f.resource_logical_id) for f in scan.findings}


def _counts_by_severity(scan: Scan) -> dict[str, int]:
    return Counter(f.severity.value for f in scan.findings)


# ---------------------------------------------------------------------------
# Clean
# ---------------------------------------------------------------------------


def test_clean_template_yields_no_findings(session: Session, fixtures_dir: Path) -> None:
    """A fully-compliant template produces zero findings and zero counters."""
    scan = run_scan(_load(fixtures_dir, "clean.yaml"), "clean.yaml", session)

    assert scan.id is not None
    assert scan.status is ScanStatus.SUCCEEDED
    assert scan.template_name == "clean.yaml"
    assert scan.findings == []
    assert scan.finding_count == 0
    assert scan.critical_count == 0
    assert scan.high_count == 0
    assert scan.medium_count == 0
    assert scan.low_count == 0
    assert scan.info_count == 0


# ---------------------------------------------------------------------------
# Medium
# ---------------------------------------------------------------------------


def test_medium_template_finding_set_and_counters(session: Session, fixtures_dir: Path) -> None:
    """Medium oracle: precise finding set + finalised severity counters."""
    scan = run_scan(_load(fixtures_dir, "medium.yaml"), "medium.yaml", session)

    expected = {
        ("CFN_IAM_002", "ScopedActionPolicy"),
        ("CFN_CT_001", "AppTrail"),
        ("CFN_EC2_001", "ScratchVolume"),
        ("CFN_SG_001", "WebSecurityGroup"),
    }
    assert _finding_keys(scan) == expected
    assert _counts_by_severity(scan) == {"MEDIUM": 3, "HIGH": 1}

    assert scan.finding_count == 4
    assert scan.critical_count == 0
    assert scan.high_count == 1
    assert scan.medium_count == 3
    assert scan.low_count == 0


def test_findings_carry_resource_type(session: Session, fixtures_dir: Path) -> None:
    """Each persisted Finding records the resource_type from the source resource."""
    scan = run_scan(_load(fixtures_dir, "medium.yaml"), "medium.yaml", session)
    types_by_logical_id = {
        (f.rule_id, f.resource_logical_id): f.resource_type for f in scan.findings
    }
    assert types_by_logical_id[("CFN_IAM_002", "ScopedActionPolicy")] == "AWS::IAM::Policy"
    assert types_by_logical_id[("CFN_CT_001", "AppTrail")] == "AWS::CloudTrail::Trail"
    assert types_by_logical_id[("CFN_EC2_001", "ScratchVolume")] == "AWS::EC2::Volume"
    assert types_by_logical_id[("CFN_SG_001", "WebSecurityGroup")] == "AWS::EC2::SecurityGroup"


# ---------------------------------------------------------------------------
# Critical
# ---------------------------------------------------------------------------


def test_critical_template_finding_set_and_counters(session: Session, fixtures_dir: Path) -> None:
    """Critical oracle: at least one CRITICAL, exact finding-set match."""
    scan = run_scan(_load(fixtures_dir, "critical.yaml"), "critical.yaml", session)

    expected = {
        ("CFN_S3_001", "PublicBucket"),
        ("CFN_S3_002", "PublicBucket"),
        ("CFN_S3_003", "PublicBucket"),
        ("CFN_SG_001", "SshOpenSecurityGroup"),
        ("CFN_IAM_001", "AdminPolicy"),
        ("CFN_IAM_002", "AdminPolicy"),
        ("CFN_RDS_001", "PublicDb"),
        ("CFN_RDS_002", "PublicDb"),
    }
    assert _finding_keys(scan) == expected
    assert scan.critical_count >= 1
    assert _counts_by_severity(scan) == {
        "CRITICAL": 4,  # S3-002, S3-003, SG-001 (escalated), RDS-002
        "HIGH": 3,  # S3-001, IAM-001, RDS-001
        "MEDIUM": 1,  # IAM-002
    }
    assert scan.finding_count == 8
    assert scan.critical_count == 4
    assert scan.high_count == 3
    assert scan.medium_count == 1


# ---------------------------------------------------------------------------
# Persistence: scan + findings round-trip through the session
# ---------------------------------------------------------------------------


def test_scan_and_findings_persist_and_relate(session: Session, fixtures_dir: Path) -> None:
    """Findings persist with the Scan FK and load back via the relationship."""
    scan = run_scan(_load(fixtures_dir, "medium.yaml"), "medium.yaml", session)
    scan_id = scan.id
    assert scan_id is not None

    loaded_findings = session.exec(select(Finding).where(Finding.scan_id == scan_id)).all()
    assert len(loaded_findings) == scan.finding_count

    loaded_scan = session.exec(select(Scan).where(Scan.id == scan_id)).one()
    assert len(loaded_scan.findings) == scan.finding_count


# ---------------------------------------------------------------------------
# Parse failures propagate; the engine does NOT silently persist an empty scan
# ---------------------------------------------------------------------------


def test_malformed_template_propagates(session: Session) -> None:
    """A malformed YAML/JSON input raises and does not persist a Scan."""
    with pytest.raises(MalformedTemplateError):
        run_scan("Resources: : :\n  bad", "bad.yaml", session)
    assert session.exec(select(Scan)).all() == []


def test_missing_resources_propagates(session: Session) -> None:
    """A template with no Resources mapping raises and does not persist."""
    with pytest.raises(NotACloudFormationTemplateError):
        run_scan("Description: docs only\n", "noresources.yaml", session)
    assert session.exec(select(Scan)).all() == []


def test_oversize_propagates(session: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    """An oversized template raises and does not persist."""
    from cfn_auditor.config import get_settings

    monkeypatch.setenv("CFN_AUDITOR_MAX_TEMPLATE_BYTES", "32")
    get_settings.cache_clear()
    try:
        with pytest.raises(TemplateTooLargeError):
            run_scan(
                "Resources:\n  R:\n    Type: AWS::S3::Bucket\n    Properties: {}\n",
                "big.yaml",
                session,
            )
    finally:
        get_settings.cache_clear()
    assert session.exec(select(Scan)).all() == []
