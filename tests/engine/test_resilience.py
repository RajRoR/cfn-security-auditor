"""Resilience: a raising rule must not abort the scan.

The scan continues, the throwing rule yields no finding, every other rule's
findings are still present, and the failure is logged. The deliberately-
throwing rule is added to the registry inside the test fixture and removed
in teardown so registry state does not leak across tests.
"""

from collections.abc import Generator
from pathlib import Path
from typing import ClassVar

import pytest
from sqlmodel import Session

from cfn_auditor.engine import run_scan
from cfn_auditor.parser import Resource, Template
from cfn_auditor.rules import Rule, RuleFinding, Severity
from cfn_auditor.rules.registry import _IDS, _RULES


class _AlwaysRaisingRule(Rule):
    """A rule that always raises — used to exercise the engine's per-rule isolation."""

    id: ClassVar[str] = "CFN_TEST_RAISES"
    title: ClassVar[str] = "deliberately raises"
    severity: ClassVar[Severity] = Severity.HIGH
    resource_types: ClassVar[frozenset[str]] = frozenset({"AWS::S3::Bucket"})

    def evaluate(self, resource: Resource, template: Template) -> list[RuleFinding]:
        raise RuntimeError("intentional test failure")


@pytest.fixture
def throwing_rule_registered() -> Generator[None]:
    """Register ``_AlwaysRaisingRule`` for the duration of the test only."""
    rule = _AlwaysRaisingRule()
    _RULES.append(rule)
    _IDS.add(rule.id)
    try:
        yield
    finally:
        _RULES[:] = [r for r in _RULES if r.id != rule.id]
        _IDS.discard(rule.id)


def test_raising_rule_does_not_abort_scan(
    session: Session,
    fixtures_dir: Path,
    caplog: pytest.LogCaptureFixture,
    throwing_rule_registered: None,
) -> None:
    """The scan completes, the throwing rule yields nothing, others still run."""
    template_text = (fixtures_dir / "critical.yaml").read_text(encoding="utf-8")

    with caplog.at_level("ERROR", logger="cfn_auditor.engine.scanner"):
        scan = run_scan(template_text, "critical.yaml", session)

    # Scan finalised: status SUCCEEDED, counters written.
    assert scan.id is not None
    assert scan.finding_count > 0

    # Throwing rule yielded zero findings.
    assert all(f.rule_id != "CFN_TEST_RAISES" for f in scan.findings)

    # Every non-throwing finding from the critical oracle is still present.
    expected_other = {
        ("CFN_S3_001", "PublicBucket"),
        ("CFN_S3_002", "PublicBucket"),
        ("CFN_S3_003", "PublicBucket"),
        ("CFN_SG_001", "SshOpenSecurityGroup"),
        ("CFN_IAM_001", "AdminPolicy"),
        ("CFN_IAM_002", "AdminPolicy"),
        ("CFN_RDS_001", "PublicDb"),
        ("CFN_RDS_002", "PublicDb"),
    }
    actual = {(f.rule_id, f.resource_logical_id) for f in scan.findings}
    assert expected_other <= actual

    # Failure was logged with rule id + exception type, no template content.
    raising_records = [
        r for r in caplog.records if r.levelname == "ERROR" and "CFN_TEST_RAISES" in r.getMessage()
    ]
    assert raising_records, "Expected an ERROR log naming the throwing rule."
    msg = raising_records[0].getMessage()
    assert "RuntimeError" in msg
    assert "PublicBucket" in msg  # the resource that triggered it
    # Sanity: the log line must not contain template content.
    assert "BucketName" not in msg
    assert "AccessControl" not in msg
