"""Round-trip a Scan with a Finding through an in-memory SQLite database.

This is the smoke test that validates the foundation: tables create, a Scan
persists, the relationship loads back, and severity counts survive the round
trip. Future PRs will lean on this same pattern via shared fixtures.
"""

from collections.abc import Generator

import pytest
from sqlalchemy.engine import Engine
from sqlmodel import Session, SQLModel, select

from cfn_auditor.db import reset_engine_for_testing
from cfn_auditor.models import Finding, Scan, ScanStatus, Severity


@pytest.fixture
def engine() -> Generator[Engine]:
    """Yield a fresh in-memory SQLite engine with all tables created."""
    test_engine = reset_engine_for_testing("sqlite://")
    SQLModel.metadata.create_all(test_engine)
    try:
        yield test_engine
    finally:
        SQLModel.metadata.drop_all(test_engine)
        test_engine.dispose()


def test_scan_with_finding_round_trip(engine: Engine) -> None:
    """A Scan persisted with one Finding loads back via the relationship."""
    with Session(engine) as session:
        scan = Scan(
            template_name="bucket.yaml",
            status=ScanStatus.SUCCEEDED,
            finding_count=1,
            high_count=1,
        )
        scan.findings.append(
            Finding(
                rule_id="CFN_S3_001",
                severity=Severity.HIGH,
                resource_logical_id="MyBucket",
                resource_type="AWS::S3::Bucket",
                message="S3 bucket allows public read access.",
            )
        )
        session.add(scan)
        session.commit()
        scan_id = scan.id

    assert scan_id is not None

    with Session(engine) as session:
        loaded = session.exec(select(Scan).where(Scan.id == scan_id)).one()
        assert loaded.template_name == "bucket.yaml"
        assert loaded.status is ScanStatus.SUCCEEDED
        assert loaded.finding_count == 1
        assert loaded.high_count == 1
        assert len(loaded.findings) == 1

        finding = loaded.findings[0]
        assert finding.rule_id == "CFN_S3_001"
        assert finding.severity is Severity.HIGH
        assert finding.resource_logical_id == "MyBucket"
        assert finding.resource_type == "AWS::S3::Bucket"
        assert finding.scan_id == scan_id


def test_cascade_delete_removes_findings(engine: Engine) -> None:
    """Deleting a Scan cascades and removes its child Findings."""
    with Session(engine) as session:
        scan = Scan(template_name="cascade.yaml", status=ScanStatus.SUCCEEDED)
        scan.findings.append(
            Finding(
                rule_id="CFN_TEST_001",
                severity=Severity.LOW,
                resource_logical_id="X",
                resource_type="AWS::Test::Thing",
                message="x",
            )
        )
        session.add(scan)
        session.commit()
        session.delete(scan)
        session.commit()

    with Session(engine) as session:
        remaining = session.exec(select(Finding)).all()
        assert remaining == []
