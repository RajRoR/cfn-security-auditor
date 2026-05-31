"""Security-group guardrails."""

from typing import Any, ClassVar

from cfn_auditor.parser import Resource, Template
from cfn_auditor.rules.base import Rule
from cfn_auditor.rules.finding import RuleFinding
from cfn_auditor.rules.intrinsics import literal_or_none
from cfn_auditor.rules.registry import register
from cfn_auditor.rules.severity import Severity

__all__ = ["SecurityGroupWideOpenIngress"]


_OPEN_CIDRS: frozenset[str] = frozenset({"0.0.0.0/0", "::/0"})
_HIGH_RISK_PORTS: tuple[int, ...] = (22, 3389)


def _port_range_covers_high_risk(from_port: Any, to_port: Any) -> bool:
    """Return True if the literal ``[from_port, to_port]`` range includes 22 or 3389.

    A port set to ``-1`` (CFN's "all ports" sentinel) is treated as covering
    every high-risk port. Unresolved intrinsics on either bound are treated
    as not-known and do not escalate severity.
    """
    fp = literal_or_none(from_port)
    tp = literal_or_none(to_port)
    if not isinstance(fp, int) or not isinstance(tp, int):
        return False
    if fp == -1 or tp == -1:
        return True
    low, high = (fp, tp) if fp <= tp else (tp, fp)
    return any(low <= port <= high for port in _HIGH_RISK_PORTS)


@register
class SecurityGroupWideOpenIngress(Rule):
    """CFN_SG_001 — SecurityGroup ingress open to the world.

    Fires on any inline ``SecurityGroupIngress`` entry whose ``CidrIp`` is
    literally ``0.0.0.0/0`` or whose ``CidrIpv6`` is literally ``::/0``.
    Severity is :class:`Severity.HIGH`, escalating to
    :class:`Severity.CRITICAL` when the literal port range covers SSH (22)
    or RDP (3389).

    Standalone ``AWS::EC2::SecurityGroupIngress`` resources are a documented
    MVP limitation — only inline rules are evaluated.
    """

    id: ClassVar[str] = "CFN_SG_001"
    title: ClassVar[str] = "SecurityGroup allows ingress from anywhere"
    severity: ClassVar[Severity] = Severity.HIGH
    resource_types: ClassVar[frozenset[str]] = frozenset({"AWS::EC2::SecurityGroup"})

    def evaluate(self, resource: Resource, template: Template) -> list[RuleFinding]:
        """Emit one finding per offending inline ingress entry."""
        ingress_value = resource.properties.get("SecurityGroupIngress")
        if ingress_value is None:
            return []
        if literal_or_none(ingress_value) is None:
            return []
        if not isinstance(ingress_value, list):
            return []

        findings: list[RuleFinding] = []
        for entry in ingress_value:
            if literal_or_none(entry) is None or not isinstance(entry, dict):
                continue
            cidr_v4 = literal_or_none(entry.get("CidrIp"))
            cidr_v6 = literal_or_none(entry.get("CidrIpv6"))
            wide_open = cidr_v4 in _OPEN_CIDRS or cidr_v6 in _OPEN_CIDRS
            if not wide_open:
                continue

            severity = self.severity
            if _port_range_covers_high_risk(entry.get("FromPort"), entry.get("ToPort")):
                severity = Severity.CRITICAL

            cidr = cidr_v4 if cidr_v4 in _OPEN_CIDRS else cidr_v6
            findings.append(
                RuleFinding(
                    rule_id=self.id,
                    severity=severity,
                    resource_logical_id=resource.logical_id,
                    message=(
                        f"SecurityGroup {resource.logical_id!r} allows ingress from "
                        f"{cidr} on ports {entry.get('FromPort')}-{entry.get('ToPort')}."
                    ),
                    remediation=(
                        "Restrict CidrIp/CidrIpv6 to a known network range and limit the "
                        "port range to the smallest set required."
                    ),
                )
            )
        return findings
