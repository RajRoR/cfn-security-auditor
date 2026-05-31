"""RDS database guardrails."""

from typing import ClassVar

from cfn_auditor.parser import Resource, Template
from cfn_auditor.rules.base import Rule
from cfn_auditor.rules.finding import RuleFinding
from cfn_auditor.rules.intrinsics import literal_or_none
from cfn_auditor.rules.registry import register
from cfn_auditor.rules.remediation import remediation_for
from cfn_auditor.rules.severity import Severity

__all__ = ["RdsPubliclyAccessible", "RdsStorageNotEncrypted"]


@register
class RdsStorageNotEncrypted(Rule):
    """CFN_RDS_001 — DB instance has StorageEncrypted false or absent.

    Fires when ``StorageEncrypted`` is missing or literally ``false``. An
    unresolved intrinsic on the property does not fire.
    """

    id: ClassVar[str] = "CFN_RDS_001"
    title: ClassVar[str] = "RDS DB instance is not encrypted at rest"
    severity: ClassVar[Severity] = Severity.HIGH
    resource_types: ClassVar[frozenset[str]] = frozenset({"AWS::RDS::DBInstance"})

    def evaluate(self, resource: Resource, template: Template) -> list[RuleFinding]:
        """Fire on missing or literally-false ``StorageEncrypted``."""
        if "StorageEncrypted" not in resource.properties:
            return self._fire(resource, "absent")
        value = literal_or_none(resource.properties["StorageEncrypted"])
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
                    f"RDS DB instance {resource.logical_id!r} has StorageEncrypted {why}; "
                    "data at rest is not encrypted."
                ),
                remediation=remediation_for(self.id),
            )
        ]


@register
class RdsPubliclyAccessible(Rule):
    """CFN_RDS_002 — DB instance has PubliclyAccessible true.

    Fires only on the literal ``true``. Absence is treated as the AWS default
    (false) and is not flagged. Unresolved intrinsics do not fire.
    """

    id: ClassVar[str] = "CFN_RDS_002"
    title: ClassVar[str] = "RDS DB instance is publicly accessible"
    severity: ClassVar[Severity] = Severity.CRITICAL
    resource_types: ClassVar[frozenset[str]] = frozenset({"AWS::RDS::DBInstance"})

    def evaluate(self, resource: Resource, template: Template) -> list[RuleFinding]:
        """Fire on a literal-true ``PubliclyAccessible``."""
        value = literal_or_none(resource.properties.get("PubliclyAccessible"))
        if value is not True:
            return []
        return [
            RuleFinding(
                rule_id=self.id,
                severity=self.severity,
                resource_logical_id=resource.logical_id,
                message=(
                    f"RDS DB instance {resource.logical_id!r} is publicly accessible; "
                    "the database is reachable from the public internet."
                ),
                remediation=remediation_for(self.id),
            )
        ]
