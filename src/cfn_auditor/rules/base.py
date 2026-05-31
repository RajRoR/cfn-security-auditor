"""Abstract base class for guardrail rules.

Each subclass declares its stable ``id``, human-readable ``title``, default
``severity``, and the CloudFormation ``resource_types`` it applies to. The
engine drives the dispatch: it iterates the registry, and for each
``(rule, resource)`` pair where ``resource.type in rule.resource_types`` it
calls :meth:`Rule.evaluate`.
"""

from abc import ABC, abstractmethod
from typing import ClassVar

from cfn_auditor.parser import Resource, Template
from cfn_auditor.rules.finding import RuleFinding
from cfn_auditor.rules.severity import Severity

__all__ = ["Rule"]


class Rule(ABC):
    """Base class for every guardrail rule."""

    id: ClassVar[str]
    title: ClassVar[str]
    severity: ClassVar[Severity]
    resource_types: ClassVar[frozenset[str]]

    @abstractmethod
    def evaluate(self, resource: Resource, template: Template) -> list[RuleFinding]:
        """Return findings raised against ``resource``.

        Implementations must:
          * Return ``[]`` when the resource is compliant.
          * Return ``[]`` when a target property is present but its value is an
            unresolved CloudFormation intrinsic (we cannot prove insecurity).
          * Return one or more :class:`RuleFinding` instances when an absence
            check fails, or when a literal value is provably insecure.

        ``template`` is supplied so cross-resource rules (later turns) can
        consult sibling resources without re-parsing.
        """
