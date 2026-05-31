"""S3 bucket guardrails."""

from typing import ClassVar

from cfn_auditor.parser import Resource, Template
from cfn_auditor.rules.base import Rule
from cfn_auditor.rules.finding import RuleFinding
from cfn_auditor.rules.registry import register
from cfn_auditor.rules.severity import Severity

__all__ = ["S3MissingBucketEncryption"]


@register
class S3MissingBucketEncryption(Rule):
    """CFN_S3_001 — S3 bucket has no BucketEncryption configured.

    Without ``BucketEncryption``, objects written to the bucket are not
    encrypted at rest by a server-side encryption rule, leaving operators
    relying on AWS account-level defaults that may not exist.

    This is a **pure absence check**: a present ``BucketEncryption`` is a
    pass regardless of whether its value is a literal or an unresolved
    intrinsic. The tests still cover the intrinsic case to document that we
    do not false-positive when encryption is defined via ``!If`` or ``!Ref``.
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
                remediation=(
                    "Add a BucketEncryption.ServerSideEncryptionConfiguration block "
                    "with an SSEAlgorithm of AES256 or aws:kms."
                ),
            )
        ]
