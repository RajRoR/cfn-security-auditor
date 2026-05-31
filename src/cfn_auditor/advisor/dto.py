"""Plain typed DTOs crossing the advisor seam.

We never pass ORM rows across the provider boundary — the LLM provider in
part 2 may run out-of-process or under different auth, and a SQLModel-bound
row is the wrong shape for that.
"""

from dataclasses import dataclass

from cfn_auditor.models import Severity

__all__ = ["AdviceItem", "FindingInput"]


@dataclass(frozen=True)
class FindingInput:
    """Findings are passed into a provider as plain DTOs (no ORM rows).

    Attributes:
        finding_id: Persisted Finding row id (used by the API to align
            advice items with the source findings on the wire).
        rule_id: The rule that produced the finding (e.g. ``CFN_S3_001``).
        severity: Severity level on the finding.
        resource_logical_id: CFN logical id of the offending resource.
        resource_type: CFN type, e.g. ``AWS::S3::Bucket``.
        message: Human-readable description from the rule.
    """

    finding_id: int
    rule_id: str
    severity: Severity
    resource_logical_id: str
    resource_type: str
    message: str


@dataclass(frozen=True)
class AdviceItem:
    """One remediation entry returned by a provider.

    Attributes:
        finding_id: The :class:`FindingInput`'s id this advice is for.
        rule_id: Echoed for client convenience.
        severity: Echoed for client convenience.
        resource_logical_id: Echoed for client convenience.
        message: Echoed for client convenience.
        remediation: The remediation guidance produced by the provider.
        source: Provider label (e.g. ``"static"``, ``"llm:openai-gpt-4"``).
    """

    finding_id: int
    rule_id: str
    severity: Severity
    resource_logical_id: str
    message: str
    remediation: str
    source: str
