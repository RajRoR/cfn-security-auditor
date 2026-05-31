"""StaticRemediationProvider unit tests + factory selection."""

from cfn_auditor.advisor import (
    FindingInput,
    StaticRemediationProvider,
    get_provider,
)
from cfn_auditor.models import Severity
from cfn_auditor.rules.remediation import REMEDIATION_BY_RULE_ID


def _input(rule_id: str, *, finding_id: int = 1) -> FindingInput:
    return FindingInput(
        finding_id=finding_id,
        rule_id=rule_id,
        severity=Severity.HIGH,
        resource_logical_id="R",
        resource_type="AWS::Test::Thing",
        message="m",
    )


def test_known_rule_ids_resolve_to_canonical_remediation() -> None:
    """Every registered rule id has a non-empty remediation in the map."""
    provider = StaticRemediationProvider()
    inputs = [_input(rid, finding_id=i) for i, rid in enumerate(REMEDIATION_BY_RULE_ID)]
    items = provider.advise(inputs)

    assert len(items) == len(REMEDIATION_BY_RULE_ID)
    for item in items:
        expected = REMEDIATION_BY_RULE_ID[item.rule_id]
        assert item.remediation == expected
        assert item.source == "static"


def test_provider_preserves_input_order() -> None:
    """``advise`` returns items in the same order as the input iterable."""
    provider = StaticRemediationProvider()
    ordered_ids = ["CFN_S3_001", "CFN_RDS_002", "CFN_CT_001"]
    inputs = [_input(rid, finding_id=i) for i, rid in enumerate(ordered_ids)]
    items = provider.advise(inputs)
    assert [it.rule_id for it in items] == ordered_ids
    assert [it.finding_id for it in items] == [0, 1, 2]


def test_unknown_rule_id_falls_back_to_explicit_message() -> None:
    """Unknown ids surface a clear fallback string — no crash, no empty remediation."""
    provider = StaticRemediationProvider()
    items = provider.advise([_input("CFN_TEST_UNKNOWN")])
    assert len(items) == 1
    assert items[0].remediation
    assert "manually" in items[0].remediation.lower()


def test_provider_echoes_metadata_for_client_convenience() -> None:
    """rule_id, severity, resource_logical_id, message ride along on each item."""
    provider = StaticRemediationProvider()
    findings = [
        FindingInput(
            finding_id=42,
            rule_id="CFN_S3_001",
            severity=Severity.HIGH,
            resource_logical_id="MyBucket",
            resource_type="AWS::S3::Bucket",
            message="No encryption.",
        ),
    ]
    item = provider.advise(findings)[0]
    assert item.finding_id == 42
    assert item.severity is Severity.HIGH
    assert item.resource_logical_id == "MyBucket"
    assert item.message == "No encryption."


def test_factory_returns_static_when_no_llm_configured() -> None:
    """``get_provider`` falls back to the static provider when nothing is set."""
    provider = get_provider()
    assert isinstance(provider, StaticRemediationProvider)
    assert provider.name == "static"
