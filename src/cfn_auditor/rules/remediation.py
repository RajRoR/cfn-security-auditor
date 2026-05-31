"""Single source of truth for per-rule remediation guidance.

Each registered guardrail rule has one canonical remediation string keyed
by its stable rule id. The rule classes pull the string from here when
emitting :class:`RuleFinding` instances; the advisor module reads the same
map to drive the static remediation provider. One literal, two readers — no
divergence.

This module is a **leaf**: it imports nothing from the rest of the project.
That keeps both ``rules`` and ``advisor`` importable without cycles.

When adding a new rule:
  1. Add its ``id`` and remediation string here.
  2. Reference it from the rule class.
  3. The advisor picks it up automatically.

Conversely, deleting a rule must delete its entry here so unused remediation
strings do not rot in the codebase.
"""

from typing import Final

__all__ = ["REMEDIATION_BY_RULE_ID", "remediation_for"]


REMEDIATION_BY_RULE_ID: Final[dict[str, str]] = {
    "CFN_S3_001": (
        "Add a BucketEncryption.ServerSideEncryptionConfiguration block "
        "with an SSEAlgorithm of AES256 or aws:kms."
    ),
    "CFN_S3_002": (
        "Ensure PublicAccessBlockConfiguration is present and that all four "
        "flags (BlockPublicAcls, IgnorePublicAcls, BlockPublicPolicy, "
        "RestrictPublicBuckets) are set to true."
    ),
    "CFN_S3_003": (
        "Remove the AccessControl canned ACL or set it to 'Private'. "
        "Configure access via bucket policies and PublicAccessBlockConfiguration."
    ),
    "CFN_SG_001": (
        "Restrict CidrIp/CidrIpv6 to a known network range and limit the "
        "port range to the smallest set required."
    ),
    "CFN_IAM_001": (
        "Replace Action '*' with the explicit set of API actions " "the principal must perform."
    ),
    "CFN_IAM_002": (
        "Replace Resource '*' with explicit ARNs scoped to the "
        "objects the principal must access."
    ),
    "CFN_RDS_001": (
        "Set StorageEncrypted to true and supply a KmsKeyId for a "
        "customer-managed key when required."
    ),
    "CFN_RDS_002": ("Set PubliclyAccessible to false and place the instance in a private subnet."),
    "CFN_EC2_001": (
        "Set Encrypted to true and supply a KmsKeyId for a customer-managed " "key when required."
    ),
    "CFN_CT_001": "Set KMSKeyId to the ARN of a CMK to encrypt CloudTrail log files.",
}


def remediation_for(rule_id: str) -> str:
    """Return the canonical remediation string for ``rule_id``.

    Raises:
        KeyError: when no remediation is registered for ``rule_id``. This is
            a programmer error — every registered rule must have an entry in
            :data:`REMEDIATION_BY_RULE_ID`.
    """
    return REMEDIATION_BY_RULE_ID[rule_id]
