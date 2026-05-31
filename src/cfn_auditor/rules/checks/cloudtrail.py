"""CloudTrail guardrails."""

from typing import ClassVar

from cfn_auditor.parser import Resource, Template
from cfn_auditor.rules.base import Rule
from cfn_auditor.rules.finding import RuleFinding
from cfn_auditor.rules.registry import register
from cfn_auditor.rules.severity import Severity

__all__ = ["CloudTrailMissingKmsKeyId"]


@register
class CloudTrailMissingKmsKeyId(Rule):
    """CFN_CT_001 — CloudTrail trail has no KMSKeyId configured.

    Pure absence check: a present ``KMSKeyId`` is a pass regardless of
    whether the value is a literal or an unresolved intrinsic.
    """

    id: ClassVar[str] = "CFN_CT_001"
    title: ClassVar[str] = "CloudTrail trail is not encrypted with a KMS key"
    severity: ClassVar[Severity] = Severity.MEDIUM
    resource_types: ClassVar[frozenset[str]] = frozenset({"AWS::CloudTrail::Trail"})

    def evaluate(self, resource: Resource, template: Template) -> list[RuleFinding]:
        """Fire when ``KMSKeyId`` is absent."""
        if "KMSKeyId" in resource.properties:
            return []
        return [
            RuleFinding(
                rule_id=self.id,
                severity=self.severity,
                resource_logical_id=resource.logical_id,
                message=(
                    f"CloudTrail trail {resource.logical_id!r} has no KMSKeyId; "
                    "log files are not encrypted with a customer-managed KMS key."
                ),
                remediation=("Set KMSKeyId to the ARN of a CMK to encrypt CloudTrail log files."),
            )
        ]
