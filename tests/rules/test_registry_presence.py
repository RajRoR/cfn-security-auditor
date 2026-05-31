"""All 10 batch + reference rule ids must be present in the registry.

This guards against a forgotten ``checks/__init__`` import — an unimported
service module silently never registers its rules.
"""

from cfn_auditor.rules import all_rules

EXPECTED_IDS: frozenset[str] = frozenset(
    {
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
)


def test_all_expected_rule_ids_registered() -> None:
    """The registry contains every locked MVP rule id."""
    registered = {rule.id for rule in all_rules()}
    missing = EXPECTED_IDS - registered
    assert not missing, f"Missing rules: {sorted(missing)}"


def test_no_duplicate_rule_ids() -> None:
    """Each rule id appears at most once in the registry."""
    ids = [rule.id for rule in all_rules()]
    assert len(ids) == len(set(ids))
