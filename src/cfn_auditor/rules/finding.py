"""RuleFinding DTO returned by every rule's ``evaluate``.

Plain immutable dataclass. The engine maps this onto the persisted ``Finding``
SQLModel. Rules MUST NOT import the db/models layer.
"""

from dataclasses import dataclass

from cfn_auditor.rules.severity import Severity

__all__ = ["RuleFinding"]


@dataclass(frozen=True)
class RuleFinding:
    """One rule violation against one resource.

    Attributes:
        rule_id: Stable rule identifier (e.g. ``CFN_S3_001``).
        severity: Severity assigned by the rule.
        resource_logical_id: The CloudFormation logical ID of the offending resource.
        message: Human-readable description of the violation.
        remediation: Short, actionable suggestion for the operator.
    """

    rule_id: str
    severity: Severity
    resource_logical_id: str
    message: str
    remediation: str
