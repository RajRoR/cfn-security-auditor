"""Deterministic, network-free remediation provider.

Reads :data:`cfn_auditor.rules.remediation.REMEDIATION_BY_RULE_ID` — the same
canonical map the rule classes use when emitting findings. Identical input
always yields identical output. No retries, no LLM, no network.
"""

from collections.abc import Iterable

from cfn_auditor.advisor.dto import AdviceItem, FindingInput
from cfn_auditor.rules.remediation import REMEDIATION_BY_RULE_ID

__all__ = ["StaticRemediationProvider"]


_FALLBACK_REMEDIATION = (
    "Review this finding manually — no static remediation is registered "
    "for the rule that produced it."
)


class StaticRemediationProvider:
    """Returns curated remediation strings keyed by rule id."""

    name: str = "static"

    def advise(self, findings: Iterable[FindingInput]) -> list[AdviceItem]:
        """Return one :class:`AdviceItem` per finding, in the order received.

        Findings whose ``rule_id`` is not registered in the canonical map
        get a clear fallback string rather than a crash, in line with the
        fail-open contract.
        """
        return [
            AdviceItem(
                finding_id=f.finding_id,
                rule_id=f.rule_id,
                severity=f.severity,
                resource_logical_id=f.resource_logical_id,
                message=f.message,
                remediation=REMEDIATION_BY_RULE_ID.get(f.rule_id, _FALLBACK_REMEDIATION),
                source=self.name,
            )
            for f in findings
        ]
