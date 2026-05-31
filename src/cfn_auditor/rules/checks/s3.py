"""S3 bucket guardrails."""

from typing import ClassVar

from cfn_auditor.parser import Resource, Template
from cfn_auditor.rules.base import Rule
from cfn_auditor.rules.finding import RuleFinding
from cfn_auditor.rules.intrinsics import literal_or_none
from cfn_auditor.rules.registry import register
from cfn_auditor.rules.remediation import remediation_for
from cfn_auditor.rules.severity import Severity

__all__ = [
    "S3MissingBucketEncryption",
    "S3MissingPublicAccessBlock",
    "S3PublicAcl",
]


_PUBLIC_ACCESS_BLOCK_FLAGS: tuple[str, ...] = (
    "BlockPublicAcls",
    "IgnorePublicAcls",
    "BlockPublicPolicy",
    "RestrictPublicBuckets",
)


@register
class S3MissingBucketEncryption(Rule):
    """CFN_S3_001 — S3 bucket has no BucketEncryption configured.

    This is a **pure absence check**: a present ``BucketEncryption`` is a
    pass regardless of whether its value is a literal or an unresolved
    intrinsic. Tests still cover the intrinsic case to document we do not
    false-positive when encryption is defined via ``!If`` or ``!Ref``.
    """

    id: ClassVar[str] = "CFN_S3_001"
    title: ClassVar[str] = "S3 bucket has no BucketEncryption configured"
    severity: ClassVar[Severity] = Severity.HIGH
    resource_types: ClassVar[frozenset[str]] = frozenset({"AWS::S3::Bucket"})

    def evaluate(self, resource: Resource, template: Template) -> list[RuleFinding]:
        """Emit a finding when ``BucketEncryption`` is absent."""
        if "BucketEncryption" in resource.properties:
            return []
        return [
            RuleFinding(
                rule_id=self.id,
                severity=self.severity,
                resource_logical_id=resource.logical_id,
                message=(
                    f"S3 bucket {resource.logical_id!r} does not configure "
                    "BucketEncryption; objects may be stored unencrypted at rest."
                ),
                remediation=remediation_for(self.id),
            )
        ]


@register
class S3MissingPublicAccessBlock(Rule):
    """CFN_S3_002 — Public-access block missing or partially disabled.

    Fires when ``PublicAccessBlockConfiguration`` is absent, or when any of
    ``BlockPublicAcls`` / ``IgnorePublicAcls`` / ``BlockPublicPolicy`` /
    ``RestrictPublicBuckets`` is literally ``false``. Unresolved-intrinsic
    flag values do not fire.
    """

    id: ClassVar[str] = "CFN_S3_002"
    title: ClassVar[str] = "S3 bucket public-access block missing or disabled"
    severity: ClassVar[Severity] = Severity.CRITICAL
    resource_types: ClassVar[frozenset[str]] = frozenset({"AWS::S3::Bucket"})

    def evaluate(self, resource: Resource, template: Template) -> list[RuleFinding]:
        """Fire on missing block, or on any literal-false flag inside the block."""
        block = resource.properties.get("PublicAccessBlockConfiguration")
        if block is None:
            return [
                RuleFinding(
                    rule_id=self.id,
                    severity=self.severity,
                    resource_logical_id=resource.logical_id,
                    message=(
                        f"S3 bucket {resource.logical_id!r} has no "
                        "PublicAccessBlockConfiguration; the bucket may permit public ACLs "
                        "or policies."
                    ),
                    remediation=remediation_for(self.id),
                )
            ]

        if literal_or_none(block) is None or not isinstance(block, dict):
            # Block is an unresolved intrinsic or a non-dict literal we cannot
            # introspect — refuse to assert insecurity.
            return []

        offending: list[str] = []
        for flag in _PUBLIC_ACCESS_BLOCK_FLAGS:
            if flag not in block:
                continue
            value = literal_or_none(block[flag])
            if value is False:
                offending.append(flag)

        if not offending:
            return []
        return [
            RuleFinding(
                rule_id=self.id,
                severity=self.severity,
                resource_logical_id=resource.logical_id,
                message=(
                    f"S3 bucket {resource.logical_id!r} has public-access block flags "
                    f"set to false: {', '.join(offending)}."
                ),
                remediation=remediation_for(self.id),
            )
        ]


@register
class S3PublicAcl(Rule):
    """CFN_S3_003 — Bucket AccessControl is PublicRead or PublicReadWrite.

    Fires only on the literal canned-ACL value. An unresolved-intrinsic
    AccessControl does not fire.
    """

    id: ClassVar[str] = "CFN_S3_003"
    title: ClassVar[str] = "S3 bucket uses public canned ACL"
    severity: ClassVar[Severity] = Severity.CRITICAL
    resource_types: ClassVar[frozenset[str]] = frozenset({"AWS::S3::Bucket"})

    def evaluate(self, resource: Resource, template: Template) -> list[RuleFinding]:
        """Fire when ``AccessControl`` is literally ``PublicRead`` or ``PublicReadWrite``."""
        access_control = literal_or_none(resource.properties.get("AccessControl"))
        if access_control not in {"PublicRead", "PublicReadWrite"}:
            return []
        return [
            RuleFinding(
                rule_id=self.id,
                severity=self.severity,
                resource_logical_id=resource.logical_id,
                message=(
                    f"S3 bucket {resource.logical_id!r} grants "
                    f"{access_control!r} via canned ACL — the bucket is publicly readable."
                ),
                remediation=remediation_for(self.id),
            )
        ]
