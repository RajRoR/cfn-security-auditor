"""EC2 / EBS guardrails."""

from typing import ClassVar

from cfn_auditor.parser import Resource, Template
from cfn_auditor.rules.base import Rule
from cfn_auditor.rules.finding import RuleFinding
from cfn_auditor.rules.intrinsics import literal_or_none
from cfn_auditor.rules.registry import register
from cfn_auditor.rules.remediation import remediation_for
from cfn_auditor.rules.severity import Severity

__all__ = ["EbsVolumeNotEncrypted"]


@register
class EbsVolumeNotEncrypted(Rule):
    """CFN_EC2_001 — EBS volume has Encrypted false or absent.

    Fires when ``Encrypted`` is missing or literally ``false``. An
    unresolved intrinsic on the property does not fire.
    """

    id: ClassVar[str] = "CFN_EC2_001"
    title: ClassVar[str] = "EBS volume is not encrypted at rest"
    severity: ClassVar[Severity] = Severity.MEDIUM
    resource_types: ClassVar[frozenset[str]] = frozenset({"AWS::EC2::Volume"})

    def evaluate(self, resource: Resource, template: Template) -> list[RuleFinding]:
        """Fire on missing or literally-false ``Encrypted``."""
        if "Encrypted" not in resource.properties:
            return self._fire(resource, "absent")
        value = literal_or_none(resource.properties["Encrypted"])
        if value is None:
            return []
        if value is False:
            return self._fire(resource, "literally false")
        return []

    def _fire(self, resource: Resource, why: str) -> list[RuleFinding]:
        return [
            RuleFinding(
                rule_id=self.id,
                severity=self.severity,
                resource_logical_id=resource.logical_id,
                message=(
                    f"EBS volume {resource.logical_id!r} has Encrypted {why}; "
                    "data at rest is not encrypted."
                ),
                remediation=remediation_for(self.id),
            )
        ]
