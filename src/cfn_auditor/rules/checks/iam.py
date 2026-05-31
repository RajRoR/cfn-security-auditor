"""IAM policy guardrails — wildcard Action / Resource on Allow statements."""

from typing import Any, ClassVar

from cfn_auditor.parser import Resource, Template
from cfn_auditor.rules.base import Rule
from cfn_auditor.rules.finding import RuleFinding
from cfn_auditor.rules.intrinsics import as_list, literal_or_none
from cfn_auditor.rules.registry import register
from cfn_auditor.rules.severity import Severity

__all__ = ["IamAllowActionWildcard", "IamAllowResourceWildcard"]


# Resource types whose Properties carry a single PolicyDocument.
_POLICY_DOCUMENT_TYPES: frozenset[str] = frozenset({"AWS::IAM::Policy", "AWS::IAM::ManagedPolicy"})
# Resource types whose Properties carry a list of inline Policies, each with
# a nested PolicyDocument.
_POLICIES_LIST_TYPES: frozenset[str] = frozenset(
    {"AWS::IAM::Role", "AWS::IAM::User", "AWS::IAM::Group"}
)
_ALL_IAM_TYPES: frozenset[str] = _POLICY_DOCUMENT_TYPES | _POLICIES_LIST_TYPES


def _iter_policy_documents(resource: Resource) -> list[Any]:
    """Yield every PolicyDocument attached to ``resource`` (literal-only).

    Documents that are themselves unresolved intrinsics are dropped — we
    cannot reason about their statements.
    """
    docs: list[Any] = []
    if resource.type in _POLICY_DOCUMENT_TYPES:
        doc = literal_or_none(resource.properties.get("PolicyDocument"))
        if doc is not None:
            docs.append(doc)
    if resource.type in _POLICIES_LIST_TYPES:
        policies = literal_or_none(resource.properties.get("Policies"))
        if isinstance(policies, list):
            for policy in policies:
                policy_lit = literal_or_none(policy)
                if not isinstance(policy_lit, dict):
                    continue
                doc = literal_or_none(policy_lit.get("PolicyDocument"))
                if doc is not None:
                    docs.append(doc)
        if resource.type == "AWS::IAM::Role":
            assume = literal_or_none(resource.properties.get("AssumeRolePolicyDocument"))
            if assume is not None:
                docs.append(assume)
    return docs


def _allow_statements(document: Any) -> list[dict[str, Any]]:
    """Return the literal Allow statements inside ``document``."""
    if not isinstance(document, dict):
        return []
    statements_value = literal_or_none(document.get("Statement"))
    if statements_value is None:
        return []
    statements = as_list(statements_value)
    out: list[dict[str, Any]] = []
    for stmt in statements:
        stmt_lit = literal_or_none(stmt)
        if not isinstance(stmt_lit, dict):
            continue
        effect = literal_or_none(stmt_lit.get("Effect"))
        if effect == "Allow":
            out.append(stmt_lit)
    return out


def _has_literal_star(value: Any) -> bool:
    """Return True if ``value`` (string or list) contains the literal full wildcard ``*``."""
    literal = literal_or_none(value)
    if literal is None:
        return False
    for item in as_list(literal):
        item_lit = literal_or_none(item)
        if item_lit == "*":
            return True
    return False


@register
class IamAllowActionWildcard(Rule):
    """CFN_IAM_001 — IAM Allow statement uses Action ``"*"``.

    Service-scoped wildcards (``s3:*``) are NOT flagged in MVP. Effect must
    be a literal ``"Allow"``; intrinsic Effect/Action values do not fire.
    """

    id: ClassVar[str] = "CFN_IAM_001"
    title: ClassVar[str] = "IAM Allow statement permits Action '*'"
    severity: ClassVar[Severity] = Severity.HIGH
    resource_types: ClassVar[frozenset[str]] = _ALL_IAM_TYPES

    def evaluate(self, resource: Resource, template: Template) -> list[RuleFinding]:
        """One finding per Allow statement whose Action contains ``"*"``."""
        findings: list[RuleFinding] = []
        for doc in _iter_policy_documents(resource):
            for stmt in _allow_statements(doc):
                if _has_literal_star(stmt.get("Action")):
                    findings.append(
                        RuleFinding(
                            rule_id=self.id,
                            severity=self.severity,
                            resource_logical_id=resource.logical_id,
                            message=(
                                f"IAM resource {resource.logical_id!r} has an Allow "
                                "statement permitting Action '*' (full administrative access)."
                            ),
                            remediation=(
                                "Replace Action '*' with the explicit set of API actions "
                                "the principal must perform."
                            ),
                        )
                    )
        return findings


@register
class IamAllowResourceWildcard(Rule):
    """CFN_IAM_002 — IAM Allow statement uses Resource ``"*"``.

    Effect must be a literal ``"Allow"``. The check fires only on the literal
    full wildcard; resource ARNs containing path wildcards (e.g.
    ``arn:aws:s3:::my-bucket/*``) are not flagged.
    """

    id: ClassVar[str] = "CFN_IAM_002"
    title: ClassVar[str] = "IAM Allow statement permits Resource '*'"
    severity: ClassVar[Severity] = Severity.MEDIUM
    resource_types: ClassVar[frozenset[str]] = _ALL_IAM_TYPES

    def evaluate(self, resource: Resource, template: Template) -> list[RuleFinding]:
        """One finding per Allow statement whose Resource contains ``"*"``."""
        findings: list[RuleFinding] = []
        for doc in _iter_policy_documents(resource):
            for stmt in _allow_statements(doc):
                if _has_literal_star(stmt.get("Resource")):
                    findings.append(
                        RuleFinding(
                            rule_id=self.id,
                            severity=self.severity,
                            resource_logical_id=resource.logical_id,
                            message=(
                                f"IAM resource {resource.logical_id!r} has an Allow "
                                "statement applying to Resource '*'."
                            ),
                            remediation=(
                                "Replace Resource '*' with explicit ARNs scoped to the "
                                "objects the principal must access."
                            ),
                        )
                    )
        return findings
